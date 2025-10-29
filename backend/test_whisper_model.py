"""
Test Replicate Whisper Diarization Model
"""
import os
import replicate
from dotenv import load_dotenv

load_dotenv()

# Get API token
api_token = os.getenv('REPLICATE_API_TOKEN')
print(f"[OK] Found REPLICATE_API_TOKEN: {api_token[:15]}...")

# Test different model formats
models_to_try = [
    "thomasmol/whisper-diarization",
    "vaibhavs10/incredibly-fast-whisper",
    "openai/whisper-large-v3",
]

print("\n[TEST] Testing Whisper models on Replicate...\n")

for model_id in models_to_try:
    try:
        print(f"Testing: {model_id}")

        # Try to get model info using replicate.models.get()
        parts = model_id.split('/')
        if len(parts) == 2:
            owner, name = parts
            model = replicate.models.get(f"{owner}/{name}")
            print(f"  [OK] Model exists: {model.name}")
            print(f"       Latest version: {model.latest_version.id if model.latest_version else 'None'}")

    except replicate.exceptions.ReplicateError as e:
        print(f"  [ERROR] {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected: {e}")

    print()

print("\n[DONE] Model testing complete")
