# Short-Form Content Generation System

## Overview

The short-form generation system converts long-form audio + DRT timelines into optimized short-form content (15-180 seconds) using AI-powered analysis and speaker diarization.

## Architecture

### Pipeline Flow

```
Input: Audio File + DRT Timeline
   ↓
1. Parse DRT Timeline
   → Extract timeline structure, clips, markers
   ↓
2. Analyze Audio
   → Detect silence segments, speech patterns
   ↓
3. Create 30-Second Chunks
   → Intelligently split at silence/clip boundaries
   → Maintain metadata for each chunk
   ↓
4. Process Each Chunk with Sarvam API
   → Transcription + Speaker Diarization
   → Extract speaker segments with timestamps
   ↓
5. Build Speaker Continuity Map
   → Link speakers across chunks
   → Track conversation flow
   ↓
6. Group into Conversations
   → Cluster speaker utterances
   → Calculate engagement scores
   ↓
7. Apply AI Enhancement (OpenAI)
   → Analyze based on prompt type
   → Score segments for optimal selection
   ↓
8. Create Optimized Timeline
   → Select best segments up to target duration
   → Add speaker markers
   ↓
Output: Optimized DRT File
```

## Core Components

### 1. Timeline Chunker Service (`timeline_chunker.py`)

**Purpose:** Split timeline into 30-second chunks for Sarvam API processing

**Features:**
- Respects clip boundaries (avoids cutting mid-clip)
- Prefers silence segments for natural breaks
- Maintains 1-second overlap for speaker continuity
- Tracks original timeline offsets

**Configuration:**
- Target chunk: 30 seconds (Sarvam real-time API limit)
- Min chunk: 25 seconds
- Overlap: 1 second

**Output:** List of `TimelineChunk` objects with clips and metadata

### 2. Speaker Identifier Service (`speaker_identifier.py`)

**Purpose:** Identify speakers across timeline chunks

**Process:**
1. Extract audio for each chunk
2. Process with Sarvam API (diarization enabled)
3. Parse speaker segments with global timestamps
4. Build speaker continuity map across chunks
5. Generate speaker profiles with statistics

**Output:**
- `SpeakerSegment[]`: Individual speaker utterances
- `SpeakerProfile{}`: Unified speaker data across all chunks

**Key Metrics:**
- Speaker ID, label, total speaking time
- Segment count, chunks appeared
- Conversation flow timeline

### 3. Conversation Merger Service (`conversation_merger.py`)

**Purpose:** Group speaker utterances into cohesive conversations

**Engagement Scoring:**
- **Speaker changes (30%):** More dynamic = higher score
- **Pace (30%):** Words per second (optimal: 3 wps)
- **Duration (20%):** Optimal 15-45 seconds
- **Speaker balance (20%):** Equal speaking time = higher score

**Configuration:**
- Max pause between turns: 3 seconds
- Min conversation duration: 5 seconds
- Topic transition threshold: 5 seconds

**Output:**
- `ConversationSegment[]`: Scored conversation segments
- Optimized `Timeline` with best segments

### 4. Short-Form AI Enhancer (`shortform_ai_enhancer.py`)

**Purpose:** AI-powered optimization based on content type

**Supported Prompt Types:**

| Type | Focus | Cut Priorities | Emphasis |
|------|-------|----------------|----------|
| **Engaging** | Viral hooks, emotional peaks, surprises | Slow moments, repetition | Punchlines, reveals |
| **Informative** | Key insights, data, explanations | Tangents, filler | Statistics, tips |
| **Emotional** | Vulnerability, personal stories | Logic, facts | Emotional peaks |
| **Funny** | Jokes, punchlines, timing | Serious moments | Reactions, callbacks |
| **Tutorial** | Step-by-step, demonstrations | Mistakes, long pauses | Key steps, warnings |
| **Inspirational** | Success stories, transformation | Negativity, doubt | Breakthroughs, CTAs |
| **Controversial** | Bold statements, debate | Hedging, uncertainty | Strong takes, rebuttals |
| **Storytelling** | Narrative arc, tension | Unnecessary details | Plot twists, resolution |

