A prompt and a primitive class to grade philosophy essays.

put some essays in `/essays_input` (as .txt or .md) your Anthropic API key in `.env` and run `grade_essays.py`

## Things that don't work

1. Model generates results in thinking_text block instead of response_text block. This usually happens when Claude gets into a discussion with the "student" and justifies the grade. The fields (such as `<score1>`) that populate the dataframe (and the csv) are hence then not where we expect them and you have to go find them in the output files when rows in the CSV are empty.
2. Grading is somewhat indeterministic: I suspect high variance in grades for same essay over multiple runs

## Things to fix

1. Improve the prompt to shut down excessive reasoning (such as discussions with the student)
2. extract fields from both thinking_block as well as response_block
3. Experiment with temperature parameter
4. Better error handling. Esp since API runs sometimes fail (httpx.ReadTimeout in `_send_to_api`): should save dataframe at the end either way

## Things that would be nice to have

1. load prompt from file
2. parametrize number of grading criteria in rubric (so that you can exchange rubric)