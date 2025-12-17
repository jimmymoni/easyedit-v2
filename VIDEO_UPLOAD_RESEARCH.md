# Large Video File Upload Research (3GB+)
## Research Summary for Major Online Video Editing Platforms

**Research Date:** 2025-12-17
**Focus:** Upload architecture, file size limits, user experiences, and technical implementations for 3GB+ files

---

## Executive Summary

Modern video editing platforms use a combination of **chunked multipart uploads**, **direct-to-S3 uploads with pre-signed URLs**, and **resumable upload protocols (TUS)** to handle large files. Most platforms have file size limits ranging from 2GB to 6GB, with professional tools like Frame.io supporting larger files through optimized upload acceleration.

**Key Findings:**
- **Chunked uploads** (5-20MB chunks) with parallel processing are standard
- **Direct-to-S3/cloud storage** uploads reduce server load
- **Resumable uploads** (TUS protocol) are critical for 3GB+ files
- **Client-side compression** is avoided due to device limitations
- **Upload speed** varies dramatically based on implementation quality

---

## Platform-by-Platform Analysis

### 1. Frame.io (Professional Tool)

**File Size Limits:**
- No explicit limit mentioned for standard uploads
- Video editor project exports limited to **35GB total**
- Designed for professional video workflows

**Upload Architecture:**
- **Chunked uploads:** Files sliced into **20MB chunks**
- **Parallel uploads:** 5 chunks uploaded concurrently
- **Direct-to-S3:** Uses Amazon S3 with acceleration (`s3-accelerate.amazonaws.com`)
- **Speed:** Up to **5x faster** than top file-sharing services

**Technical Implementation:**
```
1. Asset Creation: API call creates placeholder asset in "uploading" state
2. Upload URLs: Server provides multiple pre-signed S3 URLs
3. Chunk Upload: PUT requests directly to S3 with proper ordering
4. Server Assembly: Chunks concatenated and transcoded after upload
```

**Key Details:**
- Chunk size calculated as: `chunk_size = ceil(file_size / len(upload_urls))`
- Uses S3 headers: `content-type` and `x-amz-acl: private`
- Recommends 2 concurrent uploads per CPU core for optimal performance
- Supports real-time uploads for streaming scenarios

**User Experience:**
- "Ludicrous speed" and "massively flexible feature set"
- "Speed of web-interface is basically magic"
- "Drastically changed workflow" with mobile app and Premiere Pro integration
- Wired connection recommended over WiFi for best performance

