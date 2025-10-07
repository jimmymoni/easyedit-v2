"""
Short-Form AI Enhancement Service
Uses OpenAI to optimize short-form content based on prompt type
- Engaging: viral hooks, punchlines, emotional peaks
- Informative: key insights, educational moments, clear explanations
- Emotional: heartfelt moments, vulnerability, connection
- Funny: jokes, punchlines, comedic timing
- Tutorial: step-by-step, clear instructions, demonstrations
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

from services.conversation_merger import ConversationSegment
from services.openai_client import OpenAIClient
from config import Config

logger = logging.getLogger(__name__)


class PromptType(str, Enum):
    """Short-form content types"""
    ENGAGING = "engaging"
    INFORMATIVE = "informative"
    EMOTIONAL = "emotional"
    FUNNY = "funny"
    TUTORIAL = "tutorial"
    INSPIRATIONAL = "inspirational"
    CONTROVERSIAL = "controversial"
    STORYTELLING = "storytelling"


@dataclass
class EnhancementSuggestion:
    """AI suggestion for content enhancement"""
    suggestion_type: str  # "hook", "cut", "emphasis", "reorder", "text_overlay"
    timestamp: float
    description: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShortFormAIEnhancer:
    """AI-powered enhancement for short-form content"""

    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        """
        Initialize AI enhancer

        Args:
            openai_client: OpenAI client (creates new if None)
        """
        self.openai_client = openai_client or OpenAIClient()

        # Prompt templates for different content types
        self.prompt_templates = {
            PromptType.ENGAGING: {
                'focus': ['viral hooks', 'emotional peaks', 'surprising moments', 'pattern interrupts'],
                'cut_priorities': ['slow moments', 'repetition', 'dead air'],
                'emphasis': ['punchlines', 'reveals', 'reactions']
            },
            PromptType.INFORMATIVE: {
                'focus': ['key insights', 'data points', 'explanations', 'examples'],
                'cut_priorities': ['tangents', 'filler', 'redundancy'],
                'emphasis': ['statistics', 'actionable tips', 'important facts']
            },
            PromptType.EMOTIONAL: {
                'focus': ['vulnerable moments', 'personal stories', 'authentic reactions', 'heartfelt'],
                'cut_priorities': ['logical explanations', 'facts', 'dry content'],
                'emphasis': ['emotional peaks', 'connection moments', 'vulnerability']
            },
            PromptType.FUNNY: {
                'focus': ['jokes', 'punchlines', 'comedic timing', 'funny reactions'],
                'cut_priorities': ['serious moments', 'exposition', 'setup (keep minimal)'],
                'emphasis': ['punchlines', 'reactions', 'callbacks']
            },
            PromptType.TUTORIAL: {
                'focus': ['step-by-step', 'demonstrations', 'clear instructions', 'results'],
                'cut_priorities': ['unrelated content', 'mistakes (unless valuable)', 'long pauses'],
                'emphasis': ['key steps', 'important tips', 'warnings', 'results']
            },
            PromptType.INSPIRATIONAL: {
                'focus': ['motivational', 'success stories', 'transformation', 'hope'],
                'cut_priorities': ['negativity', 'doubt', 'obstacles (unless overcome)'],
                'emphasis': ['peak moments', 'breakthroughs', 'calls to action']
            },
            PromptType.CONTROVERSIAL: {
                'focus': ['bold statements', 'counterarguments', 'strong opinions', 'debate'],
                'cut_priorities': ['hedging', 'uncertainty', 'waffling'],
                'emphasis': ['strong takes', 'evidence', 'rebuttals']
            },
            PromptType.STORYTELLING: {
                'focus': ['narrative arc', 'tension', 'resolution', 'character development'],
                'cut_priorities': ['unnecessary details', 'tangents', 'slow pacing'],
                'emphasis': ['plot points', 'twists', 'emotional beats', 'resolution']
            }
        }

    def enhance_conversations(
        self,
        conversations: List[ConversationSegment],
        prompt_type: PromptType = PromptType.ENGAGING,
        target_duration: float = 60.0
    ) -> Dict[str, Any]:
        """
        Analyze conversations and provide AI-powered enhancement suggestions

        Args:
            conversations: List of conversation segments
            prompt_type: Type of content to optimize for
            target_duration: Target duration for final output

        Returns:
            Dictionary with enhancement suggestions
        """
        logger.info(f"Enhancing {len(conversations)} conversations for {prompt_type.value} content...")

        if not conversations:
            return {'error': 'No conversations to enhance'}

        # Get prompt template
        template = self.prompt_templates.get(prompt_type, self.prompt_templates[PromptType.ENGAGING])

        # Build transcript for AI analysis
        full_transcript = self._build_transcript(conversations)

        # Get AI recommendations
        try:
            recommendations = self._get_ai_recommendations(
                full_transcript,
                prompt_type,
                template,
                target_duration
            )
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            recommendations = self._fallback_recommendations(conversations, prompt_type)

        # Analyze conversation engagement against prompt type
        scored_conversations = self._score_conversations_by_prompt(
            conversations,
            prompt_type,
            recommendations
        )

        return {
            'prompt_type': prompt_type.value,
            'total_conversations': len(conversations),
            'scored_conversations': scored_conversations,
            'ai_recommendations': recommendations,
            'template_used': template
        }

    def _build_transcript(self, conversations: List[ConversationSegment]) -> str:
        """Build full transcript from conversations"""
        transcript_parts = []

        for conv in conversations:
            conv_text = f"\n[{conv.start_time:.1f}s - {conv.end_time:.1f}s] ({conv.topic or 'Conversation'})\n"

            for utterance in conv.utterances:
                speaker_label = utterance.speaker_label or utterance.speaker_id
                conv_text += f"  [{utterance.start_time:.1f}s] {speaker_label}: {utterance.text}\n"

            transcript_parts.append(conv_text)

        return "\n".join(transcript_parts)

    def _get_ai_recommendations(
        self,
        transcript: str,
        prompt_type: PromptType,
        template: Dict[str, Any],
        target_duration: float
    ) -> Dict[str, Any]:
        """Get AI recommendations from OpenAI"""

        prompt = f"""You are an expert video editor specializing in short-form content for social media.

