"""
AI enhancement background tasks
"""

from celery_app import celery_app
from config import Config
from services.openai_client import OpenAIClient
from utils.error_handlers import ProcessingError
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, queue='ai', priority=4)
def enhance_with_ai_task(self, timeline_data: dict, transcription_data: dict, audio_analysis: dict):
    """
    Background task for AI-powered timeline enhancement
    """
    try:
        if not Config.OPENAI_API_KEY:
            raise ProcessingError("OpenAI API key not configured")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Initializing AI enhancement'}
        )

        openai_client = OpenAIClient()

        # Enhance transcription if available
        enhanced_transcription = None
        if transcription_data and transcription_data.get('transcript'):
            self.update_state(
                state='PROGRESS',
                meta={'progress': 30, 'message': 'Enhancing transcription'}
            )

            enhanced_transcription = openai_client.enhance_transcription(
                transcription_data['transcript']
            )

        # Extract highlights
        highlights = None
        if transcription_data:
            self.update_state(
                state='PROGRESS',
                meta={'progress': 50, 'message': 'Extracting highlights'}
            )

            highlights = openai_client.extract_highlights(
                transcription_data,
                duration_limit=300  # 5 minutes of highlights
            )

        # Generate summary
        summary = None
        if transcription_data and transcription_data.get('transcript'):
            self.update_state(
                state='PROGRESS',
                meta={'progress': 70, 'message': 'Generating summary'}
            )

            summary = openai_client.generate_summary(
                transcription_data['transcript'],
                max_length=200
            )

        # Generate markers and chapters
        markers_and_chapters = None
        if transcription_data:
            self.update_state(
                state='PROGRESS',
                meta={'progress': 85, 'message': 'Creating markers and chapters'}
            )

            markers_and_chapters = openai_client.generate_markers_and_chapters(
                transcription_data
            )

        # Suggest editing improvements
        suggestions = None
        if timeline_data:
            self.update_state(
                state='PROGRESS',
                meta={'progress': 95, 'message': 'Generating editing suggestions'}
            )

            suggestions = openai_client.suggest_editing_improvements(
                timeline_data,
                transcription_data or {}
            )

        # Compile results
        result = {
            'status': 'completed',
            'enhancements': {
                'enhanced_transcription': enhanced_transcription,
                'highlights': highlights,
                'summary': summary,
                'markers_and_chapters': markers_and_chapters,
                'editing_suggestions': suggestions
            },
            'success': True,
            'applied_enhancements': []
        }

        # Track which enhancements were successful
        if enhanced_transcription and enhanced_transcription.get('success'):
            result['applied_enhancements'].append('transcription_enhancement')

        if highlights and highlights.get('success'):
            result['applied_enhancements'].append('highlight_extraction')

        if summary and summary.get('success'):
            result['applied_enhancements'].append('summary_generation')

        if markers_and_chapters and markers_and_chapters.get('success'):
            result['applied_enhancements'].append('markers_and_chapters')

        if suggestions and suggestions.get('success'):
            result['applied_enhancements'].append('editing_suggestions')

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'AI enhancement complete'}
        )

        logger.info(f"AI enhancement completed with {len(result['applied_enhancements'])} enhancements")
        return result

    except Exception as e:
        logger.exception("AI enhancement failed")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True, queue='ai', priority=6)
def enhance_transcription_task(self, transcription_text: str, context: str = ""):
    """
    Background task for transcription enhancement only
    """
    try:
        if not Config.OPENAI_API_KEY:
            raise ProcessingError("OpenAI API key not configured")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Enhancing transcription with AI'}
        )

        openai_client = OpenAIClient()
        result = openai_client.enhance_transcription(transcription_text, context)

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Transcription enhancement complete'}
        )

        return {
            'status': 'completed',
            'enhancement_result': result
        }

    except Exception as e:
        logger.exception("Transcription enhancement failed")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True, queue='ai', priority=3)
def generate_content_summary_task(self, transcription_data: dict, max_length: int = 200):
    """
    Background task for content summary generation
    """
    try:
        if not Config.OPENAI_API_KEY:
            raise ProcessingError("OpenAI API key not configured")

        if not transcription_data or not transcription_data.get('transcript'):
            raise ProcessingError("No transcription data provided")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Generating content summary'}
        )

        openai_client = OpenAIClient()
        summary_result = openai_client.generate_summary(
            transcription_data['transcript'],
            max_length
        )

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Summary generation complete'}
        )

        return {
            'status': 'completed',
            'summary': summary_result
        }

    except Exception as e:
        logger.exception("Summary generation failed")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise