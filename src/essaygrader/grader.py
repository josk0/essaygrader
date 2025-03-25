import asyncio
from anthropic import AsyncAnthropic, APIStatusError
from anthropic.types import TextBlock, ThinkingBlock
import pandas as pd
import re
import pathlib
import time
import random
from functools import wraps
from typing import Dict, Union

def retry_with_exponential_backoff(max_retries=5, initial_delay=1, backoff_factor=2, max_delay=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except APIStatusError as e:
                    error_type = getattr(e, "type", "")
                    #error_message = getattr(e, "message", "")
                    
                    if "overloaded_error" in error_type or "rate_limit_error" in error_type:
                        retries += 1
                        if retries >= max_retries:
                            print(f"Max retries ({max_retries}) exceeded for APIStatusError")
                            raise
                        # Calculate delay with jitter
                        sleep_time = min(delay * (backoff_factor ** (retries - 1)) * (1 + random.random() * 0.1), max_delay)
                        print(f"API {error_type}. Retrying in {sleep_time:.2f} seconds (attempt {retries}/{max_retries})")
                        time.sleep(sleep_time)
                    else:
                        # Not an overloaded error, don't retry
                        raise
            
            # This line shouldn't be reached but is here for safety
            return func(*args, **kwargs)
        return wrapper
    return decorator

class EssayGrader:
    def __init__(self, rubric, prompt, word_limit, anthroptic_api_key):
        self.client = AsyncAnthropic(
            api_key=anthroptic_api_key,
        )

        self.response_fields = [ # a list of response fields in the prompt
        'criterion1',
        'criterion2',
        'criterion3',
        'criterion4',
        'score1',
        'score2',
        'score3',
        'score4',
        'overall_assessment',
        'total_score',
        'letter_grade',
        'student_feedback',
        'essay_analysis',
        ]
        
        #self.base_prompt = "You are an AI grading assistant for a philosophy and public policy course. Your task is to evaluate a student essay based on a provided rubric and general essay writing guidelines. Your goal is to maintain consistency and fairness in your assessment while being critical and thorough in your analysis.\n\nHere are the materials you'll be working with:\n\n1. The student's essay:\n<essay>\n{{ESSAY}}\n</essay>\n\n2. The grading rubric:\n<rubric>\n{{RUBRIC}}\n</rubric>\n\n3. The word limit for the essay:\n<word_limit>\n{{WORD_LIMIT}}\n</word_limit>\n\nInstructions for Essay Evaluation:\n\n1. Read the essay and rubric carefully.\n\n2. Keep these general guidelines for a good essay in mind:\n   - Contains a valid argument\n   - Has a clear structure\n   - Employs simple language\n   - Uses examples to illustrate points and support arguments\n   - Focuses on a few key points and develops them carefully\n   - Directly answers the question posed\n\n3. Conduct a thorough analysis of the essay. Do this work inside <essay_analysis> tags in your thinking block. In your analysis:\n   a) For each rubric criterion:\n      - Quote 2-3 key sentences from the essay that relate to that criterion.\n      - Explicitly state how well the essay meets the criterion.\n      - Provide a preliminary assessment (in terms of the rubric categories of good, needs improvement, etc.) for the criterion based on your analysis.\n   b) Identify and explicitly state the main argument presented in the essay.\n   c) List 3-5 supporting points for the main argument.\n   d) Critically examine each argument for validity and logical consistency.\n   e) Assess the essay's structure, language, use of examples, and focus.\n   f) Determine how well the essay addresses the assigned question or topic.\n\n   Be both charitable and critical in your analysis. Point out flaws, inconsistencies, or weak arguments. Consider the provided word limit when assessing the depth of engagement with the literature.\n\n   IMPORTANT: Focus solely on analyzing the essay. Do not create any fictional dialogues or characters (e.g., \"human\", \"assistant\", \"student\") in your analysis.\n\n4. After your analysis, evaluate the essay based on each rubric criterion. For each criterion:\n   a) Quote relevant parts of the essay.\n   b) List strengths and weaknesses.\n   c) Explicitly state how well the essay meets the criterion.\n   d) Justify your assessment based on the rubric.\n\n5. Calculate a total score out of 100, considering the essay's quality in each rubric dimension holistically.\n\n6. Assign a letter grade following the US system, based on your assessment.\n\n7. Provide a brief overall assessment of the essay's strengths and suggest 1-2 main points for improvement.\n\n8. Create feedback directly for the student based on your overall assessment. This feedback should:\n   a) Address the student directly\n   b) Use informal language (e.g., \"Good job!\" or \"Here are two things you could try for next time:\")\n   c) Be critical and precisely identify the 1-2 main weaknesses\n   d) \"Sandwich\" the critical points between encouraging and supportive words\n\nPresent your final evaluation using the following structure:\n\n<evaluation>\n\n<criterion1>\n[Evaluation for criterion 1]\n[Examples/quotes]\n</criterion1>\n<score1>\n[X]\n</score1>\n\n<criterion2>\n[Evaluation for criterion 2]\n[Examples/quotes]\n</criterion2>\n<score2>\n[X]\n</score2>\n\n[Continue for all criteria]\n\n<overall_assessment>\n[Brief, overall assessment of strengths and 1-2 points on how to improve]\n</overall_assessment>\n\n<total_score>\n[X]\n</total_score>\n\n<letter_grade>\n[X]\n</letter_grade>\n\n<student_feedback>\n[Informal feedback addressing the student directly, sandwiching critical points between encouraging words]\n</student_feedback>\n\n</evaluation>\n\nRemember:\n- Be objective, fair, and consistent in your grading.\n- Base your evaluation solely on the essay's content, how it meets the rubric criteria, and how well it follows the general essay guidelines.\n- Do not be lenient. Provide harsh, honest feedback where necessary.\n- Rigorously apply the grading rubric.\n\nBegin your evaluation by analyzing the essay in your thinking block using <essay_analysis> tags. Your final output should consist only of the evaluation structure provided above and should not duplicate or rehash any of the work you did in the thinking block."
        self.base_prompt = prompt
        self.base_prompt = self.base_prompt.replace('{{RUBRIC}}', rubric)
        self.base_prompt = self.base_prompt.replace('{{WORD_LIMIT}}', str(word_limit))
        self.df = pd.DataFrame(columns=self.response_fields + ['essay_id'])

    @retry_with_exponential_backoff(max_retries=5, initial_delay=1, backoff_factor=2)
    async def grade_essay(self, essay, essay_id):
        response_list = await self._send_to_api(essay)
        self._save_response_to_file(response_list, essay_id)
        response_dict = self._extract_fields_from_response(response_list)
        response_dict['essay_id'] = essay_id
        self.df = pd.concat([self.df, pd.DataFrame([response_dict])], ignore_index=True)
        return response_dict

    def grade_essays(self, directory: Union[str, pathlib.Path]):
        # Convert string path to Path object if needed
        if isinstance(directory, str):
            directory = pathlib.Path(directory)
        
        essays_dict = self._extract_essays_from_dir(directory)
        
        for essay_id, essay in essays_dict.items():
            print(f"Grading essay {essay_id}...")
            asyncio.run(self.grade_essay(
                essay=essay, 
                essay_id=essay_id))

    def _extract_essays_from_dir(self, directory: Union[str, pathlib.Path]) -> Dict[str, str]:
        """
        Extract essays from .txt and .md files in the given directory.
        
        Args:
            directory: Path to the directory containing essay files
            
        Returns:
            Dictionary mapping essay_id to essay_text
        """
        # Convert string path to Path object if needed
        if isinstance(directory, str):
            directory = pathlib.Path(directory)
        
        essays_dict = {}
        
        # Get all .txt and .md files in the directory
        file_paths = list(directory.glob("*.txt")) + list(directory.glob("*.md"))
        
        for file_path in file_paths:
            filename = file_path.name
            
            # Extract essay_id from filename
            if "Submission_Receipt_" in filename:
                start_idx = filename.find("Submission_Receipt_") + len("Submission_Receipt_")
                rest = filename[start_idx:]
                end_idx = rest.find("_")
                
                if end_idx != -1:
                    essay_id = rest[:end_idx]
                    
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8') as file:
                        essay_text = file.read()
                    
                    # Add to dictionary
                    essays_dict[essay_id] = essay_text
        
        return essays_dict

    def _save_response_to_file(self, response_list, essay_id: str):
        thinking_text = ""
        response_text = ""

        for content_block in response_list:
            if isinstance(content_block, ThinkingBlock):
                thinking_text = content_block.thinking
            if isinstance(content_block, TextBlock):
                response_text = content_block.text
            

        # Create the file content with appropriate headers
        file_content = f"======================\nThinking\n======================\n{thinking_text}\n\n"
        file_content += f"======================\nResponse\n======================\n{response_text}"

        # Save to file
        with open(f"{essay_id}.txt", "w", encoding="utf-8") as file:
            file.write(file_content)


    def _extract_fields_from_response(self, response_list, save_to_file: bool = False) -> dict:
        results_dict = {}

        for content_block in response_list:
            if isinstance(content_block, ThinkingBlock):
                thinking_text = content_block.thinking
            if isinstance(content_block, TextBlock):
                response_text = content_block.text
            
        joined_text = thinking_text + response_text

        for field in self.response_fields:
            pattern = f"<{field}>(.*?)</{field}>"
            match = re.search(pattern, joined_text, re.DOTALL)
            if match:
                results_dict[field] = match.group(1).strip()
            else:
                results_dict[field] = None

        return results_dict

    async def _send_to_api(self, essay) -> list:
        async with self.client.messages.stream(
            model="claude-3-7-sonnet-20250219",
            max_tokens=26000,
            temperature=1,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.base_prompt.replace('{{ESSAY}}', essay)
                        }
                    ]
                }
            ],
            thinking={
                "type": "enabled",
                "budget_tokens": 16000
            }
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            print()

        message = await stream.get_final_message()
        return message.content
