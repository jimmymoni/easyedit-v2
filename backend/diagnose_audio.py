"""
Diagnostic script to analyze audio file properties and energy levels
Helps understand why transcription is incomplete
"""
import os
import sys
import wave
import subprocess
import json
import tempfile

# Fix Unicode console output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

audio_file = r'C:\Users\Tomso\Downloads\for easy edit test.mp3'

print("=" * 80)
print("AUDIO FILE DIAGNOSTIC ANALYSIS")
print("=" * 80)

# Step 1: Get audio properties with ffprobe
print("\n[1/3] Analyzing audio properties with ffprobe...")
try:
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        audio_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"   ERROR: ffprobe failed")
        print(f"   Make sure ffmpeg is installed")
        sys.exit(1)

    info = json.loads(result.stdout)

    # Extract format info
    format_info = info.get('format', {})
    print(f"\n   📁 FILE INFO:")
    print(f"   Format: {format_info.get('format_name', 'unknown')}")
    print(f"   Duration: {float(format_info.get('duration', 0)):.1f} seconds")
    print(f"   Bitrate: {int(format_info.get('bit_rate', 0)) // 1000} kbps")
    print(f"   Size: {int(format_info.get('size', 0)) / (1024*1024):.2f} MB")

    # Extract audio stream info
    audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)

    if audio_stream:
        print(f"\n   🎵 AUDIO STREAM:")
        print(f"   Codec: {audio_stream.get('codec_name', 'unknown')}")
        print(f"   Sample rate: {audio_stream.get('sample_rate', 'unknown')} Hz")
        print(f"   Channels: {audio_stream.get('channels', 'unknown')}")
        print(f"   Channel layout: {audio_stream.get('channel_layout', 'unknown')}")

        sample_rate = int(audio_stream.get('sample_rate', 0))
        duration = float(audio_stream.get('duration', 0))

except subprocess.CalledProcessError as e:
    print(f"   ERROR: Could not analyze with ffprobe: {e}")
    print(f"   Make sure ffmpeg is installed and in PATH")
    sys.exit(1)

# Step 2: Convert to WAV and analyze audio energy
print("\n[2/3] Converting to WAV for audio analysis...")
try:
    # Create temporary WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
        temp_wav_path = tmp_wav.name

    # Convert MP3 to WAV using ffmpeg
    cmd = [
        'ffmpeg',
        '-i', audio_file,
        '-ar', '16000',  # 16kHz sample rate (standard for speech)
        '-ac', '1',  # Mono
        '-y',  # Overwrite
        temp_wav_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)

    if result.returncode != 0:
        print(f"   ERROR: ffmpeg conversion failed")
        sys.exit(1)

    print(f"   ✓ Converted to WAV: {os.path.getsize(temp_wav_path) / (1024*1024):.2f} MB")

    # Read WAV file and analyze
    with wave.open(temp_wav_path, 'rb') as wav_file:
        # Get audio properties
        n_channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        framerate = wav_file.getframerate()
        n_frames = wav_file.getnframes()

        print(f"\n   🔊 WAV PROPERTIES:")
        print(f"   Channels: {n_channels}")
        print(f"   Sample width: {sampwidth} bytes")
        print(f"   Frame rate: {framerate} Hz")
        print(f"   Total frames: {n_frames:,}")
        print(f"   Duration: {n_frames / framerate:.1f} seconds")

        # Read audio data
        audio_data = wav_file.readframes(n_frames)

    # Analyze audio energy in chunks
    print(f"\n[3/3] Analyzing audio energy levels...")

    import struct
    import math

    # Convert bytes to integers
    if sampwidth == 1:
        audio_values = struct.unpack(f'{len(audio_data)}b', audio_data)
    elif sampwidth == 2:
        audio_values = struct.unpack(f'{len(audio_data)//2}h', audio_data)
    else:
        print(f"   Unsupported sample width: {sampwidth}")
        os.unlink(temp_wav_path)
        sys.exit(1)

    # Analyze in 1-second chunks
    chunk_size = framerate  # 1 second of audio
    total_chunks = len(audio_values) // chunk_size

    silent_chunks = 0
    speech_chunks = 0
    silence_threshold = 500  # Adjust based on your audio

    chunk_energies = []

    for i in range(total_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk = audio_values[start:end]

        # Calculate RMS energy for this chunk
        rms = math.sqrt(sum(x*x for x in chunk) / len(chunk))
        chunk_energies.append(rms)

        if rms < silence_threshold:
            silent_chunks += 1
        else:
            speech_chunks += 1

    # Calculate statistics
    avg_energy = sum(chunk_energies) / len(chunk_energies) if chunk_energies else 0
    max_energy = max(chunk_energies) if chunk_energies else 0
    min_energy = min(chunk_energies) if chunk_energies else 0

    print(f"\n   📊 ENERGY ANALYSIS (1-second chunks):")
    print(f"   Total chunks: {total_chunks}")
    print(f"   Speech chunks: {speech_chunks} ({speech_chunks/total_chunks*100:.1f}%)")
    print(f"   Silent chunks: {silent_chunks} ({silent_chunks/total_chunks*100:.1f}%)")
    print(f"\n   Average RMS energy: {avg_energy:.1f}")
    print(f"   Max RMS energy: {max_energy:.1f}")
    print(f"   Min RMS energy: {min_energy:.1f}")

    # Show energy distribution
    print(f"\n   🎯 ENERGY DISTRIBUTION (first 60 seconds):")
    for i in range(min(60, len(chunk_energies))):
        energy = chunk_energies[i]
        bar_length = int((energy / max_energy * 50)) if max_energy > 0 else 0
        bar = '█' * bar_length + '░' * (50 - bar_length)
        status = '🔊 SPEECH' if energy >= silence_threshold else '🔇 SILENT'
        print(f"   {i:3d}s: {bar} {status}")

    # Cleanup
    os.unlink(temp_wav_path)

except Exception as e:
    print(f"   ERROR: Audio analysis failed: {e}")
    import traceback
    traceback.print_exc()
    if os.path.exists(temp_wav_path):
        os.unlink(temp_wav_path)
    sys.exit(1)

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)

# Provide recommendation
print(f"\n💡 INTERPRETATION:")
if speech_chunks / total_chunks < 0.3:
    print(f"   ⚠️  Only {speech_chunks/total_chunks*100:.1f}% of audio has speech energy")
    print(f"   This audio appears to have LONG SILENT GAPS")
    print(f"   Google STT is correctly detecting and skipping silence")
    print(f"   The transcription IS working correctly!")
elif speech_chunks / total_chunks > 0.7:
    print(f"   ✓ {speech_chunks/total_chunks*100:.1f}% of audio has speech energy")
    print(f"   This audio has CONTINUOUS SPEECH")
    print(f"   If transcription only got 34 words, there may be:")
    print(f"   - Very low volume/poor recording quality")
    print(f"   - Heavy background noise masking speech")
    print(f"   - Speech in a language/accent Google struggles with")
    print(f"   - Audio codec/format issues")
else:
    print(f"   ~ {speech_chunks/total_chunks*100:.1f}% of audio has speech energy")
    print(f"   This audio has MODERATE SPEECH DENSITY")
    print(f"   Some silence/pauses are normal in natural speech")

print()