Analyze this transcript and provide recommendations for creating {prompt_type.value} content:

TRANSCRIPT:
{transcript}

TARGET: {target_duration} seconds of {prompt_type.value} content

OPTIMIZATION GOALS:
- Focus on: {', '.join(template['focus'])}
- Cut out: {', '.join(template['cut_priorities'])}
- Emphasize: {', '.join(template['emphasis'])}

Provide:
1. Top 3-5 segments that best fit the {prompt_type.value} style (with timestamps)
2. Suggested hook for first 3 seconds
3. Optimal cuts and transitions
4. Text overlay suggestions
5. Pacing recommendations

Format your response as JSON with keys: "best_segments", "hook", "cuts", "text_overlays", "pacing"
"""

        try:
            response = self.openai_client.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert video editor for short-form content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            content = response.choices[0].message.content

            # Try to parse JSON response
            import json
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Fallback: return as text
                return {'recommendations': content}

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    def _fallback_recommendations(
        self,
        conversations: List[ConversationSegment],
        prompt_type: PromptType
    ) -> Dict[str, Any]:
        """Fallback recommendations if AI fails"""
        logger.warning("Using fallback recommendations (AI unavailable)")

        # Simple heuristic-based recommendations
        sorted_convs = sorted(conversations, key=lambda c: c.engagement_score, reverse=True)

        return {
            'best_segments': [
                {
                    'start_time': conv.start_time,
                    'end_time': conv.end_time,
                    'reason': f'High engagement score ({conv.engagement_score:.2f})'
                }
                for conv in sorted_convs[:3]
            ],
            'hook': 'Use highest engagement segment as hook',
            'cuts': 'Remove segments with engagement score < 0.5',
            'text_overlays': 'Add text at speaker changes',
            'pacing': 'Maintain fast pace with minimal pauses'
        }

    def _score_conversations_by_prompt(
        self,
        conversations: List[ConversationSegment],
        prompt_type: PromptType,
        ai_recommendations: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Score conversations based on how well they fit the prompt type"""

        scored = []

        for conv in conversations:
            # Base score is engagement
            score = conv.engagement_score

            # Adjust based on prompt type
            if prompt_type == PromptType.ENGAGING:
                # Prefer shorter, punchier segments
                if 10 <= conv.duration <= 30:
                    score += 0.2
            elif prompt_type == PromptType.INFORMATIVE:
                # Prefer longer, more detailed segments
                if 30 <= conv.duration <= 60:
                    score += 0.2
            elif prompt_type == PromptType.FUNNY:
                # Prefer segments with many speaker changes (setup-punchline)
                changes = conv.metadata.get('speaker_changes', 0)
                if changes >= 3:
                    score += 0.3
            elif prompt_type == PromptType.EMOTIONAL:
                # Prefer single-speaker monologues
                if len(conv.speakers) == 1 and conv.duration >= 15:
                    score += 0.3

            # Check if AI recommended this segment
            ai_recommended = False
            for seg in ai_recommendations.get('best_segments', []):
                if isinstance(seg, dict):
                    if abs(seg.get('start_time', -999) - conv.start_time) < 1.0:
                        ai_recommended = True
                        score += 0.3
                        break

            scored.append({
                'conversation': conv.to_dict(),
                'final_score': min(score, 1.0),  # Cap at 1.0
                'ai_recommended': ai_recommended
            })

        # Sort by final score
        scored.sort(key=lambda x: x['final_score'], reverse=True)

        return scored

    def generate_hook_suggestions(
        self,
        top_segment: ConversationSegment
    ) -> List[str]:
        """Generate hook suggestions for first 3 seconds"""

        hooks = []

        # Find first impactful utterance
        for utterance in top_segment.utterances[:3]:
            text = utterance.text.strip()
            if len(text) > 10:  # Meaningful content
                hooks.append(text[:100])  # First 100 chars

        return hooks[:3]  # Top 3 suggestions


# Utility function
def enhance_for_shortform(
    conversations: List[ConversationSegment],
    prompt_type: str = "engaging",
    target_duration: float = 60.0
) -> Dict[str, Any]:
    """
    Convenience function to enhance conversations for short-form content

    Args:
        conversations: List of conversation segments
        prompt_type: Type of content ("engaging", "informative", etc.)
        target_duration: Target duration in seconds

    Returns:
        Enhancement recommendations dictionary
    """
    # Convert string to enum
    try:
        prompt_enum = PromptType(prompt_type.lower())
    except ValueError:
        logger.warning(f"Invalid prompt type '{prompt_type}', using 'engaging'")
        prompt_enum = PromptType.ENGAGING

    enhancer = ShortFormAIEnhancer()
    return enhancer.enhance_conversations(conversations, prompt_enum, target_duration)