**AI Analysis:**
- Analyzes full transcript with context
- Identifies best segments for prompt type
- Suggests hooks, cuts, text overlays, pacing
- Scores conversations against style goals

### 5. Short-Form Processing Task (`shortform_processing.py`)

**Celery Task:** `process_shortform_content`

**Parameters:**
- `job_id`: Unique job identifier
- `audio_file_path`: Path to audio file
- `drt_file_path`: Path to DRT timeline
- `prompt_type`: Content style (default: "engaging")
- `target_duration`: Target length in seconds (default: 60.0)
- `language_code`: Transcription language (default: "ml-IN")

**Progress Tracking:**
- 0-5%: Starting
- 5-10%: Parse timeline + analyze audio
- 10-15%: Create chunks
- 15-70%: Process chunks (Sarvam API)
- 70-75%: Build conversations
- 75-80%: Apply AI enhancement
- 80-95%: Create & export optimized timeline
- 95-100%: Finalize

## API Endpoint

### `POST /process-shortform/<job_id>`

**Authentication:** Required (JWT token)

**Rate Limit:** 2 requests/minute, 20 requests/hour

**Request Body:**
```json
{
  "prompt_type": "engaging",
  "target_duration": 60.0,
  "language_code": "ml-IN"
}
```

**Validation:**
- `prompt_type`: Must be one of 8 supported types
- `target_duration`: 15-180 seconds
- `language_code`: Valid language code (ml-IN, en-IN, etc.)

**Response (Success):**
```json
{
  "job_id": "abc123",
  "task_id": "shortform_abc123",
  "status": "queued",
  "message": "Short-form content generation submitted to background queue",
  "estimated_time": "10-20 minutes",
  "options": {
    "prompt_type": "engaging",
    "target_duration": 60.0,
    "language_code": "ml-IN"
  }
}
```

**Response (Eager Mode - Immediate):**
```json
{
  "job_id": "abc123",
  "task_id": "shortform_abc123",
  "status": "completed",
  "message": "Short-form content generated successfully",
  "result": {
    "job_id": "abc123",
    "status": "completed",
    "original_duration": 960.5,
    "optimized_duration": 62.3,
    "compression_ratio": 0.065,
    "output_file": "/path/to/abc123_shortform.drt",
    "prompt_type": "engaging",
    "target_duration": 60.0,
    "statistics": {
      "total_chunks": 32,
      "total_speakers": 3,
      "total_conversations": 12,
      "segments_selected": 5,
      "speaker_profiles": [...],
      "conversation_stats": {...},
      "ai_enhancement": {...}
    }
  }
}
```

## Usage Example

### 1. Upload Audio + DRT

```bash
curl -X POST http://localhost:5000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "audio=@hackathon.wav" \
  -F "drt=@hackathon.drt"
```

Response:
```json
{
  "job_id": "abc123",
  "status": "uploaded"
}
```

### 2. Trigger Short-Form Processing

```bash
curl -X POST http://localhost:5000/process-shortform/abc123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_type": "engaging",
    "target_duration": 60.0,
    "language_code": "ml-IN"
  }'
```

### 3. Check Status

```bash
curl http://localhost:5000/status/abc123 \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Download Result

```bash
curl -O http://localhost:5000/download/abc123 \
  -H "Authorization: Bearer $TOKEN"
```

## Benefits

### 1. Bypasses Sarvam 30-Second Limitation
- Uses real-time API (fast, cheap) instead of unavailable Batch API
- Processes long files by chunking intelligently
- Maintains speaker continuity across chunks

### 2. AI-Powered Content Optimization
- 8 prompt types for different content goals
- OpenAI analysis for hooks, pacing, emphasis
- Engagement scoring based on multiple factors

### 3. Conversation-Aware Editing
- Respects natural conversation flow
- Groups related utterances
- Balances speaking time across speakers

### 4. Professional Output
- DRT format ready for DaVinci Resolve
- Speaker markers for easy identification
- Metadata preserved throughout pipeline

## Configuration

### Environment Variables

```bash
# Required for transcription
SARVAM_API_KEY=your_sarvam_api_key

# Required for AI enhancement
OPENAI_API_KEY=your_openai_api_key

