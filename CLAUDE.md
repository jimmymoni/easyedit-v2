# CLAUDE.md

## Project Overview

**EasyEdit** is a cloud-based video editor for YouTube creators that automates repetitive editing tasks.

### Problem
- Recording 18-min videos (~3GB) requires multiple takes
- Manually finding and removing repeated lines takes hours
- Adding motion graphics is tedious
- Green screen background replacement is time-consuming

### Solution
1. Upload raw video (up to 3GB)
2. AI transcribes and detects repeated takes (keep last = best)
3. User adds motion graphics via AI generation
4. Optional background removal
5. Export ZIP with DaVinci Resolve XML + all assets

---

## Tech Stack

### Backend (Flask + Python 3.13)
- **Storage**: AWS S3 (chunked upload, 10MB chunks)
- **Transcription**: Replicate Whisper (transcription + speaker diarization)
- **Image Generation**: Replicate Nano Banana Pro (google/nano-banana-pro)
- **Video Generation**: Replicate Hailuo AI (minimax/hailuo-02)
- **Segmentation**: Replicate Meta SAM-2 (meta/sam-2) - for background removal
- **Export**: FCP7 XML for DaVinci Resolve
- **Background Tasks**: Threading (no Celery/Redis)
- **Data**: In-memory + file-based JSON (no database)

### Frontend (React 18 + TypeScript)
- **Build**: Vite
- **Upload**: S3 chunked upload (direct to S3 via pre-signed URLs)
- **Timeline**: Zustand store
- **Waveform**: WaveSurfer.js
- **Styling**: Tailwind CSS + shadcn/ui

---

## User Workflow

```
PHASE 1: UPLOAD
├── User selects video file (up to 3GB)
├── Frontend calls POST /upload/init
├── Backend generates pre-signed S3 URLs (10MB chunks)
├── Frontend uploads chunks directly to S3 (5 parallel)
├── Frontend calls POST /upload/chunk-complete for each chunk
├── Frontend calls POST /upload/complete when done
└── Video stored in S3

PHASE 2: TRANSCRIBE
├── Backend extracts audio
├── Replicate Whisper generates transcript
└── Returns timestamped text with speaker info

PHASE 3: REPEATED TAKE REMOVAL
├── Algorithm groups similar sentences (80%+ match)
├── For each group, marks all but LAST for removal
├── User reviews detected repeats in UI
├── User approves or adjusts cuts
└── Timeline updated with cuts

PHASE 4: MOTION GRAPHICS (Per Segment)
├── Transcript displayed as segment boxes
├── User clicks segment needing graphics
├── User uploads style reference image
├── User clicks "Generate Start Frame" → Nano Banana Pro
├── User clicks "Generate End Frame" → Nano Banana Pro
├── User clicks "Create Animation" → Hailuo AI (start + end → video)
├── Preview plays in UI
├── User clicks Approve or Regenerate
└── Approved animation added to timeline

PHASE 5: BACKGROUND REMOVAL (Optional)
├── User clicks "Remove Background" tab
├── Meta SAM-2 segments person from background
├── User selects replacement background
└── Composited video added to timeline

PHASE 6: EXPORT
├── User clicks "Export"
├── Backend generates:
│   ├── timeline.xml (FCP7 format for DaVinci Resolve)
│   └── assets/
│       ├── animation_segment_01.mp4
│       ├── animation_segment_02.mp4
│       └── bg_removed.mp4 (if applicable)
├── Backend zips everything
└── User downloads ZIP, imports to DaVinci Resolve
```

---

## Development Commands

### Environment Setup

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Unix/Mac)
source venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Environment Variables

Create a `.env` file in `backend/` directory (NOT root):

