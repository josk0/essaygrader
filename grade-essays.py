"""
Essay Grading Script

This script loads a rubric and automatically grades essays using the EssayGrader class.
It reads essays from the specified input directory and saves the results to a CSV file.
"""
import os
from dotenv import load_dotenv
from src.essaygrader.grader import EssayGrader

# Load environment variables from .env file
# You need a .env file in the project top level folder with the line ANTHROPIC_API_KEY=__your_API_key
load_dotenv()
api_key=os.getenv("ANTHROPIC_API_KEY")

with open('rubric.txt', 'r') as file:
  rubric = file.read()

with open('prompt.txt', 'r') as file:
  prompt = file.read()

# with open('test-essay.txt', 'r') as file:
#     test_essay = file.read()

grader = EssayGrader(
  prompt=prompt,
  rubric=rubric, 
  word_limit=1500, 
  anthroptic_api_key=api_key)

# asyncio.run(grader.grade_essay(essay=test_essay, essay_id=0))

try:
  grader.grade_essays('./essays_input')
except Exception as e: 
  import traceback
  print(f"Error grading essays: {e}")
  print(f"Error type: {type(e)}")
  traceback.print_exc()
  if len(grader.df) > 0:
    print("Saving incomplete results...") 
    grader.df.to_csv('2025 essays incomplete.csv', index=False)
  else:
    print("No results to save.")

grader.df.to_csv('2025 essays.csv', index=False)
