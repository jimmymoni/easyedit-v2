# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EasyEdit v2** is an AI-powered YouTube video automation system that transforms raw talking-head videos (3GB+) into polished, multi-layer productions ready for DaVinci Resolve.

### The Problem We're Solving

Content creators record long-form videos (1-2 hours) with:
- Multiple repeated takes of the same content
- Green screen backgrounds that need replacement
- Mix of talking head, screen demos, and abstract concepts
- **Manual editing takes 4-6 hours per video**

### Our Solution

An automated pipeline that:
1. **Accepts 3GB+ raw videos** (green screen talking-head footage)
2. **Auto-detects repeated takes** using AI (keeps only the best version)
3. **Classifies segments** into:
   - Talking head (green screen)
   - Demo/screen recording
   - Abstract concepts (needs AI animation)
4. **Generates AI animations** for abstract segments
5. **Creates multi-layer timeline** (4 layers for DaVinci Resolve)
6. **Exports DaVinci Resolve XML** for final polishing

**Target Workflow**: Reduce editing time from **4-6 hours** to **~1 hour** (20 min processing + 30 min polishing)

---

## Architecture

### Backend (Flask + Python 3.13)

- **Web Framework**: Flask REST API with JWT authentication
- **Cloud Storage**: AWS S3 (chunked uploads for 3GB+ files)
- **AI Processing**:
  - Replicate Whisper (transcription + speaker diarization) - $0.078/hour
  - OpenAI GPT-4 Vision (segment classification, script analysis)
  - Replicate models (AI animation generation)
- **Video Processing**: FFmpeg (transcoding, audio extraction, composition)
- **Task Queue**: Celery with Redis (background jobs)
- **Storage Strategy**:
  - S3: Original 3GB videos, proxy videos
  - Local: Temporary processing files
  - Redis/File: Job metadata, upload sessions

### Frontend (React 18 + TypeScript)

