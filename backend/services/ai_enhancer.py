import logging
from typing import Dict, Any, Optional, List
from models.timeline import Timeline, Track, Clip
from services.openai_client import OpenAIClient
from config import Config

logger = logging.getLogger(__name__)

class AIEnhancementService:
    """
    AI-powered enhancement service that provides intelligent editing suggestions,
    content analysis, and automated improvements using OpenAI
    """

    def __init__(self):
        self.openai_client = OpenAIClient() if Config.OPENAI_API_KEY else None

    def enhance_timeline_processing(self,
                                   timeline: Timeline,
                                   transcription_data: Optional[Dict[str, Any]] = None,
                                   audio_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply AI-powered enhancements to timeline processing
        """
        enhancements = {
            'success': True,
            'applied_enhancements': [],
            'suggestions': [],
            'metadata': {}
        }

        try:
            if not self.openai_client:
                logger.info("OpenAI API not configured, skipping AI enhancements")
                enhancements['success'] = False
                enhancements['error'] = 'OpenAI API not configured'
                return enhancements

            # 1. Enhance transcription quality
            if transcription_data and transcription_data.get('transcript'):
                logger.info("Enhancing transcription with AI")
                enhanced_transcript = self._enhance_transcription(transcription_data)
                if enhanced_transcript['success']:
                    enhancements['enhanced_transcription'] = enhanced_transcript
                    enhancements['applied_enhancements'].append('transcription_enhancement')

            # 2. Generate intelligent highlights
            if transcription_data:
                logger.info("Extracting AI-powered highlights")
                highlights = self._extract_intelligent_highlights(transcription_data, timeline.duration)
                if highlights['success']:
                    enhancements['highlights'] = highlights
                    enhancements['applied_enhancements'].append('highlight_extraction')

            # 3. Generate content summary
            if transcription_data and transcription_data.get('transcript'):
                logger.info("Generating content summary")
                summary = self._generate_content_summary(transcription_data)
                if summary['success']:
                    enhancements['summary'] = summary
                    enhancements['applied_enhancements'].append('content_summary')

            # 4. Create intelligent markers and chapters
            if transcription_data:
                logger.info("Generating intelligent markers")
                markers_data = self._create_intelligent_markers(transcription_data)
                if markers_data['success']:
                    enhancements['markers'] = markers_data
                    enhancements['applied_enhancements'].append('intelligent_markers')
                    # Apply markers to timeline
                    self._apply_markers_to_timeline(timeline, markers_data)

            # 5. Generate editing suggestions
            timeline_stats = timeline.get_timeline_stats()
            editing_suggestions = self._generate_editing_suggestions(timeline_stats, transcription_data)
            if editing_suggestions['success']:
                enhancements['editing_suggestions'] = editing_suggestions
                enhancements['applied_enhancements'].append('editing_suggestions')

            # 6. Analyze content structure and pacing
            structure_analysis = self._analyze_content_structure(timeline, transcription_data)
            if structure_analysis['success']:
                enhancements['structure_analysis'] = structure_analysis
                enhancements['applied_enhancements'].append('structure_analysis')

            return enhancements

        except Exception as e:
            logger.error(f"Error in AI enhancement processing: {str(e)}")
            enhancements['success'] = False
            enhancements['error'] = str(e)
            return enhancements

    def _enhance_transcription(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance transcription quality using AI"""
        try:
            transcript = transcription_data.get('transcript', '')
            if not transcript:
                return {'success': False, 'error': 'No transcript available'}

            # Use context from audio analysis if available
            context = f"Audio content with {len(transcription_data.get('speakers', []))} speakers"

            return self.openai_client.enhance_transcription(transcript, context)

        except Exception as e:
            logger.error(f"Error enhancing transcription: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _extract_intelligent_highlights(self, transcription_data: Dict[str, Any], total_duration: float) -> Dict[str, Any]:
        """Extract intelligent highlights using AI analysis"""
        try:
            # Determine target highlight duration (20-30% of original)
            target_duration = min(total_duration * 0.25, 600)  # Max 10 minutes

            return self.openai_client.extract_highlights(transcription_data, target_duration)

        except Exception as e:
            logger.error(f"Error extracting highlights: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _generate_content_summary(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate content summary using AI"""
        try:
            transcript = transcription_data.get('transcript', '')
            return self.openai_client.generate_summary(transcript)

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_intelligent_markers(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create intelligent markers and chapter breaks"""
        try:
            return self.openai_client.generate_markers_and_chapters(transcription_data)

        except Exception as e:
            logger.error(f"Error creating intelligent markers: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _generate_editing_suggestions(self, timeline_stats: Dict[str, Any], transcription_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate AI-powered editing suggestions"""
        try:
            if not transcription_data:
                return {'success': False, 'error': 'No transcription data available'}

            return self.openai_client.suggest_editing_improvements(timeline_stats, transcription_data)

        except Exception as e:
            logger.error(f"Error generating editing suggestions: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _analyze_content_structure(self, timeline: Timeline, transcription_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze content structure and pacing"""
        try:
            analysis = {
                'success': True,
                'timeline_structure': {
                    'total_clips': sum(len(track.clips) for track in timeline.tracks),
                    'average_clip_duration': 0,
                    'clip_duration_variance': 0,
                    'track_utilization': len(timeline.tracks)
                },
                'content_analysis': {},
                'pacing_recommendations': []
            }

            # Analyze clip durations
            all_clip_durations = []
            for track in timeline.tracks:
                for clip in track.clips:
                    all_clip_durations.append(clip.duration)

            if all_clip_durations:
                import statistics
                analysis['timeline_structure']['average_clip_duration'] = statistics.mean(all_clip_durations)
                if len(all_clip_durations) > 1:
                    analysis['timeline_structure']['clip_duration_variance'] = statistics.variance(all_clip_durations)

            # Analyze speaker distribution if available
            if transcription_data:
                speakers = transcription_data.get('speakers', [])
                segments = transcription_data.get('segments', [])

                analysis['content_analysis'] = {
                    'speaker_count': len(speakers),
                    'segments_count': len(segments),
                    'speaker_balance': self._calculate_speaker_balance(segments),
                    'conversation_dynamics': self._analyze_conversation_dynamics(segments)
                }

            # Generate pacing recommendations
            analysis['pacing_recommendations'] = self._generate_pacing_recommendations(analysis)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing content structure: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _apply_markers_to_timeline(self, timeline: Timeline, markers_data: Dict[str, Any]) -> None:
        """Apply AI-generated markers to the timeline"""
        try:
            # Add chapters as markers
            for chapter in markers_data.get('chapters', []):
                timeline.add_marker(
                    time=chapter['start_time'],
                    name=chapter['title'],
                    color='Blue'
                )

            # Add individual markers
            for marker in markers_data.get('markers', []):
                color = 'Green' if marker.get('type') == 'highlight' else 'Yellow'
                timeline.add_marker(
                    time=marker['time'],
                    name=marker['name'],
                    color=color
                )

            logger.info(f"Applied {len(markers_data.get('chapters', []))} chapters and {len(markers_data.get('markers', []))} markers")

        except Exception as e:
            logger.error(f"Error applying markers to timeline: {str(e)}")

    def _calculate_speaker_balance(self, segments: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate speaking time balance between speakers"""
        try:
            speaker_times = {}
            total_time = 0

            for segment in segments:
                speaker = segment.get('speaker', 'Unknown')
                duration = segment.get('end_time', 0) - segment.get('start_time', 0)

                if speaker not in speaker_times:
                    speaker_times[speaker] = 0

                speaker_times[speaker] += duration
                total_time += duration

            # Convert to percentages
            if total_time > 0:
                return {speaker: time / total_time for speaker, time in speaker_times.items()}
            else:
                return {}

        except Exception as e:
            logger.error(f"Error calculating speaker balance: {str(e)}")
            return {}

    def _analyze_conversation_dynamics(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze conversation dynamics and speaker interactions"""
        try:
            if not segments:
                return {}

            speaker_changes = 0
            current_speaker = None
            avg_segment_length = 0
            total_segments = len(segments)

            for segment in segments:
                speaker = segment.get('speaker')
                if current_speaker is not None and speaker != current_speaker:
                    speaker_changes += 1
                current_speaker = speaker

                duration = segment.get('end_time', 0) - segment.get('start_time', 0)
                avg_segment_length += duration

            avg_segment_length = avg_segment_length / total_segments if total_segments > 0 else 0

            return {
                'speaker_changes': speaker_changes,
                'change_frequency': speaker_changes / total_segments if total_segments > 0 else 0,
                'average_segment_length': avg_segment_length,
                'conversation_style': self._classify_conversation_style(speaker_changes, total_segments, avg_segment_length)
            }

        except Exception as e:
            logger.error(f"Error analyzing conversation dynamics: {str(e)}")
            return {}

    def _classify_conversation_style(self, speaker_changes: int, total_segments: int, avg_segment_length: float) -> str:
        """Classify the conversation style based on dynamics"""
        if total_segments == 0:
            return 'unknown'

        change_ratio = speaker_changes / total_segments

        if change_ratio > 0.7:
            return 'rapid_exchange'  # Back-and-forth conversation
        elif change_ratio > 0.3:
            return 'balanced_discussion'  # Normal conversation flow
        elif avg_segment_length > 30:
            return 'monologue_style'  # Long form speaking
        else:
            return 'presentation_style'  # Structured presentation

    def _generate_pacing_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate pacing recommendations based on analysis"""
        recommendations = []

        try:
            timeline_structure = analysis.get('timeline_structure', {})
            content_analysis = analysis.get('content_analysis', {})

            avg_clip_duration = timeline_structure.get('average_clip_duration', 0)
            clip_variance = timeline_structure.get('clip_duration_variance', 0)

            # Recommendations based on clip analysis
            if avg_clip_duration > 30:
                recommendations.append("Consider shorter clips for better pacing (current average: {:.1f}s)".format(avg_clip_duration))

            if avg_clip_duration < 3:
                recommendations.append("Clips are very short - consider merging some for smoother flow")

            if clip_variance > 100:
                recommendations.append("High variance in clip lengths - consider more consistent pacing")

            # Recommendations based on conversation analysis
            conversation_style = content_analysis.get('conversation_dynamics', {}).get('conversation_style')
            if conversation_style == 'rapid_exchange':
                recommendations.append("Fast-paced conversation detected - ensure important points aren't lost in quick cuts")
            elif conversation_style == 'monologue_style':
                recommendations.append("Long-form content detected - consider adding visual breaks or B-roll")

            # Speaker balance recommendations
            speaker_balance = content_analysis.get('speaker_balance', {})
            if speaker_balance:
                most_dominant = max(speaker_balance.items(), key=lambda x: x[1])
                if most_dominant[1] > 0.8:
                    recommendations.append(f"Speaker '{most_dominant[0]}' dominates {most_dominant[1]*100:.0f}% - consider balancing")

            return recommendations

        except Exception as e:
            logger.error(f"Error generating pacing recommendations: {str(e)}")
            return ['Unable to generate pacing recommendations']

    def get_enhancement_summary(self, enhancements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of applied AI enhancements"""
        try:
            applied = enhancements.get('applied_enhancements', [])
            summary = {
                'total_enhancements': len(applied),
                'enhancement_types': applied,
                'key_insights': [],
                'recommended_actions': []
            }

            # Extract key insights
            if 'highlights' in enhancements:
                highlights = enhancements['highlights']
                summary['key_insights'].append(
                    f"Identified {len(highlights.get('highlights', []))} key segments for highlights reel"
                )

            if 'structure_analysis' in enhancements:
                structure = enhancements['structure_analysis']
                timeline_structure = structure.get('timeline_structure', {})
                summary['key_insights'].append(
                    f"Timeline has {timeline_structure.get('total_clips', 0)} clips with {timeline_structure.get('average_clip_duration', 0):.1f}s average duration"
                )

            if 'editing_suggestions' in enhancements:
                summary['recommended_actions'].extend([
                    'Review AI-generated editing suggestions',
                    'Consider implementing suggested improvements'
                ])

            if 'markers' in enhancements:
                markers = enhancements['markers']
                summary['recommended_actions'].append(
                    f"Utilize {len(markers.get('markers', []))} AI-generated markers for navigation"
                )

            return summary

        except Exception as e:
            logger.error(f"Error generating enhancement summary: {str(e)}")
            return {'error': str(e)}