# Optional tuning
MAX_FILE_SIZE_MB=500
TARGET_CHUNK_DURATION=30
MIN_CONVERSATION_DURATION=5
```

### Customization

Edit `services/shortform_ai_enhancer.py` to:
- Add new prompt types
- Adjust engagement scoring weights
- Customize AI prompts for different styles

Edit `services/conversation_merger.py` to:
- Change conversation detection thresholds
- Modify engagement scoring algorithm
- Adjust segment selection criteria

## Performance

### Processing Time

For a 16-minute (960s) Malayalam + English conversation:

| Stage | Duration | Notes |
|-------|----------|-------|
| Parse timeline | 1s | Fast XML parsing |
| Audio analysis | 5s | Silence detection |
| Create chunks | 1s | 32 chunks created |
| Process chunks | 8-12min | 32 × 15-20s per chunk |
| Build conversations | 2s | Grouping + scoring |
| AI enhancement | 30s | OpenAI GPT-4 |
| Export DRT | 1s | XML generation |
| **Total** | **10-15min** | Varies by audio duration |

### Cost Estimate

**Sarvam API:**
- Cost: Rs. 30/hour (~$0.36/hour)
- 16min audio ≈ 0.27 hours = Rs. 8 (~$0.10)

**OpenAI API:**
- Model: GPT-4
- Tokens: ~1500-2000
- Cost: ~$0.03-0.06

**Total:** ~$0.13-0.16 per 16-minute video

## Limitations

1. **30-Second Chunk Processing:** Each chunk processed separately (speaker continuity handled algorithmically, not by API)
2. **AI Cost:** OpenAI GPT-4 adds cost (~$0.03-0.06 per video)
3. **Sarvam Languages:** Limited to Sarvam-supported languages (Malayalam, English, Hindi, etc.)
4. **Processing Time:** Longer videos take proportionally longer (30 chunks = ~10-15 min)

## Future Enhancements

1. **Voice Embedding Similarity:** Better speaker matching across chunks using acoustic features
2. **Real-Time Preview:** WebSocket updates with preview snippets during processing
3. **Multi-Video Generation:** Create multiple short-form clips from single long-form content
4. **Custom Prompts:** Allow user-defined AI prompts beyond 8 presets
5. **Speaker Labeling:** Manual speaker identification UI (replace "Speaker 1" with actual names)
6. **Batch Processing:** Process multiple videos in parallel

## Testing

### Unit Tests

```bash
cd backend
pytest tests/test_timeline_chunker.py
pytest tests/test_speaker_identifier.py
pytest tests/test_conversation_merger.py
```

### Integration Test

```bash
# Set API keys
export SARVAM_API_KEY=your_key
export OPENAI_API_KEY=your_key

# Run test with real audio
python -m pytest tests/test_shortform_integration.py -v
```

### Manual Test

```bash
# Start backend
cd backend && python app.py

# Use curl or Postman to test endpoint (see Usage Example above)
```

## Troubleshooting

### Issue: "Missing pydub package"

**Solution:**
```bash
pip install pydub
```

### Issue: "ffmpeg not found"

**Solution (Windows):**
1. Download from https://www.gyan.dev/ffmpeg/builds/
2. Extract and add `bin` folder to PATH
3. Restart terminal

### Issue: "Sarvam API timeout"

**Cause:** Network issues or API rate limiting

**Solution:**
- Check API key validity
- Verify internet connection
- Reduce concurrent requests

### Issue: "OpenAI API error"

**Cause:** Invalid API key or quota exceeded

**Solution:**
- Verify OPENAI_API_KEY in `.env`
- Check OpenAI account billing

### Issue: "Speaker continuity broken"

**Cause:** Overlapping speech or very short utterances

**Solution:**
- Increase `MIN_CONVERSATION_DURATION` in `conversation_merger.py`
- Adjust `MAX_PAUSE_BETWEEN_TURNS` for tighter/looser grouping

## Contact & Support

For questions about the short-form generation system:
1. Check CLAUDE.md for project overview
2. Review this document (SHORTFORM_SYSTEM.md)
3. Contact Sarvam AI for API-related questions