- **Framework**: React + TypeScript + Tailwind CSS
- **Build Tool**: Vite (fast development builds)
- **Upload**: Uppy.js (chunked upload with progress tracking)
- **API Client**: Axios with JWT token refresh
- **Design**: Professional dark UI with orange (#FF6B35) brand

### Key Workflow

```
User uploads 3GB video → S3 chunked upload (10MB chunks)
↓
Backend triggers processing:
  1. AWS MediaConvert transcoding (create 1080p H.264 proxy video) - ~$0.90/2hr
  2. Replicate audio extraction (16kHz WAV for Whisper) - ~$0.02
  3. Whisper transcription (speaker diarization via Replicate) - ~$0.08/hr
  4. Repeated take detection (keep best versions)
  5. Segment classification (talking head / demo / abstract via GPT-4 Vision)
  6. AI animation generation (for abstract segments)
  7. Multi-layer timeline compositor (4 layers)
  8. DaVinci Resolve XML export
↓
User downloads XML → Import to DaVinci Resolve → Final polish
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

# ✅ NO FFMPEG INSTALLATION NEEDED!
# Video processing uses cloud APIs only:
# - AWS MediaConvert for transcoding (production-grade)
# - Replicate for audio extraction and utilities
```

**Hybrid Cloud Architecture:**
Video transcoding via AWS MediaConvert (GPU-accelerated, enterprise-grade).
Audio extraction via Replicate (cost-effective, fast).
No need to install FFmpeg, codecs, or any external dependencies!

🚀 **Faster:** AWS GPU acceleration + Replicate cloud processing
💰 **Cost:** ~$1.00 per 2-hour video (~$0.90 MediaConvert + ~$0.10 Replicate)
📦 **Deploy Anywhere:** Vercel, Netlify, Railway, Render (no FFmpeg required)
🏢 **Production-Ready:** AWS MediaConvert used by Netflix, Prime Video, Disney+

### Environment Variables

Create a `.env` file in `backend/` directory (NOT root):

```bash
# AWS S3 Credentials (REQUIRED)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_VIDEO_BUCKET=easyedit-videos

# AWS MediaConvert (REQUIRED for video transcoding)
AWS_MEDIACONVERT_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/EasyEditMediaConvertRole

# AI API Keys (REQUIRED)
OPENAI_API_KEY=your_openai_api_key_here
REPLICATE_API_TOKEN=your_replicate_token_here

# Optional Configuration
MAX_FILE_SIZE_MB=5120  # 5GB max
S3_CHUNK_SIZE_MB=10
S3_PRESIGNED_URL_EXPIRATION=86400  # 24 hours
AWS_MEDIACONVERT_QUEUE=Default  # MediaConvert queue (default: Default)
LOG_LEVEL=INFO
```

**CRITICAL**: Always edit `backend/.env` (not root `.env`) for backend configuration!

**AWS MediaConvert Setup**: See [AWS_MEDIACONVERT_SETUP.md](./AWS_MEDIACONVERT_SETUP.md) for detailed IAM role setup instructions.

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

#### Production Mode with Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Testing

```bash
cd backend

# Test 1: AWS credentials and S3 access
python test_aws_credentials.py

# Test 2: Pre-signed URL generation
python test_presigned_url.py

# Test 3: Multipart upload mechanism
python test_multipart_presigned.py

# Test 4: Full upload flow (end-to-end)
python test_s3_upload.py
```

All tests should pass ✅

---

## API Endpoints

### Upload Endpoints (S3 Chunked Upload)

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

### Video Processing Endpoints

- **POST /process/{job_id}** - Start video processing
- **GET /status/{job_id}** - Get processing status and progress
- **GET /download/{job_id}** - Download processed DRT XML file

### Management Endpoints

- **GET /health** - Comprehensive health check with system metrics
- **GET /metrics** - System performance and usage metrics
- **GET /jobs** - List recent processing jobs
- **POST /cleanup** - Manually trigger file cleanup

### Authentication

- **POST /auth/demo-token** - Get demo JWT token (development only)

All endpoints (except `/auth/demo-token`) require JWT authentication:
```bash
Authorization: Bearer <your_jwt_token>
```

### Rate Limits

- Upload init: 10 requests/minute
- Chunk complete: 100 requests/minute
- General API: 60 requests/minute, 1000 requests/hour

---

## Project Structure

### Backend (`backend/`)

```
backend/
├── app.py                              # Main Flask application (3426+ lines)
├── config.py                           # Configuration with S3 settings
├── models/
│   ├── video_job.py                    # Job tracking model
│   ├── video_upload_session.py         # Upload session tracking
│   └── timeline.py                     # Timeline data structure (for XML export)
├── services/
│   ├── s3_upload_manager.py            # S3 multipart upload (526 lines) ✅
│   ├── video_transcoder.py             # FFmpeg video processing
│   ├── replicate_video_client.py       # AI video processing
│   ├── repeated_take_detector.py       # Duplicate detection
│   ├── video_ai_operations.py          # Segment classification
│   ├── waveform_generator.py           # Audio waveform generation
│   └── ai_chat_handler.py              # AI chat interface
├── parsers/
│   ├── xml_writer.py                   # DaVinci Resolve XML writer ✅
│   ├── canonical_extractor.py          # Helper for XML writing ✅
│   └── fcp7_xml_writer.py              # FCP7/DaVinci XML format
├── utils/
│   ├── error_handlers.py               # Error handling utilities
│   └── ffmpeg_helpers.py               # FFmpeg wrapper functions
├── test_aws_credentials.py             # AWS setup validation ✅
├── test_s3_upload.py                   # Upload flow test ✅
├── test_presigned_url.py               # URL generation test ✅
├── test_multipart_presigned.py         # Multipart upload test ✅
└── requirements.txt                    # Python dependencies
```

**CRITICAL XML EXPORT RULES** (DaVinci Resolve compatibility):
1. **Canonical File Block**: Defined ONCE in `<media>` section (after all tracks)
2. **Clipitem References**: ALL clips reference file by ID (`<file id="file-1"/>` self-closing)
3. **Audio Tracks**: Must exist with matching clipitems for each video clip
4. **In/Out Values**: Must reflect actual source media positions (not all zeros)
5. **Sequential Positioning**: No gaps or overlaps in cumulative clip positions
6. **Sequence Duration**: Must match last clip end time

### Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── App.tsx                         # Main React application
│   ├── components/
│   │   └── video/
│   │       ├── VideoEditorWorkspace.tsx   # Main editor workspace
│   │       ├── VideoUploadZone.tsx        # File upload component (Uppy.js)
│   │       ├── WaveformViewer.tsx         # Audio waveform display
│   │       └── TimelineEditor.tsx         # Timeline editing interface
│   ├── services/
│   │   └── api.ts                      # API client with axios
│   ├── types/
│   │   └── index.ts                    # TypeScript type definitions
│   └── pages/
│       └── VideoTestPage.tsx           # Video editor test page
├── package.json                        # Node.js dependencies
└── vite.config.ts                      # Vite configuration
```

---

## Production Features

### S3 Chunked Upload System ✅ COMPLETE

**Architecture**:
- Chunk Size: 10MB
- Max File Size: 5GB (configurable to 10GB)
- Max Chunks: 500 (for 5GB file)
- Parallel Uploads: 5 concurrent chunks
- URL Expiration: 24 hours
- Stale Upload Cleanup: 48 hours

**Upload Flow**:
```
1. Frontend: POST /upload/init {filename, file_size}
   Backend: Create S3 multipart upload
   Backend: Generate 500 pre-signed URLs (10MB each)
   Response: {job_id, chunk_urls[]}

2. Frontend: Upload chunks DIRECTLY to S3 (5 parallel)
   S3: Returns ETag for each chunk

3. Frontend: POST /upload/chunk-complete {job_id, part_number, etag}
   Backend: Track progress (e.g., 250/500 = 50%)

4. Frontend: POST /upload/complete {job_id}
   Backend: Tell S3 to combine all chunks
   S3: Creates final 5GB video file
   Backend: Trigger transcoding
```

**Cost per 3GB upload**:
- 300 PUT requests: $0.0015
- Temporary storage: ~$0 (deleted after transcode)
- **Total: ~$0.002 per upload**

### Security & Reliability

- JWT authentication on all endpoints
- Rate limiting per endpoint and client
- File size validation (max 5GB)
- Pre-signed URL expiration (24 hours)
- Filename sanitization
- CORS configured (PUT, POST, ETag exposed)
- Input validation and sanitization
- Error handling with detailed logging

### Monitoring & Health Checks

- System resource monitoring (CPU, memory, disk)
- API request metrics and error tracking
- Processing job success/failure rates
- External dependency health checks (AWS S3, OpenAI, Replicate APIs)
- Comprehensive logging with rotation

---

## 🎯 Current System Status

### ✅ Completed (Week 1, Day 1)

**S3 Chunked Upload System** - 100% Complete
- ✅ S3UploadManager service (526 lines)
- ✅ VideoUploadSession model (226 lines)
- ✅ 5 API endpoints (init, chunk-complete, complete, resume, abort)
- ✅ Full test suite (4 tests, all passing)
- ✅ AWS infrastructure configured
- ✅ Regional endpoint fix applied (eu-north-1)

### 🔄 In Progress (Week 1, Day 2-3)

**Frontend Integration** - Next Up
- [ ] Uppy.js upload component
- [ ] Progress tracking UI
- [ ] Resume functionality after network failure
- [ ] Cancel/abort upload option

### 📅 Upcoming

**Week 1, Day 4-5: Multi-Layer XML Writer**
- [ ] Extend FCP7XMLWriter for 4-layer support
- [ ] Test with DaVinci Resolve

**Week 2, Day 1-2: AI Segment Classification**
- [ ] GPT-4 Vision for frame analysis
- [ ] Classify segments (talking head / demo / abstract)

**Week 2, Day 3-4: Repeated Take Detector**
- [ ] Detect duplicate takes using transcription
- [ ] Score and keep best versions

**Week 2, Day 5: Timeline Compositor**
- [ ] Auto-generate 4-layer timeline
- [ ] Export DaVinci Resolve XML

**Overall Progress**: ~5% complete (foundational infrastructure done)

---

## 🎨 Design System

**IMPORTANT**: All UI development MUST follow **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)**

**Key Rules**:
- Background: `#000000` (pure black)
- Brand: `#FF6B35` (orange) for ALL interactive elements (NEVER blue/green)
- White cards: `bg-card` | Dark surfaces: `bg-[#181818]`
- Cards: `rounded-xl` (12px) | Spacing: `p-6` or `p-8`

**Reference Components**: `UploadProgress.tsx`, `ProcessingOptionsTable.tsx`, `VideoUploadZone.tsx`

---

## 🔍 Tech Stack Quick Reference

### Cloud Storage
- **AWS S3** - `backend/services/s3_upload_manager.py`
  - Multipart upload for 3GB+ files
  - Pre-signed URLs for direct client upload
  - Automatic cleanup of stale uploads
  - **CRITICAL**: Must use regional endpoint (`https://s3.{region}.amazonaws.com`)

### Video Processing (HYBRID CLOUD: AWS + Replicate)
- **AWS MediaConvert** - `backend/services/aws_mediaconvert_service.py`
  - **H.264 Transcoding**: Enterprise-grade GPU-accelerated transcoding
  - **Production Quality**: Baseline H.264 profile for maximum compatibility
  - **Web Optimized**: Progressive download (fast start) enabled
  - **Cost**: ~$0.0075/minute (~$0.90 per 2-hour video)
  - **Used by**: Netflix, Prime Video, Disney+
  - **No FFmpeg installation required!** ✅

- **Replicate APIs** - `backend/services/replicate_video_processor.py`
  - **Audio Extraction**: High-quality WAV extraction for Whisper
  - **Video Merging**: Combine segments after repeated take removal
  - **Models Used**:
    - `lucataco/extract-audio` - Audio extraction (~$0.02 per video)
    - `foixasoftware/ffmpeg` - Video merging (~$0.05 per concatenation)
  - **Cost**: ~$0.07 per 3GB video (utilities only)
  - **No FFmpeg installation required!** ✅

**Total Cost per 3GB Video**: ~$1.00 (~$0.90 MediaConvert + ~$0.10 Replicate + AI operations)

### AI Services
1. **Replicate Whisper** - `backend/services/replicate_video_client.py`
   - Cost: $0.078/hr
   - Model: incredibly-fast-whisper + pyannote diarization
   - Transcription + speaker identification

2. **OpenAI GPT-4 Vision** - `backend/services/video_ai_operations.py`
   - Segment classification (talking head / demo / abstract)
   - Script analysis and optimization
   - Chapter generation

3. **Replicate AI Models** - For animation generation
   - AI-generated backgrounds for abstract segments
   - Scene composition

### DaVinci Resolve XML Export
- **FCP7XMLWriter** - `backend/parsers/fcp7_xml_writer.py`
  - Generates DaVinci Resolve compatible XML
  - Multi-layer timeline support (4 tracks)
  - Proper canonical file block structure
  - Sequential clip positioning

---

## 🐛 Critical Issues & Solutions

### Issue: SignatureDoesNotMatch (403) on S3 presigned URLs

**Root Cause**: boto3 defaults to global S3 endpoint which causes signature mismatches for regional buckets.

**Solution**: Use regional endpoint in boto3 client:
```python
self.s3_client = boto3.client(
    's3',
    region_name=Config.AWS_REGION,
    endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'  # This fixes it
)
```

### Issue: Backend can't find .env file

**Problem**: Two `.env` files exist (root and backend/)

**Solution**: Always edit `backend/.env` (NOT root `.env`)

### Issue: boto3 not installed

**Solution**:
```bash
cd backend
pip install boto3==1.42.11 botocore==1.42.11
```

---

## 📊 Success Metrics

### Week 1 Goals:
- [x] S3 upload handles 3GB+ files ✅
- [ ] Frontend shows upload progress
- [ ] Can generate 4-layer XML
- [ ] XML imports into DaVinci Resolve

### Week 2 Goals:
- [ ] AI classifies segments accurately (>90%)
- [ ] Repeated takes are detected
- [ ] Timeline is auto-generated
- [ ] Full pipeline: Upload → Process → Export XML

### Final Success:
- [ ] 3GB video → 4-layer timeline in <20 minutes
- [ ] No manual intervention required
- [ ] DaVinci Resolve import is clean
- [ ] Cost per video <$1

---

## 📚 Additional Documentation

- **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)** - UI/UX design standards
- **[NEXT_SESSION_PROMPT_COMPLETE.md](./NEXT_SESSION_PROMPT_COMPLETE.md)** - Current roadmap and session context
- **[VIDEO_UPLOAD_RESEARCH.md](./VIDEO_UPLOAD_RESEARCH.md)** - Technical reference for S3 uploads

---

## 💡 Quick Start for Development

### Test S3 Upload System
```bash
cd backend
python test_aws_credentials.py    # Verify AWS setup
python test_s3_upload.py           # Test full upload flow
```

### Get Demo Token
```bash
curl http://localhost:5000/auth/demo-token
```

### Upload Test Video
```bash
curl -X POST http://localhost:5000/upload/init \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.mp4", "file_size": 104857600}'
```

### Check Backend Health
```bash
curl http://localhost:5000/health
```

---

**For detailed session history and technical deep-dives, see [NEXT_SESSION_PROMPT_COMPLETE.md](./NEXT_SESSION_PROMPT_COMPLETE.md)**
