"""
Optimized Google Cloud STT test with best practices for quality
- 16000 Hz sample rate (Google's recommended)
- Video model (better for clear speech)
- Enhanced models if available
- Proper language configuration
"""
import os
import sys
import time
import wave
import struct
import array
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Fix Unicode
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Config
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Tomso/Documents/easyedit-v2/backend/gcp-credentials/easyedit-stt-key.json'
bucket_name = 'easyedit-v2-audio-staging'

if len(sys.argv) < 2:
    print("Usage: python test_optimized_google_stt.py <wav_file>")
    sys.exit(1)

audio_file = sys.argv[1].strip().strip('"')

print("=" * 80)
print("OPTIMIZED GOOGLE CLOUD STT TEST")
print("Best practices: 16kHz + video model + enhanced")
print("=" * 80)

# Step 1: Check and convert to optimal format
print("\n[1/5] Checking audio format...")

with wave.open(audio_file, 'rb') as w:
    orig_rate = w.getframerate()
    orig_channels = w.getnchannels()
    orig_width = w.getsampwidth()
    duration = w.getnframes() / w.getframerate()

    print(f"   Original: {orig_channels}ch, {orig_width*8}-bit, {orig_rate} Hz, {duration:.1f}s")

needs_conversion = (orig_rate != 16000 or orig_channels != 1 or orig_width != 2)

