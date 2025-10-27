"""
Convert 24-bit stereo WAV to 16-bit mono using pure Python (no ffmpeg needed)
"""
import os
import sys
import wave
import struct
import array

input_file = sys.argv[1] if len(sys.argv) > 1 else None

if not input_file or not os.path.exists(input_file):
    print("Usage: python convert_wav_python.py <input.wav>")
    sys.exit(1)

output_file = input_file.replace('.wav', '_16bit_mono.wav')

print(f"Converting: {os.path.basename(input_file)}")
print(f"Output: {os.path.basename(output_file)}")

# Read input WAV
with wave.open(input_file, 'rb') as wav_in:
    params = wav_in.getparams()
    n_channels = params.nchannels
    sampwidth = params.sampwidth
    framerate = params.framerate
    n_frames = params.nframes

    print(f"\nInput: {n_channels} channel(s), {sampwidth*8}-bit, {framerate} Hz")

    # Read all audio data
    audio_data = wav_in.readframes(n_frames)

# Convert based on sample width
if sampwidth == 3:  # 24-bit
    # Unpack 24-bit samples (3 bytes each)
    samples = []
    for i in range(0, len(audio_data), sampwidth * n_channels):
        for ch in range(n_channels):
            # Read 3 bytes for this sample
            offset = i + ch * 3
            if offset + 3 <= len(audio_data):
                # 24-bit little-endian to int
                b1, b2, b3 = audio_data[offset:offset+3]
                # Combine bytes (little-endian, signed)
                sample_24bit = b1 | (b2 << 8) | (b3 << 16)
                # Convert to signed (24-bit range: -8388608 to 8388607)
                if sample_24bit >= 0x800000:
                    sample_24bit -= 0x1000000

                samples.append(sample_24bit)

    print(f"Unpacked {len(samples)} samples")

    # Convert to mono if stereo (average channels)
    if n_channels == 2:
        mono_samples = []
        for i in range(0, len(samples), 2):
            if i + 1 < len(samples):
                avg = (samples[i] + samples[i+1]) // 2
                mono_samples.append(avg)
        samples = mono_samples
        print(f"Converted to mono: {len(samples)} samples")

    # Convert 24-bit to 16-bit (scale down)
    samples_16bit = array.array('h')  # signed short (16-bit)
    for sample in samples:
        # Scale from 24-bit (-8388608 to 8388607) to 16-bit (-32768 to 32767)
        sample_16bit = sample // 256  # Divide by 256 (2^8)
        # Clamp to 16-bit range
        sample_16bit = max(-32768, min(32767, sample_16bit))
        samples_16bit.append(sample_16bit)

    print(f"Converted to 16-bit: {len(samples_16bit)} samples")

elif sampwidth == 2:  # Already 16-bit
    # Just unpack and convert to mono if needed
    samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)

    if n_channels == 2:
        mono_samples = []
        for i in range(0, len(samples), 2):
            if i + 1 < len(samples):
                avg = (samples[i] + samples[i+1]) // 2
                mono_samples.append(avg)
        samples_16bit = array.array('h', mono_samples)
    else:
        samples_16bit = array.array('h', samples)

else:
    print(f"Unsupported sample width: {sampwidth} bytes")
    sys.exit(1)

# Write output WAV
with wave.open(output_file, 'wb') as wav_out:
    wav_out.setnchannels(1)  # Mono
    wav_out.setsampwidth(2)  # 16-bit
    wav_out.setframerate(framerate)
    wav_out.writeframes(samples_16bit.tobytes())

output_size = os.path.getsize(output_file) / (1024 * 1024)
print(f"\n✅ Conversion complete!")
print(f"Output: {output_file}")
print(f"Size: {output_size:.2f} MB")
print(f"Format: 1 channel, 16-bit, {framerate} Hz")
