import os
from dotenv import load_dotenv
from src.essaygrader.grader import EssayGrader
import asyncio

# You need a .env file in the project top level folder with the line ANTHROPIC_API_KEY=__your_API_key
load_dotenv()

api_key=os.getenv("ANTHROPIC_API_KEY")

with open('rubric.txt', 'r') as file:
    rubric = file.read()

# with open('test-essay.txt', 'r') as file:
#     test_essay = file.read()

grader = EssayGrader(rubric, 1500, api_key)

# asyncio.run(grader.grade_essay(essay=test_essay, essay_id=0))

grader.grade_essays('./essays_input')

grader.df.to_csv('2025 essays.csv', index=False)