if needs_conversion:
    print(f"\n[2/5] Converting to OPTIMAL format (16kHz mono 16-bit)...")

    # Read original
    with wave.open(audio_file, 'rb') as w_in:
        frames = w_in.readframes(w_in.getnframes())

        # Unpack based on sample width
        if orig_width == 3:  # 24-bit
            samples = []
            for i in range(0, len(frames), orig_width * orig_channels):
                for ch in range(orig_channels):
                    offset = i + ch * 3
                    if offset + 3 <= len(frames):
                        b1, b2, b3 = frames[offset:offset+3]
                        sample = b1 | (b2 << 8) | (b3 << 16)
                        if sample >= 0x800000:
                            sample -= 0x1000000
                        samples.append(sample)
        elif orig_width == 2:  # 16-bit
            samples = list(struct.unpack(f'<{len(frames)//2}h', frames))
        else:
            print(f"   Unsupported: {orig_width} bytes")
            sys.exit(1)

    # Convert to mono
    if orig_channels == 2:
        mono = [(samples[i] + samples[i+1]) // 2 for i in range(0, len(samples), 2) if i+1 < len(samples)]
        samples = mono

    # Resample to 16kHz if needed
    if orig_rate != 16000:
        # Simple resampling (linear interpolation)
        ratio = 16000 / orig_rate
        new_length = int(len(samples) * ratio)
        resampled = []

        for i in range(new_length):
            # Calculate source position
            src_pos = i / ratio
            src_idx = int(src_pos)

            if src_idx + 1 < len(samples):
                # Linear interpolation
                frac = src_pos - src_idx
                sample = int(samples[src_idx] * (1 - frac) + samples[src_idx + 1] * frac)
            else:
                sample = samples[-1]

            resampled.append(sample)

        samples = resampled
        print(f"   Resampled: {orig_rate} Hz → 16000 Hz")

    # Convert 24-bit to 16-bit if needed
    if orig_width == 3:
        samples = [max(-32768, min(32767, s // 256)) for s in samples]

    # Create output file
    converted_file = audio_file.replace('.wav', '_16k_mono.wav')

    samples_16 = array.array('h', samples)
    with wave.open(converted_file, 'wb') as w_out:
        w_out.setnchannels(1)
        w_out.setsampwidth(2)
        w_out.setframerate(16000)
        w_out.writeframes(samples_16.tobytes())

    print(f"   Saved: {converted_file}")
    print(f"   Format: 1ch, 16-bit, 16000 Hz")

    audio_file = converted_file
else:
    print("   Already optimal format!")
    print("\n[2/5] Skipping conversion...")

# Step 3: Upload to GCS
print(f"\n[3/5] Uploading to GCS...")

storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

timestamp = int(time.time())
blob_name = f"temp/optimized_{timestamp}.wav"
blob = bucket.blob(blob_name)

start_upload = time.time()
blob.upload_from_filename(audio_file)
upload_time = time.time() - start_upload

gcs_uri = f"gs://{bucket_name}/{blob_name}"
print(f"   Uploaded in {upload_time:.1f}s")
print(f"   URI: {gcs_uri}")

# Step 4: Configure with OPTIMIZED settings
print(f"\n[4/5] Configuring OPTIMIZED transcription...")

speech_client = speech.SpeechClient()

# OPTIMIZED CONFIGURATION
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,  # OPTIMAL: Google's recommended rate
    audio_channel_count=1,
    language_code='en-US',  # Try US English (may work better than en-IN)
    # alternative_language_codes=['en-IN', 'ml-IN'],  # NOT supported with enhanced models
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    enable_word_confidence=True,
    model='video',  # BETTER MODEL: optimized for clear speech
    use_enhanced=True,  # ENHANCED: Better quality (costs more)
)

# Diarization
diarization_config = speech.SpeakerDiarizationConfig(
    enable_speaker_diarization=True,
    min_speaker_count=1,
    max_speaker_count=2,
)
config.diarization_config = diarization_config

print(f"   Sample rate: 16000 Hz (optimal)")
print(f"   Model: video (enhanced)")
print(f"   Language: en-US only (enhanced models don't support alternatives)")
print(f"   Enhanced: YES (better quality)")

# Step 5: Transcribe
print(f"\n[5/5] Transcribing with optimized settings...")

audio = speech.RecognitionAudio(uri=gcs_uri)

start_time = time.time()
operation = speech_client.long_running_recognize(config=config, audio=audio)

print(f"   Processing...")
last_update = time.time()
while not operation.done():
    if time.time() - last_update > 15:
        print(f"   ... {time.time() - start_time:.0f}s elapsed")
        last_update = time.time()
    time.sleep(3)

response = operation.result(timeout=600)
elapsed = time.time() - start_time

print(f"   Completed in {elapsed:.1f}s")

# Process results
print(f"\n   Result segments: {len(response.results)}")

full_transcript = []
all_words = []

for result in response.results:
    if not result.alternatives:
        continue

    alt = result.alternatives[0]
    if alt.transcript.strip():
        full_transcript.append(alt.transcript)

    if hasattr(alt, 'words') and alt.words:
        for word_info in alt.words:
            all_words.append({
                'word': word_info.word,
                'start': word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0,
                'confidence': word_info.confidence if hasattr(word_info, 'confidence') else 0.0
            })

complete = ' '.join(full_transcript)

print("\n" + "=" * 80)
print("OPTIMIZED RESULTS")
print("=" * 80)

print(f"\n📊 Statistics:")
print(f"   Words: {len(all_words)}")
print(f"   Characters: {len(complete)}")

if all_words:
    avg_conf = sum(w['confidence'] for w in all_words) / len(all_words)
    print(f"   Avg confidence: {avg_conf:.1%}")

print(f"\n📝 Transcript:")
print("-" * 80)
if complete:
    # Word wrap
    words = complete.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 <= 76:
            line += word + " "
        else:
            print(f"   {line}")
            line = word + " "
    if line:
        print(f"   {line}")
else:
    print("   (No transcript)")
print("-" * 80)

# Save
output_file = sys.argv[1].replace('.wav', '_optimized_transcript.txt')
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("OPTIMIZED GOOGLE CLOUD STT TRANSCRIPT\n")
        f.write("=" * 80 + "\n\n")
        f.write(complete + "\n")
    print(f"\n💾 Saved: {output_file}")
except:
    pass

# Cleanup
try:
    blob.delete()
    print(f"   Cleaned up GCS file")
except:
    pass

print("\n" + "=" * 80)
print(f"✅ Complete - {len(all_words)} words transcribed")
print("=" * 80)
print()
