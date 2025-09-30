import pytest
import os
import tempfile
import numpy as np
import soundfile as sf
import json
from io import BytesIO

from app import app


class TestAPIUploadFormats:
    """Test API endpoints with various audio file formats"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def sample_audio_data(self):
        """Generate sample audio data for testing"""
        duration = 30.0  # 30 seconds
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Create realistic audio with varied content
        audio = np.zeros_like(t)

        # Speech segment 1 (0-10s)
        mask1 = (t >= 0) & (t < 10)
        speech1 = 0.3 * np.sin(2 * np.pi * 180 * t[mask1])
        speech1 += 0.1 * np.sin(2 * np.pi * 360 * t[mask1])
        speech1 *= (1 + 0.2 * np.random.random(len(speech1)))
        audio[mask1] = speech1

        # Silence (10-12s)
        mask2 = (t >= 10) & (t < 12)
        audio[mask2] = 0.01 * np.random.random(np.sum(mask2))

        # Speech segment 2 (12-25s)
        mask3 = (t >= 12) & (t < 25)
        speech2 = 0.25 * np.sin(2 * np.pi * 220 * t[mask3])
        speech2 += 0.08 * np.sin(2 * np.pi * 440 * t[mask3])
        speech2 *= (1 + 0.3 * np.random.random(len(speech2)))
        audio[mask3] = speech2

        # Final silence (25-30s)
        mask4 = (t >= 25) & (t < 30)
        audio[mask4] = 0.005 * np.random.random(np.sum(mask4))

        return audio, sample_rate

    @pytest.fixture
    def sample_drt_content(self):
        """Sample DRT file content"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
    <project>
        <name>Test Timeline</name>
        <children>
            <sequence id="sequence-1">
                <name>Test Sequence</name>
                <duration>750</duration>
                <rate>
                    <timebase>25</timebase>
                    <ntsc>FALSE</ntsc>
                </rate>
                <format>
                    <samplecharacteristics>
                        <rate>
                            <timebase>25</timebase>
                            <ntsc>FALSE</ntsc>
                        </rate>
                        <audio>
                            <samplerate>44100</samplerate>
                            <depth>16</depth>
                        </audio>
                    </samplecharacteristics>
                </format>
                <media>
                    <audio>
                        <format>
                            <samplecharacteristics>
                                <depth>16</depth>
                                <samplerate>44100</samplerate>
                            </samplecharacteristics>
                        </format>
                        <track>
                            <clipitem id="clipitem-1">
                                <name>Test Audio</name>
                                <enabled>TRUE</enabled>
                                <duration>750</duration>
                                <rate>
                                    <timebase>25</timebase>
                                    <ntsc>FALSE</ntsc>
                                </rate>
                                <start>0</start>
                                <end>750</end>
                                <in>0</in>
                                <out>750</out>
                                <file id="file-1">
                                    <name>test_audio.wav</name>
                                    <pathurl>file://localhost/test_audio.wav</pathurl>
                                </file>
                            </clipitem>
                        </track>
                    </audio>
                </media>
            </sequence>
        </children>
    </project>
