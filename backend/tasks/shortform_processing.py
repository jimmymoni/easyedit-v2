"""
Short-Form Content Processing Tasks
Celery tasks for generating short-form content from long-form audio + DRT
"""

import logging
import os
import tempfile
from typing import Dict, Any, Optional

from celery_app import celery_app
from job_manager import job_manager
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
from services.timeline_chunker import TimelineChunkerService
from services.speaker_identifier import SpeakerIdentifierService
from services.conversation_merger import ConversationMergerService
from services.shortform_ai_enhancer import ShortFormAIEnhancer, PromptType
from services.simple_audio_analyzer import SimpleAudioAnalyzer
from config import Config

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='tasks.shortform_processing.process_shortform_content')
def process_shortform_content(
    self,
    job_id: str,
    audio_file_path: str,
    drt_file_path: str,
    prompt_type: str = "engaging",
    target_duration: float = 60.0,
    language_code: str = "ml-IN"
) -> Dict[str, Any]:
    """
    Process long-form content into short-form clips

    Args:
        job_id: Job identifier
        audio_file_path: Path to audio file
        drt_file_path: Path to DRT timeline file
        prompt_type: Content type (engaging, informative, emotional, etc.)
        target_duration: Target duration for short-form output (seconds)
        language_code: Language for transcription

    Returns:
        Processing result dictionary
    """
    try:
        # Update job status
        job_manager.update_job_status(
            job_id,
            'processing',
            progress=0,
            message='Starting short-form content generation...'
        )

        # STEP 1: Parse DRT timeline (5%)
        logger.info(f"[{job_id}] Parsing DRT timeline...")
        job_manager.update_job_status(job_id, 'processing', progress=5, message='Parsing timeline...')

        drt_parser = DRTParser()
        timeline = drt_parser.parse_file(drt_file_path)

        if not timeline:
            raise ValueError("Failed to parse DRT file")

        logger.info(f"[{job_id}] Timeline parsed: {timeline.duration:.2f}s, {len(timeline.tracks)} tracks")

        # STEP 2: Analyze audio for silence segments (10%)
        logger.info(f"[{job_id}] Analyzing audio...")
        job_manager.update_job_status(job_id, 'processing', progress=10, message='Analyzing audio...')

        audio_analyzer = SimpleAudioAnalyzer()
        audio_analyzer.load_audio(audio_file_path)
        silence_segments = audio_analyzer.detect_silence(min_silence_duration=0.5)

        logger.info(f"[{job_id}] Found {len(silence_segments)} silence segments")

        # STEP 3: Create timeline chunks (15%)
        logger.info(f"[{job_id}] Chunking timeline into 30-second segments...")
        job_manager.update_job_status(job_id, 'processing', progress=15, message='Creating chunks...')

        chunker = TimelineChunkerService(timeline, audio_file_path)
        chunks = chunker.create_chunks(
            silence_segments=silence_segments,
            respect_clip_boundaries=True
        )

        logger.info(f"[{job_id}] Created {len(chunks)} chunks")

        # STEP 4: Process chunks for speaker identification (20-70%)
        logger.info(f"[{job_id}] Processing chunks for speaker identification...")
        job_manager.update_job_status(
            job_id, 'processing', progress=20,
            message=f'Processing {len(chunks)} chunks with Sarvam API...'
        )

        identifier = SpeakerIdentifierService(audio_file_path, language_code)

        # Process chunks with progress updates
        progress_per_chunk = 50 / len(chunks) if chunks else 0

        speaker_segments, speaker_profiles = identifier.process_chunks(chunks)

        # Update progress after all chunks processed
        job_manager.update_job_status(
            job_id, 'processing', progress=70,
            message=f'Identified {len(speaker_profiles)} speakers...'
        )

        logger.info(
            f"[{job_id}] Speaker identification complete: "
            f"{len(speaker_profiles)} speakers, {len(speaker_segments)} segments"
        )

        # STEP 5: Build conversation segments (75%)
        logger.info(f"[{job_id}] Building conversation segments...")
        job_manager.update_job_status(
            job_id, 'processing', progress=75,
            message='Analyzing conversations...'
        )

        merger = ConversationMergerService(speaker_segments, speaker_profiles, timeline)
        conversations = merger.create_conversation_segments()

        logger.info(f"[{job_id}] Created {len(conversations)} conversation segments")

        # STEP 6: Apply AI enhancement (80%)
        logger.info(f"[{job_id}] Applying AI enhancement for '{prompt_type}' content...")
        job_manager.update_job_status(
            job_id, 'processing', progress=80,
            message=f'Optimizing for {prompt_type} content...'
        )

        # Convert prompt_type string to enum
        try:
            prompt_enum = PromptType(prompt_type.lower())
        except ValueError:
            logger.warning(f"Invalid prompt type '{prompt_type}', using 'engaging'")
            prompt_enum = PromptType.ENGAGING

        enhancer = ShortFormAIEnhancer()
        enhancement_result = enhancer.enhance_conversations(
            conversations,
            prompt_enum,
            target_duration
        )

        logger.info(f"[{job_id}] AI enhancement complete")

        # STEP 7: Create optimized timeline (90%)
        logger.info(f"[{job_id}] Creating optimized timeline...")
        job_manager.update_job_status(
            job_id, 'processing', progress=90,
            message='Building optimized timeline...'
        )

        # Get top segments for target duration
        top_n_segments = min(len(conversations), 5)
        optimized_timeline = merger.create_optimized_timeline(
            top_n_segments=top_n_segments,
            target_duration=target_duration
        )

        logger.info(
            f"[{job_id}] Optimized timeline created: "
            f"{optimized_timeline.duration:.2f}s from {timeline.duration:.2f}s original"
        )

        # STEP 8: Export DRT file (95%)
        logger.info(f"[{job_id}] Exporting optimized DRT...")
        job_manager.update_job_status(
            job_id, 'processing', progress=95,
            message='Exporting DRT file...'
        )

        # Create output directory
        output_dir = os.path.join(Config.UPLOAD_FOLDER, job_id)
        os.makedirs(output_dir, exist_ok=True)

        output_drt_path = os.path.join(output_dir, f"{job_id}_shortform.drt")

        drt_writer = DRTWriter()
        success = drt_writer.write_timeline(optimized_timeline, output_drt_path)

        if not success:
            raise ValueError("Failed to write DRT file")

        logger.info(f"[{job_id}] DRT exported: {output_drt_path}")

        # STEP 9: Prepare result (100%)
        result = {
            'job_id': job_id,
            'status': 'completed',
            'original_duration': timeline.duration,
            'optimized_duration': optimized_timeline.duration,
            'compression_ratio': optimized_timeline.duration / timeline.duration,
            'output_file': output_drt_path,
            'prompt_type': prompt_type,
            'target_duration': target_duration,
            'statistics': {
                'total_chunks': len(chunks),
                'total_speakers': len(speaker_profiles),
                'total_conversations': len(conversations),
                'segments_selected': top_n_segments,
                'speaker_profiles': [p.to_dict() for p in speaker_profiles.values()],
                'conversation_stats': merger.get_merger_statistics(),
                'ai_enhancement': enhancement_result
            }
        }

        # Update job with success
        job_manager.update_job_status(
            job_id, 'completed', progress=100,
            message='Short-form content generated successfully!',
            result=result
        )

        logger.info(f"[{job_id}] Short-form processing completed successfully")
        return result

    except Exception as e:
        logger.error(f"[{job_id}] Short-form processing failed: {e}", exc_info=True)

        # Update job with failure
        job_manager.update_job_status(
            job_id, 'failed', progress=0,
            message=f'Processing failed: {str(e)}'
        )

        return {
            'job_id': job_id,
            'status': 'failed',
            'error': str(e)
        }

    finally:
        # Cleanup audio analyzer
        if 'audio_analyzer' in locals():
            try:
                audio_analyzer.cleanup()
            except Exception as e:
                logger.warning(f"[{job_id}] Cleanup warning: {e}")
