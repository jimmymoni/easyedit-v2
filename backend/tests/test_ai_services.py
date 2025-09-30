import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import json

from services.soniox_client import SonioxClient
from services.openai_client import OpenAIClient
from services.ai_enhancer import AIEnhancementService

class TestSonioxClient:
    """Test cases for SonioxClient"""

    @pytest.fixture
    def soniox_client(self):
        """Create SonioxClient with mock API key"""
        with patch('services.soniox_client.Config.SONIOX_API_KEY', 'test_api_key'):
            return SonioxClient()

    @patch('services.soniox_client.requests.Session.post')
    def test_start_transcription_job_success(self, mock_post, soniox_client, temp_dir):
        """Test successful transcription job start"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'job_123'}
        mock_post.return_value = mock_response

        # Create dummy audio file
        audio_file = os.path.join(temp_dir, 'test.wav')
        with open(audio_file, 'wb') as f:
            f.write(b'dummy audio data')

        job_id = soniox_client._start_transcription_job(audio_file, True)

        assert job_id == 'job_123'
        mock_post.assert_called_once()

    @patch('services.soniox_client.requests.Session.post')
    def test_start_transcription_job_failure(self, mock_post, soniox_client, temp_dir):
        """Test transcription job start failure"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        # Create dummy audio file
        audio_file = os.path.join(temp_dir, 'test.wav')
        with open(audio_file, 'wb') as f:
            f.write(b'dummy audio data')

        job_id = soniox_client._start_transcription_job(audio_file, True)

        assert job_id is None

    @patch('services.soniox_client.requests.Session.get')
    def test_poll_transcription_job_completed(self, mock_get, soniox_client):
        """Test polling completed transcription job"""
        # Mock completed job response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'job_123',
            'status': 'COMPLETED',
            'transcript': 'Test transcript',
            'words': [
                {'text': 'Test', 'start_ms': 0, 'end_ms': 500, 'confidence': 0.95, 'speaker': 'Speaker1'},
                {'text': 'transcript', 'start_ms': 600, 'end_ms': 1200, 'confidence': 0.88, 'speaker': 'Speaker1'}
            ]
        }
        mock_get.return_value = mock_response

        result = soniox_client._poll_transcription_job('job_123')

        assert result is not None
        assert result['status'] == 'COMPLETED'
        assert 'transcript' in result

    @patch('services.soniox_client.requests.Session.get')
    def test_poll_transcription_job_failed(self, mock_get, soniox_client):
        """Test polling failed transcription job"""
        # Mock failed job response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'job_123',
            'status': 'FAILED',
            'error': 'Processing failed'
        }
        mock_get.return_value = mock_response

        result = soniox_client._poll_transcription_job('job_123')

        assert result is None

    def test_process_transcription_result(self, soniox_client, mock_soniox_response):
        """Test processing raw transcription result"""
        processed = soniox_client._process_transcription_result(mock_soniox_response)

        assert isinstance(processed, dict)
        assert 'transcript' in processed
        assert 'segments' in processed
        assert 'speakers' in processed
        assert 'duration' in processed
        assert 'confidence' in processed
        assert 'word_count' in processed

        # Check segments structure
        segments = processed['segments']
        assert len(segments) > 0

        for segment in segments:
            assert 'speaker' in segment
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'text' in segment
            assert 'words' in segment

    def test_get_speaker_segments(self, soniox_client):
        """Test extracting speaker segments"""
        transcription_result = {
            'segments': [
                {
                    'speaker': 'Speaker1',
                    'start_time': 0.0,
                    'end_time': 5.0,
                    'text': 'Hello world',
                    'words': [{'text': 'Hello'}, {'text': 'world'}],
                    'confidence': 0.95
                },
                {
                    'speaker': 'Speaker2',
                    'start_time': 6.0,
                    'end_time': 10.0,
                    'text': 'How are you',
                    'words': [{'text': 'How'}, {'text': 'are'}, {'text': 'you'}],
                    'confidence': 0.88
                }
            ]
        }

        speaker_segments = soniox_client.get_speaker_segments(transcription_result)

        assert len(speaker_segments) == 2
        assert speaker_segments[0]['speaker'] == 'Speaker1'
        assert speaker_segments[1]['speaker'] == 'Speaker2'
        assert speaker_segments[0]['duration'] == 5.0
        assert speaker_segments[1]['duration'] == 4.0

    def test_get_silence_detection_hints(self, soniox_client):
        """Test getting silence detection hints from transcription"""
        transcription_result = {
            'segments': [
                {'start_time': 0.0, 'end_time': 5.0},
                {'start_time': 8.0, 'end_time': 12.0},  # 3 second gap
                {'start_time': 15.0, 'end_time': 20.0}  # 3 second gap
            ]
        }

        silence_gaps = soniox_client.get_silence_detection_hints(
            transcription_result,
            min_gap_seconds=2.0
        )

        assert len(silence_gaps) == 2
        assert silence_gaps[0]['start_time'] == 5.0
        assert silence_gaps[0]['end_time'] == 8.0
        assert silence_gaps[0]['duration'] == 3.0

    @patch('services.soniox_client.requests.Session.get')
    def test_check_api_status(self, mock_get, soniox_client):
        """Test API status check"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        status = soniox_client.check_api_status()
        assert status == True

        # Mock failed response
        mock_response.status_code = 500
        status = soniox_client.check_api_status()
        assert status == False

class TestOpenAIClient:
    """Test cases for OpenAIClient"""

    @pytest.fixture
    def openai_client(self):
        """Create OpenAIClient with mock API key"""
        with patch('services.openai_client.Config.OPENAI_API_KEY', 'test_api_key'):
            return OpenAIClient()

    @patch('services.openai_client.OpenAI')
    def test_enhance_transcription_success(self, mock_create, openai_client, mock_openai_response):
        """Test successful transcription enhancement"""
        mock_create.return_value = mock_openai_response

        original_text = "this is a test transcript with errors"
        result = openai_client.enhance_transcription(original_text, "Context info")

        assert result['success'] == True
        assert 'original' in result
        assert 'enhanced' in result
        assert 'improvement_score' in result
        assert result['original'] == original_text

    def test_enhance_transcription_no_api_key(self):
        """Test transcription enhancement without API key"""
        client = OpenAIClient(api_key=None)
        result = client.enhance_transcription("test text")

        assert result['success'] == False
        assert 'error' in result

    @patch('services.openai_client.OpenAI')
    def test_extract_highlights_success(self, mock_create, openai_client):
        """Test successful highlight extraction"""
        # Mock response with JSON highlights
        mock_response = {
            'choices': [{
                'message': {
                    'content': '[{"start_time": 5.0, "end_time": 15.0, "reason": "Key insight", "priority": "high"}]'
                }
            }]
        }
        mock_create.return_value = mock_response

        transcription_data = {
            'transcript': 'This is a test transcript with important information.',
            'segments': [{'start_time': 0, 'end_time': 20, 'text': 'Test content'}]
        }

        result = openai_client.extract_highlights(transcription_data, 300)

        assert result['success'] == True
        assert 'highlights' in result
        assert isinstance(result['highlights'], list)

    @patch('services.openai_client.OpenAI')
    def test_generate_summary_success(self, mock_create, openai_client):
        """Test successful summary generation"""
        mock_response = {
            'choices': [{
                'message': {
                    'content': 'This is a concise summary of the content.'
                }
            }]
        }
        mock_create.return_value = mock_response

        transcript = "This is a long transcript that needs to be summarized into key points."
        result = openai_client.generate_summary(transcript, 100)

        assert result['success'] == True
        assert 'summary' in result
        assert 'compression_ratio' in result

    @patch('services.openai_client.OpenAI')
    def test_suggest_editing_improvements(self, mock_create, openai_client):
        """Test editing suggestions generation"""
        mock_response = {
            'choices': [{
                'message': {
                    'content': '1. Improve pacing\n2. Add transitions\n3. Remove redundancy'
                }
            }]
        }
        mock_create.return_value = mock_response

        timeline_stats = {'original_duration': 300, 'edited_clips': 15}
        transcription_data = {'speakers': ['Speaker1'], 'confidence': 0.9}

        result = openai_client.suggest_editing_improvements(timeline_stats, transcription_data)

        assert result['success'] == True
        assert 'suggestions' in result

    def test_calculate_improvement_score(self, openai_client):
        """Test improvement score calculation"""
        original = "this is test text"
        enhanced = "This is a test text."

        score = openai_client._calculate_improvement_score(original, enhanced)

        assert 0.0 <= score <= 1.0
        # Enhanced version should have better score due to punctuation
        assert score > 0.0

    def test_extract_highlights_fallback(self, openai_client):
        """Test fallback highlight extraction"""
        segments = [
            {'start_time': 0, 'end_time': 10, 'confidence': 0.9, 'text': 'High confidence'},
            {'start_time': 15, 'end_time': 20, 'confidence': 0.5, 'text': 'Low confidence'},
            {'start_time': 25, 'end_time': 35, 'confidence': 0.95, 'text': 'Very high confidence'}
        ]

        result = openai_client._extract_highlights_fallback(segments, 15.0)

        assert result['success'] == True
        assert 'highlights' in result
        assert result['total_suggested_duration'] <= 15.0

class TestAIEnhancementService:
    """Test cases for AIEnhancementService"""

    @pytest.fixture
    def ai_enhancer(self):
        """Create AI enhancement service"""
        with patch('services.ai_enhancer.Config.OPENAI_API_KEY', 'test_api_key'):
            return AIEnhancementService()

    def test_enhance_timeline_processing_no_api_key(self):
        """Test enhancement without API key"""
        enhancer = AIEnhancementService()
        enhancer.openai_client = None

        timeline = Mock()
        result = enhancer.enhance_timeline_processing(timeline)

        assert result['success'] == False
        assert 'error' in result

    @patch.object(OpenAIClient, 'enhance_transcription')
    @patch.object(OpenAIClient, 'extract_highlights')
    def test_enhance_timeline_processing_success(self, mock_highlights, mock_enhance, ai_enhancer, sample_timeline, sample_transcription_data):
        """Test successful timeline enhancement"""
        # Mock successful OpenAI responses
        mock_enhance.return_value = {'success': True, 'enhanced': 'Enhanced text'}
        mock_highlights.return_value = {'success': True, 'highlights': []}

        result = ai_enhancer.enhance_timeline_processing(
            sample_timeline,
            sample_transcription_data,
            None
        )

        assert result['success'] == True
        assert 'applied_enhancements' in result

    def test_analyze_content_structure(self, ai_enhancer, sample_timeline, sample_transcription_data):
        """Test content structure analysis"""
        result = ai_enhancer._analyze_content_structure(sample_timeline, sample_transcription_data)

        assert result['success'] == True
        assert 'timeline_structure' in result
        assert 'content_analysis' in result
        assert 'pacing_recommendations' in result

        # Check timeline structure
        structure = result['timeline_structure']
        assert 'total_clips' in structure
        assert 'average_clip_duration' in structure

        # Check content analysis
        content = result['content_analysis']
        assert 'speaker_count' in content
        assert 'segments_count' in content

    def test_calculate_speaker_balance(self, ai_enhancer):
        """Test speaker balance calculation"""
        segments = [
            {'speaker': 'Speaker1', 'start_time': 0, 'end_time': 10},    # 10 seconds
            {'speaker': 'Speaker2', 'start_time': 10, 'end_time': 15},   # 5 seconds
            {'speaker': 'Speaker1', 'start_time': 15, 'end_time': 25}    # 10 seconds
        ]

        balance = ai_enhancer._calculate_speaker_balance(segments)

        assert isinstance(balance, dict)
        assert 'Speaker1' in balance
        assert 'Speaker2' in balance

        # Speaker1 should have 20/25 = 80% of time
        assert abs(balance['Speaker1'] - 0.8) < 0.01
        # Speaker2 should have 5/25 = 20% of time
        assert abs(balance['Speaker2'] - 0.2) < 0.01

    def test_analyze_conversation_dynamics(self, ai_enhancer):
        """Test conversation dynamics analysis"""
        segments = [
            {'speaker': 'Speaker1', 'start_time': 0, 'end_time': 10},
            {'speaker': 'Speaker2', 'start_time': 10, 'end_time': 15},
            {'speaker': 'Speaker1', 'start_time': 15, 'end_time': 20},
            {'speaker': 'Speaker2', 'start_time': 20, 'end_time': 30}
        ]

        dynamics = ai_enhancer._analyze_conversation_dynamics(segments)

        assert isinstance(dynamics, dict)
        assert 'speaker_changes' in dynamics
        assert 'change_frequency' in dynamics
        assert 'average_segment_length' in dynamics
        assert 'conversation_style' in dynamics

        # Should detect 3 speaker changes
        assert dynamics['speaker_changes'] == 3

    def test_classify_conversation_style(self, ai_enhancer):
        """Test conversation style classification"""
        # Rapid exchange (many speaker changes)
        style = ai_enhancer._classify_conversation_style(10, 12, 2.0)
        assert style == 'rapid_exchange'

        # Balanced discussion
        style = ai_enhancer._classify_conversation_style(5, 10, 5.0)
        assert style == 'balanced_discussion'

        # Monologue style (long segments)
        style = ai_enhancer._classify_conversation_style(2, 10, 35.0)
        assert style == 'monologue_style'

        # Presentation style
        style = ai_enhancer._classify_conversation_style(1, 10, 10.0)
        assert style == 'presentation_style'

    def test_generate_pacing_recommendations(self, ai_enhancer):
        """Test pacing recommendations generation"""
        analysis = {
            'timeline_structure': {
                'average_clip_duration': 35.0,  # Long clips
                'clip_duration_variance': 150.0,  # High variance
                'total_clips': 10
            },
            'content_analysis': {
                'conversation_dynamics': {
                    'conversation_style': 'rapid_exchange'
                },
                'speaker_balance': {
                    'Speaker1': 0.9,  # Dominant speaker
                    'Speaker2': 0.1
                }
            }
        }

        recommendations = ai_enhancer._generate_pacing_recommendations(analysis)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Should recommend shorter clips for long average duration
        long_clip_warning = any('shorter clips' in rec for rec in recommendations)
        assert long_clip_warning

        # Should mention speaker dominance
        dominance_warning = any('dominates' in rec for rec in recommendations)
        assert dominance_warning

    def test_get_enhancement_summary(self, ai_enhancer):
        """Test enhancement summary generation"""
        enhancements = {
            'applied_enhancements': ['transcription_enhancement', 'highlight_extraction'],
            'highlights': {'highlights': [1, 2, 3]},
            'structure_analysis': {
                'timeline_structure': {'total_clips': 15, 'average_clip_duration': 8.5}
            },
            'editing_suggestions': {'suggestions': 'Test suggestions'},
            'markers': {'markers': [1, 2, 3, 4]}
        }

        summary = ai_enhancer.get_enhancement_summary(enhancements)

        assert isinstance(summary, dict)
        assert summary['total_enhancements'] == 2
        assert 'key_insights' in summary
        assert 'recommended_actions' in summary
        assert len(summary['key_insights']) > 0
        assert len(summary['recommended_actions']) > 0