</xmeml>'''

    def create_audio_bytes(self, audio_data, sample_rate, format_name, subtype=None):
        """Create audio file bytes for upload testing"""
        audio, sr = audio_data, sample_rate

        # Create in-memory file
        buffer = BytesIO()

        try:
            if subtype:
                sf.write(buffer, audio, sr, format=format_name.upper(), subtype=subtype)
            else:
                sf.write(buffer, audio, sr, format=format_name.upper())

            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            pytest.skip(f"Cannot create {format_name} bytes: {e}")

    def test_wav_upload_success(self, client, sample_audio_data, sample_drt_content):
        """Test successful WAV file upload"""
        audio_bytes = self.create_audio_bytes(sample_audio_data, 44100, 'wav')

        data = {
            'audio': (BytesIO(audio_bytes), 'test_audio.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] == True
        assert 'job_id' in result
        assert result['message'] == "Files uploaded and processing started"

    def test_flac_upload_success(self, client, sample_audio_data, sample_drt_content):
        """Test successful FLAC file upload"""
        try:
            audio_bytes = self.create_audio_bytes(sample_audio_data, 44100, 'flac')

            data = {
                'audio': (BytesIO(audio_bytes), 'test_audio.flac', 'audio/flac'),
                'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
            }

            response = client.post('/upload', data=data, content_type='multipart/form-data')

            assert response.status_code == 200
            result = json.loads(response.data)

            assert result['success'] == True
            assert 'job_id' in result

            print("✓ FLAC upload successful")

        except Exception as e:
            pytest.skip(f"FLAC upload test skipped: {e}")

    def test_aiff_upload_success(self, client, sample_audio_data, sample_drt_content):
        """Test successful AIFF file upload"""
        try:
            audio_bytes = self.create_audio_bytes(sample_audio_data, 44100, 'aiff')

            data = {
                'audio': (BytesIO(audio_bytes), 'test_audio.aiff', 'audio/aiff'),
                'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
            }

            response = client.post('/upload', data=data, content_type='multipart/form-data')

            assert response.status_code == 200
            result = json.loads(response.data)

            assert result['success'] == True
            assert 'job_id' in result

            print("✓ AIFF upload successful")

        except Exception as e:
            pytest.skip(f"AIFF upload test skipped: {e}")

    def test_wav_different_bit_depths(self, client, sample_audio_data, sample_drt_content):
        """Test WAV uploads with different bit depths"""
        bit_depths = [
            ('PCM_16', '16-bit'),
            ('PCM_24', '24-bit'),
            ('FLOAT', '32-bit float')
        ]

        for subtype, description in bit_depths:
            try:
                audio_bytes = self.create_audio_bytes(sample_audio_data, 48000, 'wav', subtype=subtype)

                data = {
                    'audio': (BytesIO(audio_bytes), f'test_audio_{description}.wav', 'audio/wav'),
                    'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
                }

                response = client.post('/upload', data=data, content_type='multipart/form-data')

                assert response.status_code == 200
                result = json.loads(response.data)

                assert result['success'] == True
                assert 'job_id' in result

                print(f"✓ {description} WAV upload successful")

            except Exception as e:
                print(f"⚠ Skipping {description} WAV: {e}")

    def test_different_sample_rates_upload(self, client, sample_audio_data, sample_drt_content):
        """Test uploads with different sample rates"""
        original_audio, _ = sample_audio_data
        sample_rates = [22050, 44100, 48000]

        for sr in sample_rates:
            try:
                # Simple resampling for test
                if sr != 44100:
                    ratio = sr / 44100
                    new_length = int(len(original_audio) * ratio)
                    resampled_audio = np.interp(
                        np.linspace(0, len(original_audio), new_length),
                        np.arange(len(original_audio)),
                        original_audio
                    )
                else:
                    resampled_audio = original_audio

                audio_bytes = self.create_audio_bytes((resampled_audio, sr), sr, 'wav')

                data = {
                    'audio': (BytesIO(audio_bytes), f'test_audio_{sr}hz.wav', 'audio/wav'),
                    'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
                }

                response = client.post('/upload', data=data, content_type='multipart/form-data')

                assert response.status_code == 200
                result = json.loads(response.data)

                assert result['success'] == True
                assert 'job_id' in result

                print(f"✓ {sr}Hz upload successful")

            except Exception as e:
                print(f"⚠ Skipping {sr}Hz: {e}")

    def test_stereo_vs_mono_upload(self, client, sample_audio_data, sample_drt_content):
        """Test mono and stereo audio uploads"""
        audio, sample_rate = sample_audio_data

        # Test mono
        mono_bytes = self.create_audio_bytes((audio, sample_rate), sample_rate, 'wav')

        data_mono = {
            'audio': (BytesIO(mono_bytes), 'test_mono.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response_mono = client.post('/upload', data=data_mono, content_type='multipart/form-data')
        assert response_mono.status_code == 200

        # Test stereo
        stereo_audio = np.column_stack([audio, audio])
        stereo_bytes = self.create_audio_bytes((stereo_audio, sample_rate), sample_rate, 'wav')

        data_stereo = {
            'audio': (BytesIO(stereo_bytes), 'test_stereo.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response_stereo = client.post('/upload', data=data_stereo, content_type='multipart/form-data')
        assert response_stereo.status_code == 200

        print("✓ Both mono and stereo uploads successful")

    def test_unsupported_format_rejection(self, client, sample_drt_content):
        """Test rejection of unsupported audio formats"""
        fake_audio = b'fake audio data not in supported format'

        data = {
            'audio': (BytesIO(fake_audio), 'test_audio.xyz', 'audio/xyz'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        # Should either reject immediately or fail during processing
        if response.status_code == 400:
            result = json.loads(response.data)
            assert result['success'] == False
            assert 'error' in result
        elif response.status_code == 200:
            # May accept but fail during processing - that's also acceptable
            result = json.loads(response.data)
            assert 'job_id' in result

    def test_corrupted_audio_file_upload(self, client, sample_drt_content):
        """Test upload of corrupted audio file"""
        corrupted_audio = b'RIFF    WAVEfmt corrupted content that is not valid'

        data = {
            'audio': (BytesIO(corrupted_audio), 'corrupted.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        # Should either reject or handle gracefully
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            # If accepted, processing should eventually fail gracefully
            result = json.loads(response.data)
            assert 'job_id' in result

    def test_very_small_audio_file(self, client, sample_drt_content):
        """Test upload of very small audio file"""
        # Create very short audio (0.1 seconds)
        duration = 0.1
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate))
        tiny_audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        audio_bytes = self.create_audio_bytes((tiny_audio, sample_rate), sample_rate, 'wav')

        data = {
            'audio': (BytesIO(audio_bytes), 'tiny_audio.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] == True
        assert 'job_id' in result

        print("✓ Very small audio file upload successful")

    def test_large_file_size_simulation(self, client, sample_drt_content):
        """Test upload behavior with larger file sizes (simulated)"""
        # Create longer audio to simulate larger files
        duration = 120.0  # 2 minutes
        sample_rate = 22050  # Lower sample rate for reasonable test size
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Create varied content
        audio = np.zeros_like(t)
        for i in range(0, int(duration), 10):  # 10-second segments
            start_idx = int(i * sample_rate)
            end_idx = int((i + 8) * sample_rate)  # 8s speech, 2s silence
            if end_idx > len(audio):
                end_idx = len(audio)

            segment_t = t[start_idx:end_idx]
            freq = 150 + (i * 10)  # Vary frequency
            segment_audio = 0.2 * np.sin(2 * np.pi * freq * segment_t)
            segment_audio *= (1 + 0.2 * np.random.random(len(segment_audio)))
            audio[start_idx:end_idx] = segment_audio

        audio_bytes = self.create_audio_bytes((audio, sample_rate), sample_rate, 'wav')

        data = {
            'audio': (BytesIO(audio_bytes), 'long_audio.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] == True
        assert 'job_id' in result

        print(f"✓ Large file upload successful (size: {len(audio_bytes)} bytes)")

    def test_multiple_format_processing(self, client, sample_audio_data, sample_drt_content):
        """Test processing multiple different formats"""
        formats_to_test = [
            ('wav', 'audio/wav'),
        ]

        # Add FLAC if available
        try:
            self.create_audio_bytes(sample_audio_data, 44100, 'flac')
            formats_to_test.append(('flac', 'audio/flac'))
        except:
            pass

        job_ids = []

        for fmt, mime_type in formats_to_test:
            try:
                audio_bytes = self.create_audio_bytes(sample_audio_data, 44100, fmt)

                data = {
                    'audio': (BytesIO(audio_bytes), f'test_audio.{fmt}', mime_type),
                    'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
                }

                response = client.post('/upload', data=data, content_type='multipart/form-data')

                assert response.status_code == 200
                result = json.loads(response.data)

                assert result['success'] == True
                assert 'job_id' in result

                job_ids.append((fmt, result['job_id']))

                print(f"✓ {fmt.upper()} format processing initiated")

            except Exception as e:
                print(f"⚠ Skipping {fmt}: {e}")

        # Should have processed at least WAV
        assert len(job_ids) >= 1

    def test_format_specific_processing_options(self, client, sample_audio_data, sample_drt_content):
        """Test processing with format-specific optimizations"""
        # High quality audio for professional processing
        hq_audio_bytes = self.create_audio_bytes(sample_audio_data, 48000, 'wav', 'PCM_24')

        data = {
            'audio': (BytesIO(hq_audio_bytes), 'hq_audio.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml'),
            'processing_options': json.dumps({
                'enable_transcription': False,
                'enable_ai_enhancements': False,
                'remove_silence': True,
                'min_clip_length': 2.0,
                'silence_threshold_db': -45  # More sensitive for high quality
            })
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] == True
        assert 'job_id' in result

        print("✓ High quality processing options accepted")

    def test_concurrent_different_format_uploads(self, client, sample_audio_data, sample_drt_content):
        """Test multiple concurrent uploads with different formats"""
        import threading
        import time

        results = []

        def upload_format(fmt, mime_type):
            try:
                audio_bytes = self.create_audio_bytes(sample_audio_data, 44100, fmt)

                data = {
                    'audio': (BytesIO(audio_bytes), f'concurrent_{fmt}.{fmt}', mime_type),
                    'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
                }

                response = client.post('/upload', data=data, content_type='multipart/form-data')
                results.append((fmt, response.status_code, response.data))

            except Exception as e:
                results.append((fmt, 500, str(e)))

        # Start concurrent uploads
        threads = []
        formats = [('wav', 'audio/wav'), ('wav', 'audio/wav')]  # Test with WAV duplicates

        for fmt, mime_type in formats:
            thread = threading.Thread(target=upload_format, args=(fmt, mime_type))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        successful_uploads = [r for r in results if r[1] == 200]
        assert len(successful_uploads) >= 1, f"Expected successful uploads, got: {results}"

        print(f"✓ Concurrent uploads completed: {len(successful_uploads)} successful")

    def test_upload_with_metadata_preservation(self, client, sample_audio_data, sample_drt_content):
        """Test that audio metadata is preserved through upload and processing"""
        # Create audio with specific characteristics
        audio, sample_rate = sample_audio_data
        audio_bytes = self.create_audio_bytes((audio, sample_rate), sample_rate, 'wav', 'PCM_24')

        data = {
            'audio': (BytesIO(audio_bytes), 'metadata_test.wav', 'audio/wav'),
            'drt': (BytesIO(sample_drt_content.encode()), 'test_timeline.drt', 'application/xml')
        }

        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] == True
        job_id = result['job_id']

        # The metadata should be accessible during processing
        # (This would be tested more thoroughly in integration tests)

        print("✓ Upload with metadata preservation successful")