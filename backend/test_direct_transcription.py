"""
Direct test of Replicate Whisper transcription with actual audio file
"""
import os
import replicate
from dotenv import load_dotenv

load_dotenv()

# Path to test audio file (use the 14MB file the user uploaded)
test_audio = r"C:\Users\Tomso\Documents\easyedit-v2\backend\uploads\da666b79-39d3-4026-826f-2a2fc105fd4d_audio_Timeline_1_audio__1_.wav"

if not os.path.exists(test_audio):
    print(f"[ERROR] Test audio not found: {test_audio}")
    exit(1)

print(f"[OK] Found test audio: {test_audio}")
print(f"     File size: {os.path.getsize(test_audio) / (1024 * 1024):.1f}MB")

# Test transcription
print("\n[TEST] Testing transcription with replicate.run()...\n")

try:
    with open(test_audio, "rb") as audio_file:
        output = replicate.run(
            "thomasmol/whisper-diarization",
            input={
                "file": audio_file,
                "language": "en",
                "batch_size": 64,
            }
        )

    print("[SUCCESS] Transcription completed!")
    print(f"\nOutput type: {type(output)}")
    print(f"Output keys: {output.keys() if isinstance(output, dict) else 'N/A'}")

    if isinstance(output, dict):
        if 'segments' in output:
            print(f"\nSegments: {len(output['segments'])} segments")
            if output['segments']:
                first_seg = output['segments'][0]
                print(f"First segment: {first_seg}")

        if 'text' in output:
            transcript_text = output['text']
            print(f"\nTranscript preview: {transcript_text[:200]}...")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
