import asyncio
from anthropic import AsyncAnthropic, APIStatusError
from anthropic.types import TextBlock, ThinkingBlock
import pandas as pd
import re
import pathlib
import random
from typing import Dict, Union

class EssayGrader:
    def __init__(self, rubric, prompt, word_limit, anthroptic_api_key):
        self.client = AsyncAnthropic(
            api_key=anthroptic_api_key,
            max_retries=3,
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
        
        self.base_prompt = prompt
        self.base_prompt = self.base_prompt.replace('{{RUBRIC}}', rubric)
        self.base_prompt = self.base_prompt.replace('{{WORD_LIMIT}}', str(word_limit))
        self.df = pd.DataFrame(columns=self.response_fields + ['essay_id'])

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


    def _extract_fields_from_response(self, response_list) -> dict:
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
        # Set backoff parameters
        max_retries=5
        initial_delay=1
        backoff_factor=2
        max_delay=60

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
            retries = 0
            while retries <= max_retries:
                try:
                    print("Streaming response...")
                    async for text in stream.text_stream:
                        print(text, end="", flush=True)
                    print()
                    break
                except APIStatusError as e:
                    error_type = getattr(e, "type", "")
                    error_dict = getattr(e, "error", {})
                    print(f"Error type: {error_type}")
                    print(f"Error dict: {error_dict}")
                    retries += 1
                    if retries >= max_retries:
                        print(f"Max retries ({max_retries}) exceeded for streaming error")
                        raise
                    # Calculate delay with jitter
                    sleep_time = min(initial_delay * (backoff_factor ** (retries - 1)) * (1 + random.random() * 0.1), max_delay)
                    print(f"Retrying in {sleep_time:.2f} seconds (attempt {retries}/{max_retries})")
                    await asyncio.sleep(sleep_time)
                    continue 
        message = await stream.get_final_message()
        return message.content
