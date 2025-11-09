#!/usr/bin/env python
"""Test DeepSeek-R1 API connectivity"""
import replicate
import json
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set Replicate token from environment
if 'REPLICATE_API_TOKEN' in os.environ:
    replicate.Client(api_token=os.environ['REPLICATE_API_TOKEN'])

def test_deepseek_api():
    print('=' * 60)
    print('Testing DeepSeek-R1 API')
    print('=' * 60)
    print('Model: deepseek-ai/deepseek-r1')
    print()

    try:
        # Simple test prompt
        test_prompt = '''You are an expert video editor. Analyze this transcript and return ONLY a JSON array.

Transcript: [0.0s - 5.0s] SPEAKER_00: Hello everyone
[5.0s - 10.0s] SPEAKER_00: This is a test video
[10.0s - 15.0s] SPEAKER_00: About video editing

Respond with ONLY this JSON format (no markdown, no explanation):
[{"start": 0.0, "end": 5.0, "reason": "test"}]
'''

        print('Calling DeepSeek API...')
        output = replicate.run(
            'deepseek-ai/deepseek-r1',
            input={
                'prompt': test_prompt,
                'max_tokens': 2048,
                'temperature': 0.1,
                'top_p': 1.0
            }
        )

        response = ''.join(output).strip()
        print('[OK] API call succeeded!')
        print()
        print('Raw Response:')
        print('-' * 60)
        print(response[:1000])
        print('-' * 60)
        print()

        # Try to parse as JSON
        original_response = response
        if response.startswith('```'):
            lines = response.split('```')
            if len(lines) >= 2:
                response = lines[1]
                if response.startswith('json'):
                    response = response[4:]
                response = response.strip()

        try:
            parsed = json.loads(response)
            print('[OK] JSON parsing succeeded!')
            print()
            print('Parsed JSON:')
            print('-' * 60)
            print(json.dumps(parsed, indent=2))
            print('-' * 60)
            print()
            print('[SUCCESS] DeepSeek-R1 is working correctly!')
            return True
        except json.JSONDecodeError as e:
            print(f'[FAIL] JSON parsing failed: {e}')
            print('Tried to parse:', response[:200])
            return False

    except Exception as e:
        print(f'[FAIL] API Error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_deepseek_api()
    sys.exit(0 if success else 1)