**Sources:**
- [Frame.io Basic Upload Guide](https://developer.dev.frame.io/docs/device-integrations/how-to-basic-upload)
- [Frame.io Advanced Uploads](https://developer.dev.frame.io/docs/device-integrations/how-to-advanced-uploads)
- [Frame.io Reviews on Capterra](https://www.capterra.com/p/148214/Frame-io/reviews/)
- [Frame.io 3.7 High-Speed File Sharing](https://www.digitalmediaworld.tv/post/3120-frame-io-3-7-supports-high-speed-file-sharing-and-accurate-reviews)

---

### 2. Kapwing (Consumer/Creator Tool)

**File Size Limits:**
- **Free Plan:** 250MB maximum
- **Pro Plan:** 6GB maximum (hard limit even for paid users)
- Duration limits: 4 min (free) vs 120 min (pro)

**Upload Architecture:**
- Standard HTTP upload (no detailed technical documentation available)
- Performance issues reported with large files

**User Complaints:**
- "Video editor struggles when working with large files or using a lot of features at once"
- Users must compress videos to stay under limits
- Strict 6GB cap is limiting for 4K video workflows

**Workarounds:**
- Official documentation provides guide on "How to Upload Over Kapwing's Limit"
- Requires external compression tools to reduce file size

**Sources:**
- [Kapwing Upload Limits Help](https://www.kapwing.com/help/how-to-over-kapwings-upload-limit/)
- [Kapwing Pro Subscription FAQ](https://www.kapwing.com/help/subscription-faq/)
- [AI Video Editing Review: Kapwing and Descript](https://podymos.com/learning-center/ai-video-editing-software-an-honest-review-of-kapwing-and-descript)

---

### 3. VEED.io (Consumer/Creator Tool)

**File Size Limits:**
- **Free Plan:** 250MB - 1GB (sources vary)
- **Paid Plans (Lite/Pro):** Unlimited file size

**Upload Architecture:**
- No specific technical details available
- Standard web upload with progress indicators

**Key Features:**
- Removes file size restrictions entirely on paid plans
- Supports drag-and-drop with visual feedback

**Sources:**
- [VEED.io Upload Guide](https://support.veed.io/en/articles/10657034-how-to-upload-video-audio-music-or-image-files)
- [VEED.io Review 2025](https://funnelscene.com/veed-io-review/)

---

### 4. Clipchamp (Microsoft-owned)

**File Size Limits:**
- **Official stance:** No file size limits
- **Reality:** Performance issues with files 4GB+ reported
- **User reports:** 2-4GB practical limits experienced

**Upload Architecture:**
- Browser-based upload
- Integration with Microsoft account storage
- No explicit chunking mentioned in documentation

**Complaints:**
- Conflicting information between Microsoft support and user experiences
- Microsoft states "no limit" but users report 2GB restrictions
- Loading errors common with 4GB+ files
- Upgrading subscription does NOT remove the 2GB import limit

**Sources:**
- [Microsoft Support: File Size Limits](https://support.microsoft.com/en-us/topic/are-there-input-file-size-limits-on-clipchamp-0b62dea9-969f-405f-b520-5ea8999e83b8)
- [Microsoft Q&A: 2GB Import Limit](https://learn.microsoft.com/en-us/answers/questions/5252361/why-is-there-all-of-a-sudden-a-2gb-import-limit-on)
- [PCWorld: Outrageous Limits Article](https://www.pcworld.com/article/622021/microsofts-new-video-editing-app-has-some-outrageous-limits.html)

---

### 5. Runway ML (AI Video Generation)

**File Size Limits:**
- Not explicitly stated for individual file uploads
- **Video editor project exports:** 35GB total limit
- Ephemeral uploads available for larger files (expire in 24 hours)
- Rate limits apply to ephemeral uploads

**Upload Architecture:**
- Standard URL uploads with size limits
- Ephemeral uploads API for larger files
- Direct API integration for developers

**Recommendations:**
- Use highest quality uncompressed footage for best AI results
- Consider ephemeral uploads for large files

**Sources:**
- [Runway API Input Parameters](https://docs.dev.runwayml.com/assets/inputs/)
- [Runway Ephemeral Uploads](https://docs.dev.runwayml.com/assets/uploads/)
- [Runway Video Files Guide](https://help.runwayml.com/hc/en-us/articles/4402453019795-Video-Files)

---

### 6. Descript (Professional Editing)

**File Size Limits:**
- No specific information found in search results
- Likely uses professional-grade upload infrastructure

**Upload Architecture:**
- No detailed technical documentation publicly available
- Review noted it "isn't as simple as Descript" compared to other tools

**User Feedback:**
- Described as text-based editing tool
- Less intimidating than pro software for beginners

**Sources:**
- [AI Video Editing Review: Kapwing and Descript](https://podymos.com/learning-center/ai-video-editing-software-an-honest-review-of-kapwing-and-descript)

---

## Technical Architecture Patterns

### 1. Chunked Multipart Uploads

**Standard Implementation:**
- File split into 5-20MB chunks
- 3-5 parallel uploads to saturate bandwidth
- Server-side reassembly after all chunks uploaded

**Benefits:**
- Better bandwidth utilization
- Resumability on network failures
- Only failed chunks need retry (not entire file)
- Reduces timeout risks

**Best Practices:**
```
Chunk Size: 5-10MB (typical), 20MB (Frame.io)
Parallel Uploads: 2 per CPU core (Frame.io recommendation)
Progress Tracking: Store chunk state in database (MongoDB/Redis)
Error Handling: Retry logic for individual chunks
```

**Sources:**
- [Why Chunked & Resumable Uploads Are a Game Changer](https://aditya007.medium.com/why-chunked-resumable-uploads-are-a-game-changer-for-video-processing-0554f2a36a98)
- [Scaling Video Uploads in a Startup](https://aditya007.medium.com/scaling-video-uploads-and-processing-in-a-startup-why-we-moved-to-cloud-based-chunk-uploads-and-ace38f8d0d5d)
- [AWS S3 Multipart Upload Guide](https://www.freecodecamp.org/news/upload-large-files-with-aws/)

---

### 2. Direct-to-S3 with Pre-signed URLs

**Architecture Flow:**
```
1. Frontend requests upload session from backend
2. Backend generates pre-signed S3 URLs for each chunk
3. Frontend uploads chunks directly to S3 (bypasses backend)
4. Backend notified on completion, triggers processing
5. S3 assembles chunks into final file
```

**Security Best Practices:**
- Short expiration times (minutes to hours, not days)
- Limit URL to specific operations (PutObject only)
- Restrict content types and file sizes
- Use HTTPS only
- Implement one-time use tracking server-side

**Benefits:**
- Reduces backend server load dramatically
- Improves upload speed (no backend bottleneck)
- Scales horizontally with cloud infrastructure
- Better user experience with instant feedback

**Sources:**
- [S3 Pre-signed URLs Architecture](https://dev.to/oliverke/the-architecture-that-lets-us-sleep-scalable-uploads-with-s3-presigned-urls-1jf3)
- [Resumable File Upload with S3](https://medium.com/@selvakumar.ponnusamy/resumable-file-upload-with-s3-ce039cbc8865)
- [GitHub: S3 Large File Uploader](https://github.com/nicholasadamou/s3-large-file-uploader)

---

### 3. TUS Protocol (Resumable Uploads)

**Overview:**
- Open protocol for resumable uploads built on HTTP
- Industry standard for large file uploads
- Interruptions can be resumed without re-uploading previous data

**Implementations:**
- **tusd:** Official Go reference implementation
- **tus-js-client:** JavaScript client library
- **Uppy.js:** Full-featured file uploader with TUS support

**Platforms Using TUS:**
- Cloudflare Stream (recommends TUS for 200MB+ videos)
- Bunny.net (BunnyCDN video platform)
- ArvanCloud (video hosting)
- Supabase Storage
- Transloadit

**Technical Requirements:**
- Minimum chunk size: 5,242,880 bytes (Cloudflare requirement)
- Upload session tracking with unique IDs
- State persistence across interruptions

**Sources:**
- [TUS Protocol Official Site](https://tus.io/)
- [Cloudflare Stream Resumable Uploads](https://developers.cloudflare.com/stream/uploading-videos/resumable-uploads/)
- [Bunny.net TUS Implementation](https://docs.bunny.net/reference/tus-resumable-uploads)
- [Uppy.js TUS Documentation](https://uppy.io/docs/tus/)

---

### 4. AWS S3 Transfer Acceleration

**What It Is:**
- Uses Amazon CloudFront edge locations globally
- Optimizes routing for long-distance uploads
- Can improve speeds by 50-500% depending on geography

**When to Use:**
- Cross-continent uploads
- Large files (multi-GB)
- Combined with multipart uploads for best results

**Implementation:**
- Enable Transfer Acceleration on S3 bucket
- Use accelerated endpoint: `bucketname.s3-accelerate.amazonaws.com`
- AWS SDK handles automatically for large files

**Sources:**
- [AWS Multipart Upload with Transfer Acceleration](https://aws.amazon.com/blogs/compute/uploading-large-objects-to-amazon-s3-using-multipart-upload-and-transfer-acceleration/)
- [Uploading Videos to S3 Faster](https://aws.plainenglish.io/uploading-videos-to-amazon-s3-buckets-faster-using-multipart-upload-73753d6de396)

---

## Client-Side vs Server-Side Processing

### Client-Side Compression

**Tools:**
- FFmpeg.wasm (WebAssembly FFmpeg in browser)
- Browser-native video encoding APIs

**Pros:**
- Reduces server load
- Privacy (data stays local)
- Reduces upload bandwidth

**Cons:**
- Mobile devices lack processing power and battery life
- Resource-intensive (causes performance issues on low-end devices)
- Inconsistent quality across browsers
- Slow processing times frustrate users

**Verdict:** Most platforms AVOID client-side compression for video

**Sources:**
- [Client-Side Video Optimization](https://pascalbirchler.com/client-side-video-optimization/)
- [Video Compression Pipeline in Web Apps](https://medium.com/@dmitry-barabash/photo-and-video-compression-pipeline-in-modern-web-applications-921fa2988628)
- [Microsoft: Avoid Client-Side Transcoding](https://learn.microsoft.com/en-us/answers/questions/5537921/how-can-i-handle-video-uploads-and-processing-effi)

### Server-Side Processing

**Approach:**
- Upload original file to cloud storage
- Transcode on powerful servers after upload
- Use services like AWS Transcoder, FFmpeg on server

**Benefits:**
- Better quality and consistency
- No device compatibility issues
- Faster processing on powerful hardware
- Works reliably on all devices

**Verdict:** Server-side processing is industry standard

---

## Common Upload Timeout Solutions

### Problems with Large Files (3GB+)

**Timeout Causes:**
1. Network interruptions
2. Files not sent within timeout period
3. Insufficient device memory
4. Server overload
5. Low client bandwidth

**Solutions:**

1. **Chunked Uploads** - Eliminate risk of timeouts between client/server
2. **Asynchronous Uploads** - Background upload while app continues functioning
3. **Resumable Uploads** - Pause/resume without starting over
4. **Server Configuration:**
   - Increase `max_execution_time`
   - Increase `upload_max_filesize`
   - Increase `post_max_size`
   - Increase `memory_limit`
5. **Cloud Storage Integration** - Direct uploads to S3/GCS/Azure

**Sources:**
- [How to Upload Large Files: Developer Guide](https://uploadcare.com/blog/handling-large-file-uploads/)
- [Common Problems with Large File Uploads](https://blog.filestack.com/thoughts-and-knowledge/common-problems-with-large-file-uploads/)
- [Stack Overflow: Timeout Issues](https://github.com/strapi/strapi/issues/9722)

---

## UX Best Practices for Large Video Uploads

### Progress Indicators

**Essential Elements:**
- Real-time progress updates (percentage completed)
- Estimated time remaining
- Current upload speed (optional)
- Cancel button for user control

**Rules:**
- Display progress bar for uploads >3 seconds
- Show percentage AND time estimate
- Update frequently (not just 0-100% jumps)

### Drag-and-Drop

**Implementation:**
- Clear visual indication drag-and-drop is supported
- Visual feedback on file drop (highlight zone)
- File preview after upload
- Multiple file support

### Resumable Uploads

**User Experience:**
- Automatic resume after network interruption
- LocalStorage checkpointing for browser refresh
- Clear messaging: "Upload paused, resume when ready"
- "Resume Upload" button visible

### Mobile Compatibility

**Critical Considerations:**
- Over 60% of uploads originate from mobile
- Touch-friendly upload buttons
- Camera integration for direct capture
- Responsive progress indicators
- Handle background app suspension

**Sources:**
- [File Upload UX Best Practices](https://megainterview.com/file-upload-ux-best-practices/)
- [10 File Upload System Features 2025](https://www.portotheme.com/10-file-upload-system-features-every-developer-should-know-in-2025/)
- [Progress Indicators for SaaS Design](https://dev.to/lollypopdesign/progress-indicators-explained-types-variations-best-practices-for-saas-design-392n)
- [Uploadcare: File Uploader UX](https://uploadcare.com/blog/file-uploader-ux-best-practices/)

---

## File Size Limits Comparison Table

| Platform     | Free Plan      | Paid Plan         | Architecture           | Resumable |
|-------------|---------------|------------------|----------------------|-----------|
| Frame.io    | N/A           | 35GB (projects)  | Chunked S3 Direct    | Yes       |
| Kapwing     | 250MB         | 6GB              | Standard HTTP        | Unknown   |
| VEED.io     | 250MB - 1GB   | Unlimited        | Standard HTTP        | Unknown   |
| Clipchamp   | No Limit*     | No Limit*        | Browser Upload       | Unknown   |
| Runway ML   | Unknown       | 35GB (projects)  | Ephemeral Uploads    | Yes       |
| Descript    | Unknown       | Unknown          | Unknown              | Unknown   |

*Clipchamp claims "no limit" but users report 2-4GB practical limits with performance issues

---

## Key Takeaways for 3GB+ File Uploads

### What Works Well

1. **Chunked multipart uploads** (5-20MB chunks)
2. **Direct-to-cloud-storage** with pre-signed URLs
3. **Parallel uploads** (3-5 concurrent chunks)
4. **TUS protocol** for resumability
5. **Server-side processing** (not client-side)
6. **Progress indicators** with time estimates
7. **AWS S3 Transfer Acceleration** for global users

### What to Avoid

1. **Single HTTP POST** for entire file (timeouts inevitable)
2. **Client-side compression** (poor UX, device limitations)
3. **Uploading through backend proxy** (bottleneck)
4. **No resumability** (users re-upload on failure)
5. **Lack of progress feedback** (users think it's frozen)

### Recommended Stack for 3GB+ Videos

**Frontend:**
- Uppy.js with TUS plugin
- Drag-and-drop interface
- Progress indicators with ETA
- LocalStorage checkpointing

**Backend:**
- Generate pre-signed S3 URLs
- Track upload sessions in Redis/MongoDB
- Trigger processing on upload completion
- Implement rate limiting

**Cloud Storage:**
- AWS S3 with Transfer Acceleration
- Multipart upload API
- CloudFront for global distribution
- Lifecycle policies for cleanup

**Processing:**
- Server-side transcoding (FFmpeg, AWS Transcoder)
- Queue system (Celery, Bull, AWS Lambda)
- Webhook notifications on completion

---

## Implementation Example (Simplified)

### Frontend (Uppy.js + TUS)
```javascript
import Uppy from '@uppy/core';
import Tus from '@uppy/tus';
import Dashboard from '@uppy/dashboard';

const uppy = new Uppy({
  restrictions: {
    maxFileSize: 5 * 1024 * 1024 * 1024, // 5GB
    allowedFileTypes: ['video/*']
  }
})
.use(Tus, {
  endpoint: '/api/upload',
  chunkSize: 10 * 1024 * 1024, // 10MB chunks
  resume: true,
  retryDelays: [0, 1000, 3000, 5000]
})
.use(Dashboard, {
  target: 'body',
  inline: true
});

uppy.on('complete', (result) => {
  console.log('Upload complete:', result.successful);
});
```

### Backend (Pre-signed URLs - Python/Flask)
```python
import boto3
from flask import Flask, request, jsonify

app = Flask(__name__)
s3_client = boto3.client('s3')

@app.route('/api/upload/presign', methods=['POST'])
def generate_presigned_url():
    data = request.json
    filename = data['filename']
    file_size = data['file_size']

    # Calculate number of chunks
    chunk_size = 10 * 1024 * 1024  # 10MB
    num_chunks = (file_size + chunk_size - 1) // chunk_size

    # Initiate multipart upload
    multipart = s3_client.create_multipart_upload(
        Bucket='my-video-bucket',
        Key=filename,
        ContentType='video/mp4'
    )

    upload_id = multipart['UploadId']

    # Generate pre-signed URLs for each chunk
    urls = []
    for part_number in range(1, num_chunks + 1):
        presigned_url = s3_client.generate_presigned_url(
            'upload_part',
            Params={
                'Bucket': 'my-video-bucket',
                'Key': filename,
                'UploadId': upload_id,
                'PartNumber': part_number
            },
            ExpiresIn=3600  # 1 hour
        )
        urls.append(presigned_url)

    return jsonify({
        'upload_id': upload_id,
        'urls': urls
    })

@app.route('/api/upload/complete', methods=['POST'])
def complete_upload():
    data = request.json
    filename = data['filename']
    upload_id = data['upload_id']
    parts = data['parts']  # List of {PartNumber, ETag}

    s3_client.complete_multipart_upload(
        Bucket='my-video-bucket',
        Key=filename,
        UploadId=upload_id,
        MultipartUpload={'Parts': parts}
    )

    return jsonify({'status': 'success'})
```

---

## Conclusion

For 3GB+ video files, modern platforms converge on a proven architecture:

1. **Chunked uploads** with 5-20MB chunks
2. **Direct-to-S3** using pre-signed URLs
3. **Parallel processing** of 3-5 chunks
4. **Resumable protocols** (TUS) for reliability
5. **Server-side transcoding** for processing
6. **Rich progress UX** with time estimates

Frame.io represents the gold standard with 5x faster uploads, 20MB chunks, and professional-grade reliability. Consumer tools (Kapwing, VEED, Clipchamp) have stricter limits (250MB-6GB) but are improving. The TUS protocol is becoming the industry standard for resumability.

**For your easyedit-v2 project handling 3GB+ video files, the recommended approach is:**
- Implement chunked multipart uploads (10MB chunks)
- Use pre-signed S3 URLs for direct uploads
- Add TUS protocol support for resumability
- Show detailed progress with ETA
- Process video server-side after upload completes
- Consider AWS S3 Transfer Acceleration for global users

---

## Additional Resources

### GitHub Examples
- [S3 Large File Uploader (Fast API + React)](https://github.com/nicholasadamou/s3-large-file-uploader)
- [TUS Protocol Reference Implementation](https://github.com/tus/tusd)
- [Uppy.js File Uploader](https://uppy.io/)

### Technical Articles
- [Resumable File Transfer Best Practices](https://dev.yunnan.ws/en/blog/resumable-file-transfer)
- [10 File Upload System Features Every Developer Should Know](https://www.portotheme.com/10-file-upload-system-features-every-developer-should-know-in-2025/)
- [Chunked & Resumable Uploads Game Changer](https://aditya007.medium.com/why-chunked-resumable-uploads-are-a-game-changer-for-video-processing-0554f2a36a98)

### Official Documentation
- [AWS S3 Multipart Upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [TUS Protocol Specification](https://tus.io/protocols/resumable-upload)
- [Frame.io Developer Documentation](https://developer.frame.io/)

---

**Research compiled by:** Claude Code (Anthropic)
**Date:** December 17, 2025
**Project:** easyedit-v2 Video Upload Architecture Research
