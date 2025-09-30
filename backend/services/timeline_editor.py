import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from models.timeline import Timeline, Track, Clip
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
from services.soniox_client import SonioxClient
from services.audio_analyzer import AudioAnalyzer
from services.edit_rules import EditRulesEngine
from config import Config

logger = logging.getLogger(__name__)

class TimelineEditingEngine:
    """
    Comprehensive timeline editing engine that coordinates all services
    to transform raw audio and DRT files into optimized timelines
    """

    def __init__(self):
        self.drt_parser = DRTParser()
        self.drt_writer = DRTWriter()
        self.soniox_client = SonioxClient() if Config.SONIOX_API_KEY else None
        self.audio_analyzer = AudioAnalyzer()
        self.edit_engine = EditRulesEngine()

        self.processing_stats = {}

    def process_timeline(self,
                        audio_file_path: str,
                        drt_file_path: str,
                        processing_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main processing pipeline for timeline editing

        Args:
            audio_file_path: Path to audio file
            drt_file_path: Path to DRT timeline file
            processing_options: Options for processing (transcription, silence removal, etc.)

        Returns:
            Dictionary containing processing results and metadata
        """

        if processing_options is None:
            processing_options = self._get_default_options()

        try:
            processing_start = datetime.now()
            logger.info("Starting timeline processing pipeline")

            # Initialize processing stats
            self.processing_stats = {
                'start_time': processing_start,
                'stages': {},
                'errors': [],
                'warnings': []
            }

            # Stage 1: Parse original timeline
            logger.info("Stage 1: Parsing DRT timeline")
            stage_start = datetime.now()

            original_timeline = self.drt_parser.parse_file(drt_file_path)

            self.processing_stats['stages']['drt_parsing'] = {
                'duration': (datetime.now() - stage_start).total_seconds(),
                'success': True,
                'timeline_duration': original_timeline.duration,
                'clips_count': sum(len(track.clips) for track in original_timeline.tracks),
                'tracks_count': len(original_timeline.tracks)
            }

            # Stage 2: Audio analysis
            logger.info("Stage 2: Analyzing audio")
            stage_start = datetime.now()

            audio_analysis_result = self._perform_audio_analysis(
                audio_file_path,
                processing_options
            )

            if not audio_analysis_result['success']:
                raise Exception("Audio analysis failed")

            self.processing_stats['stages']['audio_analysis'] = {
                'duration': (datetime.now() - stage_start).total_seconds(),
                'success': True,
                **audio_analysis_result['stats']
            }

            # Stage 3: Transcription (optional)
            transcription_result = None
            if processing_options.get('enable_transcription', True) and self.soniox_client:
                logger.info("Stage 3: Audio transcription")
                stage_start = datetime.now()

                transcription_result = self._perform_transcription(
                    audio_file_path,
                    processing_options.get('enable_speaker_diarization', True)
                )

                self.processing_stats['stages']['transcription'] = {
                    'duration': (datetime.now() - stage_start).total_seconds(),
                    'success': transcription_result['success'],
                    **transcription_result.get('stats', {})
                }

            # Stage 4: Apply editing rules
            logger.info("Stage 4: Applying editing rules")
            stage_start = datetime.now()

            editing_result = self._apply_editing_rules(
                original_timeline,
                audio_analysis_result['data'],
                transcription_result['data'] if transcription_result and transcription_result['success'] else None,
                processing_options
            )

            if not editing_result['success']:
                raise Exception("Editing rules application failed")

            edited_timeline = editing_result['timeline']

            self.processing_stats['stages']['editing'] = {
                'duration': (datetime.now() - stage_start).total_seconds(),
                'success': True,
                **editing_result['stats']
            }

            # Stage 5: Generate output
            logger.info("Stage 5: Generating output DRT file")
            stage_start = datetime.now()

            output_result = self._generate_output_file(edited_timeline, processing_options)

            if not output_result['success']:
                raise Exception("Output generation failed")

            self.processing_stats['stages']['output_generation'] = {
                'duration': (datetime.now() - stage_start).total_seconds(),
                'success': True,
                'output_file': output_result['file_path']
            }

            # Calculate total processing time
            total_duration = (datetime.now() - processing_start).total_seconds()
            self.processing_stats['total_duration'] = total_duration
            self.processing_stats['overall_success'] = True

            # Generate comprehensive results
            results = self._compile_results(
                original_timeline,
                edited_timeline,
                output_result['file_path'],
                audio_analysis_result,
                transcription_result
            )

            logger.info(f"Timeline processing completed in {total_duration:.2f} seconds")

            return results

        except Exception as e:
            logger.error(f"Timeline processing failed: {str(e)}")
            self.processing_stats['overall_success'] = False
            self.processing_stats['errors'].append(str(e))

            return {
                'success': False,
                'error': str(e),
                'processing_stats': self.processing_stats
            }

    def _get_default_options(self) -> Dict[str, Any]:
        """Get default processing options"""
        return {
            'enable_transcription': bool(Config.SONIOX_API_KEY),
            'enable_speaker_diarization': True,
            'remove_silence': True,
            'split_on_speaker_change': True,
            'min_clip_length': Config.MIN_CLIP_LENGTH_SECONDS,
            'silence_threshold_db': Config.SILENCE_THRESHOLD_DB,
            'energy_based_cutting': True,
            'preserve_markers': True,
            'output_format': 'drt'
        }

    def _perform_audio_analysis(self,
                               audio_file_path: str,
                               options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive audio analysis"""
        try:
            # Load audio
            success = self.audio_analyzer.load_audio(audio_file_path)
            if not success:
                return {
                    'success': False,
                    'error': 'Failed to load audio file'
                }

            # Get basic features
            features = self.audio_analyzer.analyze_audio_features()

            # Detect speech and silence
            silence_segments = []
            speech_segments = []

            if options.get('remove_silence', True):
                silence_segments = self.audio_analyzer.detect_silence(
                    silence_threshold_db=options.get('silence_threshold_db', Config.SILENCE_THRESHOLD_DB)
                )

            speech_segments = self.audio_analyzer.detect_speech_segments()

            # Find optimal cut points
            cut_points = []
            if options.get('energy_based_cutting', True):
                cut_points = self.audio_analyzer.find_optimal_cut_points(
                    min_segment_duration=options.get('min_clip_length', Config.MIN_CLIP_LENGTH_SECONDS)
                )

            # Get processing recommendations
            recommendations = self.audio_analyzer._get_processing_recommendations()

            analysis_data = {
                'features': features,
                'silence_segments': silence_segments,
                'speech_segments': speech_segments,
                'cut_points': cut_points,
                'recommendations': recommendations,
                'audio_duration': self.audio_analyzer.duration,
                'sample_rate': self.audio_analyzer.sample_rate
            }

            stats = {
                'audio_duration': self.audio_analyzer.duration,
                'silence_segments_count': len(silence_segments),
                'speech_segments_count': len(speech_segments),
                'cut_points_count': len(cut_points),
                'dynamic_range_db': features.get('dynamic_range_db', 0),
                'avg_db': features.get('avg_db', 0)
            }

            return {
                'success': True,
                'data': analysis_data,
                'stats': stats
            }

        except Exception as e:
            logger.error(f"Audio analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _perform_transcription(self,
                              audio_file_path: str,
                              enable_speaker_diarization: bool) -> Dict[str, Any]:
        """Perform audio transcription with speaker diarization"""
        try:
            if not self.soniox_client:
                return {
                    'success': False,
                    'error': 'Soniox API not configured'
                }

            transcription_data = self.soniox_client.transcribe_audio(
                audio_file_path,
                enable_speaker_diarization
            )

            # Get additional analysis from transcription
            speaker_segments = self.soniox_client.get_speaker_segments(transcription_data)
            silence_hints = self.soniox_client.get_silence_detection_hints(transcription_data)

            stats = {
                'transcript_length': len(transcription_data.get('transcript', '')),
                'word_count': transcription_data.get('word_count', 0),
                'speakers_count': len(transcription_data.get('speakers', [])),
                'segments_count': len(transcription_data.get('segments', [])),
                'confidence_avg': transcription_data.get('confidence', 0.0),
                'transcription_duration': transcription_data.get('duration', 0.0)
            }

            return {
                'success': True,
                'data': {
                    'transcription': transcription_data,
                    'speaker_segments': speaker_segments,
                    'silence_hints': silence_hints
                },
                'stats': stats
            }

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            self.processing_stats['warnings'].append(f"Transcription failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _apply_editing_rules(self,
                            original_timeline: Timeline,
                            audio_analysis: Dict[str, Any],
                            transcription_data: Optional[Dict[str, Any]],
                            options: Dict[str, Any]) -> Dict[str, Any]:
        """Apply editing rules to create optimized timeline"""
        try:
            # Configure edit engine based on options
            for rule_name, value in options.items():
                if rule_name in ['min_clip_length', 'silence_threshold_db', 'remove_silence',
                               'split_on_speaker_change', 'merge_short_clips', 'energy_based_cutting']:
                    self.edit_engine.set_rule(rule_name, value)

            # Apply editing rules
            edited_timeline = self.edit_engine.apply_editing_rules(
                original_timeline,
                transcription_data,
                audio_analysis
            )

            # Get editing statistics
            editing_stats = self.edit_engine.get_editing_stats(original_timeline, edited_timeline)

            return {
                'success': True,
                'timeline': edited_timeline,
                'stats': editing_stats
            }

        except Exception as e:
            logger.error(f"Editing rules application failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_output_file(self,
                             timeline: Timeline,
                             options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate output DRT file"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"edited_timeline_{timestamp}.drt"
            output_path = os.path.join(Config.TEMP_FOLDER, filename)

            # Write timeline to file
            success = self.drt_writer.write_timeline(timeline, output_path)

            if not success:
                return {
                    'success': False,
                    'error': 'Failed to write DRT file'
                }

            # Verify file was created and get size
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                return {
                    'success': True,
                    'file_path': output_path,
                    'file_size': file_size,
                    'filename': filename
                }
            else:
                return {
                    'success': False,
                    'error': 'Output file was not created'
                }

        except Exception as e:
            logger.error(f"Output generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _compile_results(self,
                        original_timeline: Timeline,
                        edited_timeline: Timeline,
                        output_file_path: str,
                        audio_analysis: Dict[str, Any],
                        transcription_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Compile comprehensive processing results"""

        # Calculate compression metrics
        duration_reduction = original_timeline.duration - edited_timeline.duration
        compression_ratio = edited_timeline.duration / original_timeline.duration if original_timeline.duration > 0 else 1.0

        # Compile timeline comparison
        timeline_comparison = {
            'original': {
                'duration': original_timeline.duration,
                'tracks': len(original_timeline.tracks),
                'clips': sum(len(track.clips) for track in original_timeline.tracks),
                'markers': len(original_timeline.markers)
            },
            'edited': {
                'duration': edited_timeline.duration,
                'tracks': len(edited_timeline.tracks),
                'clips': sum(len(track.clips) for track in edited_timeline.tracks),
                'markers': len(edited_timeline.markers)
            },
            'reduction': {
                'duration_seconds': duration_reduction,
                'duration_percentage': ((duration_reduction / original_timeline.duration) * 100) if original_timeline.duration > 0 else 0,
                'compression_ratio': compression_ratio
            }
        }

        # Compile processing insights
        insights = {
            'audio_quality': {
                'dynamic_range': audio_analysis['data']['features'].get('dynamic_range_db', 0),
                'average_volume': audio_analysis['data']['features'].get('avg_db', 0),
                'speech_to_silence_ratio': len(audio_analysis['data']['speech_segments']) / max(len(audio_analysis['data']['silence_segments']), 1)
            },
            'editing_effectiveness': {
                'silence_removed_count': len(audio_analysis['data']['silence_segments']),
                'cuts_applied': len(audio_analysis['data']['cut_points']),
                'clips_created': timeline_comparison['edited']['clips'],
                'time_saved_minutes': duration_reduction / 60
            }
        }

        # Add transcription insights if available
        if transcription_result and transcription_result['success']:
            insights['transcription'] = {
                'speakers_detected': transcription_result['stats']['speakers_count'],
                'words_transcribed': transcription_result['stats']['word_count'],
                'confidence_score': transcription_result['stats']['confidence_avg'],
                'speaker_changes': len([s for s in transcription_result['data']['speaker_segments']])
            }

        return {
            'success': True,
            'output_file': output_file_path,
            'timeline_comparison': timeline_comparison,
            'insights': insights,
            'processing_stats': self.processing_stats,
            'metadata': {
                'processing_date': self.processing_stats['start_time'].isoformat(),
                'total_processing_time': self.processing_stats['total_duration'],
                'stages_completed': len([s for s in self.processing_stats['stages'].values() if s.get('success', False)]),
                'transcription_used': transcription_result is not None and transcription_result.get('success', False),
                'version': '1.0.0'
            }
        }

    def get_processing_preview(self,
                              audio_file_path: str,
                              drt_file_path: str) -> Dict[str, Any]:
        """Get a preview of what processing would do without actually processing"""
        try:
            # Parse timeline
            timeline = self.drt_parser.parse_file(drt_file_path)
            timeline_stats = timeline.get_timeline_stats()

            # Basic audio analysis
            self.audio_analyzer.load_audio(audio_file_path)
            audio_summary = self.audio_analyzer.get_audio_summary()

            # Estimate processing impact
            estimated_cuts = len(audio_summary.get('silence_segments', []))
            estimated_duration_reduction = sum(
                seg.get('duration', 0) for seg in audio_summary.get('silence_segments', [])
            )

            return {
                'success': True,
                'preview': {
                    'original_timeline': timeline_stats,
                    'audio_analysis': audio_summary,
                    'estimated_changes': {
                        'silence_segments_to_remove': estimated_cuts,
                        'estimated_duration_reduction_seconds': estimated_duration_reduction,
                        'estimated_compression_ratio': (timeline_stats['total_duration'] - estimated_duration_reduction) / timeline_stats['total_duration'] if timeline_stats['total_duration'] > 0 else 1.0
                    }
                }
            }

        except Exception as e:
            logger.error(f"Preview generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }