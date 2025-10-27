"""
Test Google Cloud Speech-to-Text V1p1beta1 with improved MP3 handling
Fixes incomplete transcription by:
1. Using beta API (better MP3 + diarization support)
2. Detecting audio properties (sample rate, channels)
3. Processing ALL results in response array
4. Using better model selection
"""

import os
import sys
import time
import subprocess
import json
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Fix Unicode console output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Tomso/Documents/easyedit-v2/backend/gcp-credentials/easyedit-stt-key.json'
project_id = 'key-fabric-463809-r7'
bucket_name = 'easyedit-v2-audio-staging'

# Audio file
audio_file = r'C:\Users\Tomso\Downloads\for easy edit test.mp3'

print("=" * 80)
print("Google Cloud Speech-to-Text V1p1beta1 Test (Beta API)")
print("=" * 80)

# Step 1: Analyze audio properties using ffprobe
print("\n[1/5] Analyzing audio properties...")
try:
    # Use ffprobe to get audio info (Python 3.13 compatible)
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        audio_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(result.stdout)

    # Extract audio stream info
    audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)

    if audio_stream:
        sample_rate = int(audio_stream.get('sample_rate', 0))
        channels = int(audio_stream.get('channels', 1))
        duration = float(audio_stream.get('duration', 0))

        print(f"   Sample Rate: {sample_rate} Hz")
        print(f"   Channels: {channels}")
        print(f"   Duration: {duration:.1f} seconds")
    else:
        print("   Warning: Could not find audio stream")
        sample_rate = None
        channels = 1
        duration = 0

    print(f"   File Size: {os.path.getsize(audio_file) / (1024*1024):.2f} MB")

except Exception as e:
    print(f"   Warning: Could not analyze audio: {e}")
    print(f"   Will proceed without sample rate info")
    sample_rate = None
    channels = 1
    duration = 0

# Step 2: Upload to GCS
print("\n[2/5] Uploading to Google Cloud Storage...")
try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/test_{timestamp}.mp3"
    blob = bucket.blob(blob_name)

    blob.upload_from_filename(audio_file)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    print(f"   Uploaded: {gcs_uri}")
except Exception as e:
    print(f"   ERROR: Upload failed: {e}")
    exit(1)

# Step 3: Configure recognition (Beta API)
print("\n[3/5] Configuring recognition (Beta API)...")
try:
    speech_client = speech.SpeechClient()

    # Build config with detected audio properties
    # Try with automatic language detection first
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        language_code='ml-IN',  # Malayalam - based on user's use case
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        model='default',  # video model may not support Malayalam well
        # use_enhanced=True,  # Enhanced may not be available for Malayalam
    )

    # Add sample rate if detected
    if sample_rate:
        config.sample_rate_hertz = sample_rate
        print(f"   Sample rate: {sample_rate} Hz")

    # Add diarization config
    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=2,
        max_speaker_count=6,
    )
    config.diarization_config = diarization_config

    print(f"   Model: default")
    print(f"   Language: ml-IN (Malayalam)")
    print(f"   Diarization: enabled (2-6 speakers)")

except Exception as e:
    print(f"   ERROR: Configuration failed: {e}")
    exit(1)

# Step 4: Start transcription
print("\n[4/5] Starting transcription...")
try:
    audio = speech.RecognitionAudio(uri=gcs_uri)

    start_time = time.time()
    operation = speech_client.long_running_recognize(config=config, audio=audio)

    print("   Waiting for operation to complete...")
    response = operation.result(timeout=600)

    elapsed = time.time() - start_time
    print(f"   Processing time: {elapsed:.1f} seconds")

except Exception as e:
    print(f"   ERROR: Transcription failed: {e}")

    # Cleanup
    print("\n[CLEANUP] Deleting temporary GCS file...")
    try:
        blob.delete()
        print("   Deleted successfully")
    except:
        pass

    exit(1)

# Step 5: Process ALL results
print("\n[5/5] Processing results...")
print(f"   Total results: {len(response.results)}")

full_transcript = []
all_segments = []
speakers = set()
total_words = 0

for i, result in enumerate(response.results):
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]
    full_transcript.append(alternative.transcript)

    print(f"\n   Result {i+1}/{len(response.results)}:")
    print(f"   - Transcript: {alternative.transcript[:100]}..." if len(alternative.transcript) > 100 else f"   - Transcript: {alternative.transcript}")
    print(f"   - Confidence: {alternative.confidence:.1%}")
    print(f"   - Words: {len(alternative.words) if hasattr(alternative, 'words') else 0}")

    # Extract speaker segments
    if hasattr(alternative, 'words') and alternative.words:
        current_speaker = None
        current_segment = []
        segment_start = None

        for word_info in alternative.words:
            speaker_tag = word_info.speaker_tag if hasattr(word_info, 'speaker_tag') else 0
            speaker = f"Speaker_{speaker_tag}"
            speakers.add(speaker)

            start_time = word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0
            end_time = word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0

            total_words += 1

            # New segment when speaker changes
            if speaker != current_speaker:
                if current_segment:
                    all_segments.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_segment),
                        'start_time': segment_start,
                        'end_time': end_time,
                        'confidence': alternative.confidence
                    })

                current_speaker = speaker
                current_segment = [word_info.word]
                segment_start = start_time
            else:
                current_segment.append(word_info.word)

        # Save last segment
        if current_segment:
            all_segments.append({
                'speaker': current_speaker,
                'text': ' '.join(current_segment),
                'start_time': segment_start,
                'end_time': end_time,
                'confidence': alternative.confidence
            })

# Display results
print("\n" + "=" * 80)
print("FINAL RESULTS")
print("=" * 80)

complete_transcript = ' '.join(full_transcript)
print(f"\nFULL TRANSCRIPT ({len(complete_transcript)} chars, {total_words} words):")
print("-" * 80)
print(complete_transcript)
print("-" * 80)

print(f"\nSPEAKER SEGMENTS ({len(all_segments)} segments, {len(speakers)} speakers):")
print("-" * 80)
for i, segment in enumerate(all_segments[:10]):  # Show first 10
    print(f"{i+1}. [{segment['speaker']}] ({segment['start_time']:.1f}s - {segment['end_time']:.1f}s)")
    print(f"   {segment['text'][:100]}..." if len(segment['text']) > 100 else f"   {segment['text']}")
    print()

if len(all_segments) > 10:
    print(f"   ... and {len(all_segments) - 10} more segments")

# Cleanup
print("\n[CLEANUP] Deleting temporary GCS file...")
try:
    blob.delete()
    print("   Deleted successfully")
except Exception as e:
    print(f"   Warning: Could not delete: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
