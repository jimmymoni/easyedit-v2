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

---

## ⚠️ CRITICAL CONFIGURATION RULES

### 1. Frontend Port Requirement

**ALWAYS use port 3000 for frontend development.**

| Port | Status | Reason |
|------|--------|--------|
| 3000 | ✅ Required | S3 CORS allows this origin |
| 3002 | ⚠️ Allowed | S3 CORS allows this origin |
| 3005, 5173, etc. | ❌ Blocked | S3 CORS will reject uploads |

**If uploads fail with CORS error:**
1. ❌ DO NOT modify S3 CORS configuration
2. ✅ Check what port frontend is running on
3. ✅ Restart frontend on port 3000

**Why this matters:** S3 CORS is configured to only accept requests from specific origins. Changing CORS to wildcard `["*"]` is NOT the solution - using the correct port is.

### 2. S3 CORS Configuration

**Bucket:** `easyedit-videos`
**Region:** `eu-north-1`

**Configured Allowed Origins:**
```json
["http://localhost:3000", "http://localhost:3002", "https://easyedit.com"]
```

**Required Exposed Headers:**
```json
["ETag"]
```

The ETag header is critical for multipart upload completion. If uploads fail at the finalization step, verify CORS exposes ETag.

### 3. No Local Video Processing

**STRICT REQUIREMENT: All video operations must use cloud services (Replicate).**

| Operation | ✅ Allowed | ❌ Not Allowed |
|-----------|-----------|----------------|
| Transcription | Replicate Whisper | Local Whisper |
| Audio extraction | Replicate fofr/toolkit | Local FFmpeg |
| Video playback | S3 presigned URLs | Local file serving |
| Transcoding | AWS MediaConvert (if needed) | Local FFmpeg |

**Code patterns that violate this requirement:**
- `subprocess.run(['ffmpeg', ...])`
- `import ffmpeg`
- Local file paths for video processing
- Any `ffmpeg` command execution

If you need video processing, use Replicate models or AWS services.

---

## API Function Reference

### Video Status Functions

| Function Name | Location | Status | Use Case |
|---------------|----------|--------|----------|
| `api.getVideoJobStatus(jobId)` | api.ts:670-673 | ✅ EXISTS | Get video job status with proxy URL |
| `api.checkVideoStatus()` | - | ❌ DOES NOT EXIST | Never use |
| `api.getVideoStatus()` | - | ❌ DOES NOT EXIST | Never use |

**Correct usage:**
```tsx
// ✅ Correct - function exists
const status = await api.getVideoJobStatus(jobId);
const videoUrl = status.proxy_url;

// ❌ Wrong - these functions don't exist, will throw TypeError
const status = await api.checkVideoStatus(jobId);
const status = await api.getVideoStatus(jobId);
```

**Rule: Before using any API function, verify it exists in `frontend/src/services/api.ts`**

### Video Status Response Structure
```typescript
interface VideoJobStatus {
  job_id: string;
  status: string;
  proxy_url: string | null;      // S3 presigned URL for video playback
  proxy_status: string;          // 'pending' | 'ready' | 'failed'
  // ... other fields
}
```

---

## Data Structure Contracts

### Whisper Transcription → Frontend Segments

**⚠️ Backend and frontend use DIFFERENT property names!**

**Backend returns (from Whisper):**
```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Hello world"
    }
  ]
}
```

**Frontend expects:**
```typescript
interface Segment {
  start_time: number;
  end_time: number;
  text: string;
  status: 'keep' | 'remove';
}
```

**Always normalize segments in frontend:**
```tsx
const normalizedSegments = segments.map((seg, idx) => ({
  id: seg.id ?? `segment-${idx}`,
  start_time: seg.start_time ?? seg.start ?? 0,
  end_time: seg.end_time ?? seg.end ?? 0,
  text: seg.text ?? '',
  status: seg.status ?? 'keep'
}));
```

### Null Safety Requirements

**Always add fallbacks for numeric values used with .toFixed():**
```tsx
// ❌ CRASHES if value is undefined
{segment.start_time.toFixed(2)}

// ✅ SAFE with fallback
{(segment.start_time ?? 0).toFixed(2)}
```

**Always add fallbacks for calculations:**
```tsx
// ❌ CRASHES if duration is undefined
const width = (segment.duration / total) * 100;

// ✅ SAFE with fallback
const width = ((segment.duration ?? 0) / (total || 1)) * 100;
```

---

## Troubleshooting Decision Trees

### Upload Fails with CORS Error
```
CORS Error on Upload
│
├─→ Step 1: Check frontend port
│   ├─→ Port is 3000 or 3002? → Go to Step 2
│   └─→ Port is 3005/5173/other? → RESTART ON PORT 3000 ✅
│
├─→ Step 2: Check AWS credentials
│   ├─→ backend/.env has valid AWS keys? → Go to Step 3
│   └─→ Missing/invalid keys? → Fix credentials ✅
│
└─→ Step 3: Check S3 bucket
    ├─→ Run: aws s3 ls s3://easyedit-videos
    └─→ Bucket exists and accessible? → Check backend logs for specific error

❌ WRONG FIX: Changing S3 CORS to allow more origins
✅ RIGHT FIX: Use port 3000
```