```bash
# AWS S3 Credentials (REQUIRED)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_VIDEO_BUCKET=easyedit-videos

# AI API Keys (REQUIRED)
REPLICATE_API_TOKEN=your_replicate_token_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional Configuration
MAX_FILE_SIZE_MB=5120  # 5GB max
S3_CHUNK_SIZE_MB=10
S3_PRESIGNED_URL_EXPIRATION=86400  # 24 hours
LOG_LEVEL=INFO
```

**CRITICAL**: Always edit `backend/.env` (not root `.env`) for backend configuration!

### Running the Application

#### Development Mode

```bash
# Terminal 1 - Backend
cd backend
python app.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Backend runs on: `http://localhost:5000`
Frontend runs on: `http://localhost:5173`

---

## API Endpoints

### S3 Chunked Upload (5 endpoints)

- **POST /upload/init** - Initialize chunked upload
  - Generates pre-signed S3 URLs (10MB chunks)
  - Creates VideoJob + VideoUploadSession
  - Returns `{job_id, chunk_urls[]}`

- **POST /upload/chunk-complete** - Mark chunk uploaded
  - Tracks progress (e.g., 150/300 = 50%)
  - Stores ETag for each chunk

- **POST /upload/complete** - Finalize upload
  - Tells S3 to combine all chunks
  - Triggers background transcoding
  - Returns 202 Accepted

- **POST /upload/resume** - Get resume info
  - Returns completed_chunks + missing_chunks
  - Allows client to resume interrupted uploads

- **POST /upload/abort** - Cancel upload
  - Aborts S3 multipart upload
  - Cleans up temporary data

### Video Processing

- **POST /analyze-video/<job_id>** - Start video analysis
  - Audio extraction
  - Whisper transcription
  - Repeated take detection
- **GET /video-analysis/<job_id>** - Get analysis results
- **GET /video-status/<job_id>** - Get job status + proxy status
- **GET /waveform/<job_id>** - Get waveform data for timeline

### Repeated Take Removal

- **POST /apply-repeated-take-removal/<job_id>** - Apply repeated take detection
  - Returns segments to keep/remove
  - Updates timeline

### Motion Graphics (NEW - to be implemented)

- **POST /generate-start-frame/<job_id>/<segment_id>** - Generate start frame (Nano Banana Pro)
- **POST /generate-end-frame/<job_id>/<segment_id>** - Generate end frame (Nano Banana Pro)
- **POST /generate-animation/<job_id>/<segment_id>** - Create animation (Hailuo AI)
- **POST /approve-animation/<job_id>/<segment_id>** - Approve generated animation

### Background Removal (NEW - to be implemented)

- **POST /remove-background/<job_id>** - Remove background using Meta SAM-2

### Export

- **GET /export-project/<job_id>** - Export ZIP with timeline.xml + assets
- **GET /download-video/<job_id>** - Download processed video
- **GET /download-video-xml/<job_id>** - Download DaVinci Resolve XML only

### Authentication

- **GET /auth/demo-token** - Get demo JWT token (development only)

All endpoints (except `/auth/demo-token`) require JWT authentication:
```bash
Authorization: Bearer <your_jwt_token>
```

---

## Project Structure

### Backend (`backend/`)

```
backend/
├── app.py                              # Main Flask application
├── config.py                           # Configuration with S3 settings
├── models/
│   ├── video_job.py                    # Job tracking model
│   ├── video_upload_session.py         # Upload session tracking
│   └── timeline.py                     # Timeline data structure
├── services/
│   ├── s3_upload_manager.py            # S3 multipart upload ✅
│   ├── replicate_whisper_client.py     # Whisper transcription ✅
│   ├── repeated_take_detector.py       # Duplicate detection ✅
│   ├── motion_graphics_generator.py    # NEW - AI graphics generation
│   ├── background_remover.py           # NEW - Meta SAM-2 integration
│   └── video_background_processor.py   # Background transcoding
├── parsers/
│   └── xml_writer.py                   # DaVinci Resolve XML writer ✅
└── requirements.txt                    # Python dependencies
```

### Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── App.tsx                         # Main React application
│   ├── components/
│   │   └── video/
│   │       ├── VideoUploadZone.tsx        # S3 chunked upload
│   │       ├── VideoTimelineEditor.tsx    # Timeline editing
│   │       ├── WaveformViewer.tsx         # Audio waveform
│   │       ├── MotionGraphicsPanel.tsx    # NEW - AI graphics UI
│   │       └── VideoPlayer.tsx            # Video playback
│   ├── services/
│   │   └── api.ts                      # API client with axios
│   ├── types/
│   │   └── index.ts                    # TypeScript type definitions
│   └── pages/
│       └── VideoEditorPage.tsx         # Main editor page
├── package.json                        # Node.js dependencies
└── vite.config.ts                      # Vite configuration
```

---

## Current Implementation Status

### ✅ COMPLETE & WORKING

**Backend Infrastructure:**
- S3 chunked upload system (10MB chunks, resume support)
- Replicate Whisper transcription
- Repeated take detection algorithm
- Basic FCP7 XML export
- Video player with proxy support
- JWT authentication with auto-refresh
- Waveform generation

**Frontend:**
- Timeline editor UI with Zustand
- Video player with keyboard shortcuts
- Waveform visualization (WaveSurfer.js)
- Authentication with auto-refresh

### ⚠️ IN PROGRESS

**Week 1 (Current):**
- [ ] Fix frontend S3 chunked upload (currently using legacy single POST)
- [ ] Integrate repeated take detection into workflow
- [ ] Update documentation and configuration

**Week 2 (Planned):**
- [ ] Motion graphics generation (Nano Banana Pro + Hailuo AI)
- [ ] Background removal (Meta SAM-2)
- [ ] ZIP export with assets

---

## Cost Analysis (Per 3GB Video)

| Service | Operation | Cost |
|---------|-----------|------|
| AWS S3 | 300 PUT requests | $0.0015 |
| Replicate Whisper | 2hr transcription | ~$0.08 |
| Replicate Audio Extract | Audio extraction | ~$0.02 |
| **Total (Basic)** | | **~$0.10** |

**With Motion Graphics (5 segments):**
- Nano Banana Pro (10 frames): ~$0.10
- Hailuo AI (5 animations): ~$0.25
- **Total: ~$0.45**

**With Background Removal:**
- Meta SAM-2: ~$0.15
- **Total: ~$0.60**

---

## Quick Start for Development

### Test S3 Upload System
```bash
cd backend
python test_aws_credentials.py    # Verify AWS setup
```

### Get Demo Token
```bash
curl http://localhost:5000/auth/demo-token
```

### Initialize Chunked Upload
```bash
curl -X POST http://localhost:5000/upload/init \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.mp4", "file_size": 3221225472}'
```

### Check Backend Health
```bash
curl http://localhost:5000/health
```

---

## Key Differences from Previous Vision

**What Changed:**
- ❌ NO automatic segment classification (talking head / demo / abstract)
- ❌ NO 4-layer automated timeline generation
- ❌ NO AWS MediaConvert (Replicate-only for now)
- ✅ YES user-driven motion graphics generation (manual segment selection)
- ✅ YES background removal (optional, user-initiated)
- ✅ YES keep LAST occurrence of repeated takes (best take)

**Why:**
- Simpler, more focused MVP
- Lower cost (~$0.10-0.60 vs ~$1.05)
- More user control over creative decisions
- Faster time to market

---

## Next Steps

1. Fix frontend S3 chunked upload (Phase 2 - Week 1)
2. Integrate repeated take detection (Phase 3 - Week 1)
3. Build motion graphics UI (Phase 4 - Week 2)
4. Add background removal (Phase 5 - Week 2)
5. Implement ZIP export (Phase 6 - Week 2)

**For detailed implementation plan, see:** `C:\Users\Tomso\.claude\plans\melodic-bouncing-metcalfe.md`
