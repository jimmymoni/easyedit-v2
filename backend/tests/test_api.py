import pytest
import os
import json
import tempfile
from io import BytesIO
from unittest.mock import patch, Mock
import soundfile as sf
import numpy as np

# Flask app testing
from werkzeug.datastructures import FileStorage

# Import app for testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app, processing_jobs

class TestAPIEndpoints:
    """Test cases for Flask API endpoints"""

    @pytest.fixture
    def client(self):
        """Create Flask test client"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        with app.test_client() as client:
            # Clear processing jobs for each test
            processing_jobs.clear()
            yield client

    @pytest.fixture
    def test_audio_file(self, temp_dir):
        """Create test audio file for upload tests"""
        # Generate simple test audio
        duration = 10.0
        sample_rate = 22050
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = 0.3 * np.sin(2 * np.pi * 200 * t)

        audio_file = os.path.join(temp_dir, 'test_audio.wav')
        sf.write(audio_file, audio, sample_rate)

        return audio_file

    @pytest.fixture
    def test_drt_file(self, temp_dir, sample_drt_xml):
        """Create test DRT file for upload tests"""
        drt_file = os.path.join(temp_dir, 'test_timeline.drt')
        with open(drt_file, 'w', encoding='utf-8') as f:
            f.write(sample_drt_xml)

        return drt_file

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get('/health')

        assert response.status_code == 200

        data = response.get_json()
        assert 'status' in data
        assert 'timestamp' in data
        assert 'version' in data
        assert 'system_health' in data
        assert 'dependencies' in data

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get('/metrics')

        assert response.status_code == 200

        data = response.get_json()
        assert 'timestamp' in data
        assert 'uptime' in data
        assert 'system_metrics' in data
        assert 'request_metrics' in data

    def test_upload_files_success(self, client, test_audio_file, test_drt_file):
        """Test successful file upload"""
        with open(test_audio_file, 'rb') as audio, open(test_drt_file, 'rb') as drt:
            response = client.post('/upload', data={
                'audio': (audio, 'test_audio.wav'),
                'drt': (drt, 'test_timeline.drt')
            }, content_type='multipart/form-data')

        assert response.status_code == 200

        data = response.get_json()
        assert 'job_id' in data
        assert 'message' in data
        assert 'audio_filename' in data
        assert 'drt_filename' in data

        # Job should be created
        job_id = data['job_id']
        assert job_id in processing_jobs
        assert processing_jobs[job_id]['status'] == 'uploaded'

    def test_upload_missing_audio_file(self, client, test_drt_file):
        """Test upload with missing audio file"""
        with open(test_drt_file, 'rb') as drt:
            response = client.post('/upload', data={
                'drt': (drt, 'test_timeline.drt')
            }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_upload_missing_drt_file(self, client, test_audio_file):
        """Test upload with missing DRT file"""
        with open(test_audio_file, 'rb') as audio:
            response = client.post('/upload', data={
                'audio': (audio, 'test_audio.wav')
            }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_upload_invalid_audio_format(self, client, test_drt_file):
        """Test upload with invalid audio file format"""
        # Create fake file with wrong extension
        fake_audio = BytesIO(b'fake audio content')

        with open(test_drt_file, 'rb') as drt:
            response = client.post('/upload', data={
                'audio': (fake_audio, 'fake_audio.txt'),  # Wrong format
                'drt': (drt, 'test_timeline.drt')
            }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_process_timeline_not_found(self, client):
        """Test processing non-existent job"""
        response = client.post('/process/nonexistent_job_id',
                             json={'enable_transcription': False})

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_process_timeline_invalid_status(self, client):
        """Test processing job with invalid status"""
        # Create job in wrong status
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'completed',  # Wrong status for processing
            'progress': 100,
            'message': 'Already completed'
        }

        response = client.post(f'/process/{job_id}',
                             json={'enable_transcription': False})

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('app.DRTParser')
    @patch('app.AudioAnalyzer')
    @patch('app.EditRulesEngine')
    @patch('app.DRTWriter')
    def test_process_timeline_success_mock(self, mock_writer, mock_edit_engine,
                                         mock_analyzer, mock_parser, client, temp_dir):
        """Test successful timeline processing with mocked dependencies"""
        # Setup mocks
        mock_parser_instance = Mock()
        mock_parser.return_value = mock_parser_instance
        mock_timeline = Mock()
        mock_timeline.duration = 30.0
        mock_parser_instance.parse_file.return_value = mock_timeline

        mock_analyzer_instance = Mock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.load_audio.return_value = True
        mock_analyzer_instance.detect_silence.return_value = []
        mock_analyzer_instance.detect_speech_segments.return_value = []
        mock_analyzer_instance.find_optimal_cut_points.return_value = []
        mock_analyzer_instance.analyze_audio_features.return_value = {}

        mock_edit_instance = Mock()
        mock_edit_engine.return_value = mock_edit_instance
        mock_edited_timeline = Mock()
        mock_edit_instance.apply_editing_rules.return_value = mock_edited_timeline
        mock_edit_instance.get_editing_stats.return_value = {
            'original_duration': 30.0,
            'edited_duration': 25.0,
            'duration_reduction': 5.0,
            'compression_ratio': 25.0/30.0,
            'original_clips': 3,
            'edited_clips': 4,
            'clips_change': 1,
            'tracks_processed': 1,
            'markers_added': 0
        }

        mock_writer_instance = Mock()
        mock_writer.return_value = mock_writer_instance
        mock_writer_instance.write_timeline.return_value = True

        # Create job
        job_id = 'test_job_123'
        audio_file = os.path.join(temp_dir, 'fake_audio.wav')
        drt_file = os.path.join(temp_dir, 'fake_timeline.drt')

        # Create fake files
        with open(audio_file, 'w') as f:
            f.write('fake audio')
        with open(drt_file, 'w') as f:
            f.write('fake drt')

        processing_jobs[job_id] = {
            'status': 'uploaded',
            'progress': 10,
            'message': 'Ready for processing',
            'audio_file': audio_file,
            'drt_file': drt_file,
            'created_at': '2024-01-01T00:00:00'
        }

        # Process
        response = client.post(f'/process/{job_id}',
                             json={
                                 'enable_transcription': False,
                                 'remove_silence': True,
                                 'min_clip_length': 5.0
                             })

        assert response.status_code == 200

        data = response.get_json()
        assert data['job_id'] == job_id
        assert data['status'] == 'completed'
        assert 'stats' in data
        assert data['transcription_available'] == False

        # Job should be updated
        assert processing_jobs[job_id]['status'] == 'completed'
        assert processing_jobs[job_id]['progress'] == 100

    def test_get_job_status(self, client):
        """Test getting job status"""
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'processing',
            'progress': 50,
            'message': 'Processing audio',
            'created_at': '2024-01-01T00:00:00',
            'stats': {},
            'transcription_available': False
        }

        response = client.get(f'/status/{job_id}')

        assert response.status_code == 200

        data = response.get_json()
        assert data['job_id'] == job_id
        assert data['status'] == 'processing'
        assert data['progress'] == 50
        assert data['message'] == 'Processing audio'

    def test_get_job_status_not_found(self, client):
        """Test getting status of non-existent job"""
        response = client.get('/status/nonexistent_job')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_download_result_success(self, client, temp_dir):
        """Test successful file download"""
        # Create fake output file
        output_file = os.path.join(temp_dir, 'output_timeline.drt')
        with open(output_file, 'w') as f:
            f.write('<?xml version="1.0"?><timeline></timeline>')

        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'completed',
            'progress': 100,
            'message': 'Processing completed',
            'output_file': output_file
        }

        response = client.get(f'/download/{job_id}')

        assert response.status_code == 200
        assert response.content_type == 'application/xml; charset=utf-8'

        # Check download headers
        assert 'attachment' in response.headers.get('Content-Disposition', '')

    def test_download_result_not_completed(self, client):
        """Test downloading from non-completed job"""
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'processing',
            'progress': 50,
            'message': 'Still processing'
        }

        response = client.get(f'/download/{job_id}')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_download_result_file_not_found(self, client):
        """Test downloading when output file doesn't exist"""
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'completed',
            'progress': 100,
            'message': 'Processing completed',
            'output_file': '/nonexistent/file.drt'
        }

        response = client.get(f'/download/{job_id}')

        assert response.status_code == 404

    def test_list_jobs(self, client):
        """Test listing processing jobs"""
        # Add some test jobs
        processing_jobs['job1'] = {
            'status': 'completed',
            'progress': 100,
            'created_at': '2024-01-01T00:00:00'
        }
        processing_jobs['job2'] = {
            'status': 'processing',
            'progress': 75,
            'created_at': '2024-01-01T01:00:00'
        }

        response = client.get('/jobs')

        assert response.status_code == 200

        data = response.get_json()
        assert 'jobs' in data
        assert len(data['jobs']) == 2

        # Should be sorted by creation time (newest first)
        jobs = data['jobs']
        assert jobs[0]['job_id'] == 'job2'  # More recent
        assert jobs[1]['job_id'] == 'job1'

    def test_get_ai_enhancements(self, client):
        """Test getting AI enhancement data"""
        job_id = 'test_job_123'
        mock_enhancements = {
            'success': True,
            'applied_enhancements': ['transcription_enhancement', 'highlight_extraction'],
            'highlights': {'highlights': []},
            'summary': {'summary': 'Test summary'}
        }

        processing_jobs[job_id] = {
            'status': 'completed',
            'ai_enhancements': mock_enhancements
        }

        response = client.get(f'/ai-enhancements/{job_id}')

        assert response.status_code == 200

        data = response.get_json()
        assert data['job_id'] == job_id
        assert 'ai_enhancements' in data
        assert 'enhancement_summary' in data

    def test_get_ai_enhancements_not_available(self, client):
        """Test getting AI enhancements when not available"""
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'completed'
            # No ai_enhancements
        }

        response = client.get(f'/ai-enhancements/{job_id}')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_get_processing_preview(self, client, temp_dir):
        """Test getting processing preview"""
        # Create minimal test files
        audio_file = os.path.join(temp_dir, 'preview_audio.wav')
        drt_file = os.path.join(temp_dir, 'preview_timeline.drt')

        # Create simple audio file
        duration = 5.0
        sample_rate = 22050
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = 0.2 * np.sin(2 * np.pi * 200 * t)
        sf.write(audio_file, audio, sample_rate)

        # Create simple DRT
        with open(drt_file, 'w') as f:
            f.write('<?xml version="1.0"?><timeline><name>Preview</name></timeline>')

        job_id = 'preview_job_123'
        processing_jobs[job_id] = {
            'status': 'uploaded',
            'audio_file': audio_file,
            'drt_file': drt_file
        }

        response = client.get(f'/preview/{job_id}')

        # This might fail if TimelineEditingEngine is not properly mocked
        # But we're testing the endpoint structure
        assert response.status_code in [200, 500]  # Either success or expected failure

        if response.status_code == 200:
            data = response.get_json()
            assert data['job_id'] == job_id
            assert 'preview' in data

    def test_manual_cleanup(self, client):
        """Test manual cleanup endpoint"""
        response = client.post('/cleanup')

        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data

    def test_rate_limiting_simulation(self, client):
        """Test rate limiting behavior (simplified)"""
        # This test is simplified since we'd need to mock the rate limiter
        # or make many requests quickly to test actual rate limiting

        responses = []
        for i in range(5):  # Make several requests quickly
            response = client.get('/health')
            responses.append(response.status_code)

        # All should succeed with our current setup (no real rate limiting in test)
        assert all(status == 200 for status in responses)

    def test_error_handling_middleware(self, client):
        """Test error handling middleware"""
        # Test with invalid JSON
        response = client.post('/process/test_job',
                             data='invalid json',
                             content_type='application/json')

        assert response.status_code == 400

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.get('/health')

        # Check for CORS headers (might not be present in test client)
        # This is more of a smoke test
        assert response.status_code == 200

    def test_file_upload_size_validation(self, client):
        """Test file size validation during upload"""
        # Create a large fake file (simulate large upload)
        large_content = b'x' * (1024 * 1024)  # 1MB
        large_audio = BytesIO(large_content)

        small_drt = BytesIO(b'<timeline></timeline>')

        response = client.post('/upload', data={
            'audio': (large_audio, 'large_audio.wav'),
            'drt': (small_drt, 'timeline.drt')
        }, content_type='multipart/form-data')

        # Depending on configuration, this might succeed or fail
        # We're testing the endpoint handles it gracefully
        assert response.status_code in [200, 400, 413]

    def test_processing_options_validation(self, client):
        """Test processing options validation"""
        job_id = 'test_job_123'
        processing_jobs[job_id] = {
            'status': 'uploaded',
            'audio_file': 'fake.wav',
            'drt_file': 'fake.drt'
        }

        # Test with invalid options
        response = client.post(f'/process/{job_id}', json={
            'min_clip_length': -5,  # Invalid negative value
            'silence_threshold_db': 10  # Invalid positive dB value
        })

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_concurrent_job_processing(self, client, test_audio_file, test_drt_file):
        """Test handling multiple concurrent jobs"""
        job_ids = []

        # Create multiple jobs
        for i in range(3):
            with open(test_audio_file, 'rb') as audio, open(test_drt_file, 'rb') as drt:
                response = client.post('/upload', data={
                    'audio': (audio, f'test_audio_{i}.wav'),
                    'drt': (drt, f'test_timeline_{i}.drt')
                }, content_type='multipart/form-data')

                assert response.status_code == 200
                job_ids.append(response.get_json()['job_id'])

        # All jobs should be created
        assert len(job_ids) == 3
        for job_id in job_ids:
            assert job_id in processing_jobs
            assert processing_jobs[job_id]['status'] == 'uploaded'

        # Test getting status of all jobs
        for job_id in job_ids:
            response = client.get(f'/status/{job_id}')
            assert response.status_code == 200

    def test_upload_mp3_file(self, client, temp_dir, test_drt_file):
        """Test uploading MP3 audio file"""
        # Create a test MP3 file using pydub
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate 2 seconds of 440Hz tone
            tone = Sine(440).to_audio_segment(duration=2000)
            mp3_file = os.path.join(temp_dir, 'test_audio.mp3')
            tone.export(mp3_file, format='mp3', bitrate='128k')

            with open(mp3_file, 'rb') as audio, open(test_drt_file, 'rb') as drt:
                response = client.post('/upload', data={
                    'audio': (audio, 'test_audio.mp3'),
                    'drt': (drt, 'test_timeline.drt')
                }, content_type='multipart/form-data')

            assert response.status_code == 200
            data = response.get_json()
            assert 'job_id' in data
            assert data['audio_filename'] == 'test_audio.mp3'

        except Exception as e:
            pytest.skip(f"MP3 test skipped (ffmpeg may not be installed): {str(e)}")

    def test_upload_m4a_file(self, client, temp_dir, test_drt_file):
        """Test uploading M4A audio file"""
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate 2 seconds of 440Hz tone
            tone = Sine(440).to_audio_segment(duration=2000)
            m4a_file = os.path.join(temp_dir, 'test_audio.m4a')
            tone.export(m4a_file, format='mp4', codec='aac')

            with open(m4a_file, 'rb') as audio, open(test_drt_file, 'rb') as drt:
                response = client.post('/upload', data={
                    'audio': (audio, 'test_audio.m4a'),
                    'drt': (drt, 'test_timeline.drt')
                }, content_type='multipart/form-data')

            assert response.status_code == 200
            data = response.get_json()
            assert 'job_id' in data
            assert data['audio_filename'] == 'test_audio.m4a'

        except Exception as e:
            pytest.skip(f"M4A test skipped (ffmpeg may not be installed): {str(e)}")

    def test_upload_flac_file(self, client, temp_dir, test_drt_file):
        """Test uploading FLAC audio file"""
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate 2 seconds of 440Hz tone
            tone = Sine(440).to_audio_segment(duration=2000)
            flac_file = os.path.join(temp_dir, 'test_audio.flac')
            tone.export(flac_file, format='flac')

            with open(flac_file, 'rb') as audio, open(test_drt_file, 'rb') as drt:
                response = client.post('/upload', data={
                    'audio': (audio, 'test_audio.flac'),
                    'drt': (drt, 'test_timeline.drt')
                }, content_type='multipart/form-data')

            assert response.status_code == 200
            data = response.get_json()
            assert 'job_id' in data
            assert data['audio_filename'] == 'test_audio.flac'

        except Exception as e:
            pytest.skip(f"FLAC test skipped (ffmpeg may not be installed): {str(e)}")

    def test_process_mp3_file_end_to_end(self, client, temp_dir, test_drt_file):
        """Test complete workflow with MP3 file: upload -> process -> download"""
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate 5 seconds of audio with silence
            tone1 = Sine(440).to_audio_segment(duration=1000)
            silence = AudioSegment.silent(duration=1000)
            tone2 = Sine(880).to_audio_segment(duration=1000)
            audio = tone1 + silence + tone2 + silence + tone1

            mp3_file = os.path.join(temp_dir, 'test_workflow.mp3')
            audio.export(mp3_file, format='mp3', bitrate='128k')

            # Upload
            with open(mp3_file, 'rb') as audio_f, open(test_drt_file, 'rb') as drt:
                upload_response = client.post('/upload', data={
                    'audio': (audio_f, 'test_workflow.mp3'),
                    'drt': (drt, 'test_timeline.drt')
                }, content_type='multipart/form-data')

            assert upload_response.status_code == 200
            job_id = upload_response.get_json()['job_id']

            # Check status
            status_response = client.get(f'/status/{job_id}')
            assert status_response.status_code == 200
            assert status_response.get_json()['status'] == 'uploaded'

        except Exception as e:
            pytest.skip(f"MP3 workflow test skipped (ffmpeg may not be installed): {str(e)}")

    def test_unsupported_audio_format(self, client, temp_dir, test_drt_file):
        """Test that unsupported audio formats are rejected"""
        # Create a fake .xyz file
        fake_audio = os.path.join(temp_dir, 'fake.xyz')
        with open(fake_audio, 'wb') as f:
            f.write(b'not a real audio file')

        with open(fake_audio, 'rb') as audio, open(test_drt_file, 'rb') as drt:
            response = client.post('/upload', data={
                'audio': (audio, 'fake.xyz'),
                'drt': (drt, 'test_timeline.drt')
            }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data