### Video Not Playing
```
Video Not Playing
│
├─→ Console shows "api.X is not a function"?
│   └─→ Check api.ts for correct function name
│       └─→ Use api.getVideoJobStatus() not api.checkVideoStatus()
│
├─→ Console shows "No video URL available"?
│   ├─→ Check response from api.getVideoJobStatus()
│   ├─→ Is proxy_url present? → Test URL in browser
│   └─→ proxy_url is null? → Check backend video-status endpoint
│
├─→ Video URL exists but won't load?
│   ├─→ Test URL directly in browser
│   ├─→ Check if S3 presigned URL expired (24hr limit)
│   └─→ Check for CORS errors on video request
│
└─→ No errors but blank player?
    └─→ Check video element has src attribute in DevTools
```

### Timestamps Showing 0.0s or undefined
```
Timestamps Wrong
│
├─→ Step 1: Log raw segment data
│   └─→ console.log('Segment:', segments[0])
│
├─→ Step 2: Check property names
│   ├─→ Has "start"/"end"? → Need normalization (seg.start_time ?? seg.start)
│   ├─→ Has "start_time"/"end_time"? → Check values aren't 0
│   └─→ Properties missing? → Check backend response
│
└─→ Step 3: Add normalization layer
    └─→ See "Data Structure Contracts" section above
```

### Component Crashes with TypeError
```
TypeError: Cannot read property 'X' of undefined
│
├─→ Identify which value is undefined
│   └─→ Check the line number in error
│
├─→ Add null safety
│   ├─→ For objects: value?.property
│   ├─→ For defaults: value ?? defaultValue
│   └─→ For arrays: array?.map() or (array || []).map()
│
└─→ Add loading check
    └─→ if (!data) return <Loading />
```

---

## Common Mistakes to Avoid

### ❌ DON'T: Change S3 CORS for port issues
**Symptom:** Upload fails with CORS error on port 3005
**Wrong Fix:** Update S3 CORS to allow port 3005 or use wildcard `["*"]`
**Right Fix:** Restart frontend on port 3000

### ❌ DON'T: Guess API function names
**Symptom:** Need to fetch video status
**Wrong:** `api.checkVideoStatus(jobId)` - guessing the name
**Right:** Check `api.ts` for actual function → `api.getVideoJobStatus(jobId)`

### ❌ DON'T: Assume backend/frontend property names match
**Symptom:** Timestamps showing 0.0s
**Wrong:** Assume `segment.start_time` exists because frontend uses it
**Right:** Check actual API response, add normalization layer

### ❌ DON'T: Add local FFmpeg processing
**Symptom:** Need to extract audio or process video
**Wrong:** `subprocess.run(['ffmpeg', '-i', video, ...])`
**Right:** Use Replicate fofr/toolkit or other cloud service

### ❌ DON'T: Skip null safety on numeric operations
**Symptom:** Component crashes with "Cannot read property 'toFixed' of undefined"
**Wrong:** `segment.start_time.toFixed(2)`
**Right:** `(segment.start_time ?? 0).toFixed(2)`

### ❌ DON'T: Ignore TypeScript errors about missing properties
**Symptom:** TypeScript says property might be undefined
**Wrong:** Ignore with `// @ts-ignore`
**Right:** Add proper null checks or default values

---

## Pre-Development Checklist

**Before starting any development work, verify:**

- [ ] Backend running on port 5000: `python app.py`
- [ ] Frontend running on port 3000: `npm run dev` (check terminal output!)
- [ ] AWS credentials configured in `backend/.env`
- [ ] Replicate API token set in `backend/.env`
- [ ] Can access S3 bucket: `aws s3 ls s3://easyedit-videos`

**Before making API calls in frontend, verify:**

- [ ] Function exists in `frontend/src/services/api.ts`
- [ ] You're using the exact function name (case-sensitive)
- [ ] You understand the response structure

**Before displaying data from API, verify:**

- [ ] You've logged the raw response to see actual structure
- [ ] Property names match what component expects (or add normalization)
- [ ] Null safety added for all `.toFixed()`, calculations, and property access

---

## Quick Reference Card

| What | Correct | Wrong |
|------|---------|-------|
| Frontend port | 3000 | 3005, 5173, any other |
| Video status function | `api.getVideoJobStatus()` | `api.checkVideoStatus()` |
| Timestamp property (backend) | `start`, `end` | - |
| Timestamp property (frontend) | `start_time`, `end_time` | - |
| Video processing | Replicate cloud | Local FFmpeg |
| S3 bucket region | `eu-north-1` | `us-east-1` |
| Null safety | `(value ?? 0).toFixed()` | `value.toFixed()` |

---

### Running the Application

#### Development Mode

```bash
# Terminal 1 - Backend
cd backend
python app.py

# Terminal 2 - Frontend (⚠️ MUST be port 3000)
cd frontend
npm run dev  # Configured to use port 3000

# If port 3000 is busy, kill the process first:
# Windows: netstat -ano | findstr :3000 → taskkill /PID <pid> /F
# Mac/Linux: lsof -ti:3000 | xargs kill -9

# ❌ NEVER use other ports (3005, 5173, etc.) - S3 CORS will block uploads
```

Backend runs on: `http://localhost:5000`
Frontend runs on: `http://localhost:3000`  ⚠️ MUST be port 3000 (S3 CORS requirement)

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
| fofr/toolkit | Audio extraction (FFmpeg, CPU) | ~$0.0003 |
| **Total (Basic)** | | **~$0.082** |

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
