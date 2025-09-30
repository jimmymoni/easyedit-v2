import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as api from '../../services/api'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Service', () => {
  beforeEach(() => {
    mockFetch.mockClear()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mockResponse = (data: any, status = 200, ok = true) => {
    return Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(data),
      blob: () => Promise.resolve(new Blob([JSON.stringify(data)])),
      text: () => Promise.resolve(JSON.stringify(data)),
    } as Response)
  }

  describe('healthCheck', () => {
    it('should return success response', async () => {
      const mockData = { status: 'ok', version: '1.0.0' }
      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.healthCheck()

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:5000/health')
      expect(result).toEqual(mockData)
    })

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'))

      await expect(api.healthCheck()).rejects.toThrow('Network error')
    })

    it('should handle server errors', async () => {
      mockFetch.mockResolvedValue(mockResponse({ error: 'Server error' }, 500, false))

      await expect(api.healthCheck()).rejects.toThrow('HTTP error! status: 500')
    })
  })

  describe('uploadFiles', () => {
    it('should upload audio and DRT files successfully', async () => {
      const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
      const drtFile = new File(['drt content'], 'timeline.drt', { type: 'application/xml' })
      const mockData = { success: true, job_id: 'job-123', message: 'Files uploaded' }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.uploadFiles(audioFile, drtFile)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:5000/upload',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
        })
      )

      expect(result).toEqual(mockData)
    })

    it('should include both files in FormData', async () => {
      const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
      const drtFile = new File(['drt content'], 'timeline.drt', { type: 'application/xml' })
      const mockData = { success: true, job_id: 'job-123' }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      await api.uploadFiles(audioFile, drtFile)

      const call = mockFetch.mock.calls[0]
      const formData = call[1].body as FormData

      expect(formData.get('audio')).toBe(audioFile)
      expect(formData.get('drt')).toBe(drtFile)
    })

    it('should handle upload failures', async () => {
      const audioFile = new File(['audio'], 'test.wav')
      const drtFile = new File(['drt'], 'timeline.drt')

      mockFetch.mockResolvedValue(mockResponse({ error: 'Upload failed' }, 400, false))

      await expect(api.uploadFiles(audioFile, drtFile)).rejects.toThrow('HTTP error! status: 400')
    })
  })

  describe('processTimeline', () => {
    it('should start timeline processing with default options', async () => {
      const jobId = 'job-123'
      const mockData = { success: true, message: 'Processing started' }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.processTimeline(jobId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:5000/process/${jobId}`,
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        })
      )

      expect(result).toEqual(mockData)
    })

    it('should start processing with custom options', async () => {
      const jobId = 'job-123'
      const options = {
        enable_transcription: true,
        enable_speaker_diarization: false,
        remove_silence: true,
        min_clip_length: 3,
        silence_threshold_db: -35,
      }
      const mockData = { success: true, message: 'Processing started' }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.processTimeline(jobId, options)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:5000/process/${jobId}`,
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(options),
        })
      )

      expect(result).toEqual(mockData)
    })

    it('should handle processing errors', async () => {
      const jobId = 'job-123'
      mockFetch.mockResolvedValue(mockResponse({ error: 'Processing failed' }, 500, false))

      await expect(api.processTimeline(jobId)).rejects.toThrow('HTTP error! status: 500')
    })
  })

  describe('getJobStatus', () => {
    it('should fetch job status successfully', async () => {
      const jobId = 'job-123'
      const mockData = {
        job_id: jobId,
        status: 'processing',
        progress: 50,
        message: 'Processing audio...',
        created_at: '2024-01-01T10:00:00Z',
      }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.getJobStatus(jobId)

      expect(mockFetch).toHaveBeenCalledWith(`http://localhost:5000/status/${jobId}`)
      expect(result).toEqual(mockData)
    })

    it('should handle job not found', async () => {
      const jobId = 'nonexistent-job'
      mockFetch.mockResolvedValue(mockResponse({ error: 'Job not found' }, 404, false))

      await expect(api.getJobStatus(jobId)).rejects.toThrow('HTTP error! status: 404')
    })
  })

  describe('getAllJobs', () => {
    it('should fetch all jobs successfully', async () => {
      const mockData = {
        success: true,
        jobs: [
          {
            job_id: 'job-1',
            status: 'completed',
            progress: 100,
            created_at: '2024-01-01T10:00:00Z',
          },
          {
            job_id: 'job-2',
            status: 'processing',
            progress: 75,
            created_at: '2024-01-01T10:05:00Z',
          },
        ],
      }

      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.getAllJobs()

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:5000/jobs')
      expect(result).toEqual(mockData)
    })

    it('should handle empty job list', async () => {
      const mockData = { success: true, jobs: [] }
      mockFetch.mockResolvedValue(mockResponse(mockData))

      const result = await api.getAllJobs()

      expect(result).toEqual(mockData)
      expect(result.jobs).toHaveLength(0)
    })
  })

  describe('downloadResult', () => {
    it('should download file as blob successfully', async () => {
      const jobId = 'job-123'
      const mockBlob = new Blob(['file content'], { type: 'application/xml' })

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(mockBlob),
      } as Response)

      const result = await api.downloadResult(jobId)

      expect(mockFetch).toHaveBeenCalledWith(`http://localhost:5000/download/${jobId}`)
      expect(result).toBe(mockBlob)
    })

    it('should handle download failures', async () => {
      const jobId = 'job-123'
      mockFetch.mockResolvedValue(mockResponse({ error: 'File not found' }, 404, false))

      await expect(api.downloadResult(jobId)).rejects.toThrow('HTTP error! status: 404')
    })

    it('should handle large file downloads', async () => {
      const jobId = 'job-123'
      const largeContent = 'x'.repeat(10 * 1024 * 1024) // 10MB
      const mockBlob = new Blob([largeContent], { type: 'application/xml' })

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(mockBlob),
      } as Response)

      const result = await api.downloadResult(jobId)

      expect(result).toBe(mockBlob)
      expect(result.size).toBeGreaterThan(10 * 1024 * 1024)
    })
  })

  describe('API error handling', () => {
    it('should handle network timeouts', async () => {
      mockFetch.mockRejectedValue(new Error('Network timeout'))

      await expect(api.healthCheck()).rejects.toThrow('Network timeout')
    })

    it('should handle malformed JSON responses', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.reject(new Error('Invalid JSON')),
      } as Response)

      await expect(api.healthCheck()).rejects.toThrow('Invalid JSON')
    })

    it('should handle server maintenance mode', async () => {
      mockFetch.mockResolvedValue(mockResponse({ error: 'Server under maintenance' }, 503, false))

      await expect(api.healthCheck()).rejects.toThrow('HTTP error! status: 503')
    })
  })

  describe('API URL configuration', () => {
    it('should use correct base URL for all endpoints', async () => {
      const baseUrl = 'http://localhost:5000'

      // Test multiple endpoints to ensure consistent base URL usage
      mockFetch.mockResolvedValue(mockResponse({ status: 'ok' }))
      await api.healthCheck()
      expect(mockFetch).toHaveBeenCalledWith(`${baseUrl}/health`)

      mockFetch.mockResolvedValue(mockResponse({ jobs: [] }))
      await api.getAllJobs()
      expect(mockFetch).toHaveBeenCalledWith(`${baseUrl}/jobs`)

      const jobId = 'test-job'
      mockFetch.mockResolvedValue(mockResponse({ job_id: jobId }))
      await api.getJobStatus(jobId)
      expect(mockFetch).toHaveBeenCalledWith(`${baseUrl}/status/${jobId}`)
    })
  })

  describe('Request headers and content types', () => {
    it('should set correct headers for JSON requests', async () => {
      const jobId = 'job-123'
      mockFetch.mockResolvedValue(mockResponse({ success: true }))

      await api.processTimeline(jobId, { enable_transcription: true })

      const call = mockFetch.mock.calls[0]
      expect(call[1].headers).toEqual({ 'Content-Type': 'application/json' })
    })

    it('should handle multipart form data correctly', async () => {
      const audioFile = new File(['audio'], 'test.wav', { type: 'audio/wav' })
      const drtFile = new File(['drt'], 'timeline.drt', { type: 'application/xml' })

      mockFetch.mockResolvedValue(mockResponse({ success: true }))

      await api.uploadFiles(audioFile, drtFile)

      const call = mockFetch.mock.calls[0]
      expect(call[1].body).toBeInstanceOf(FormData)
      // Note: Content-Type header should not be set for FormData (browser sets it with boundary)
      expect(call[1].headers).toBeUndefined()
    })
  })

  describe('Response validation', () => {
    it('should validate response structure for job status', async () => {
      const incompleteResponse = { job_id: 'job-123' } // Missing required fields

      mockFetch.mockResolvedValue(mockResponse(incompleteResponse))

      const result = await api.getJobStatus('job-123')

      // API should return the response as-is, validation happens on the frontend
      expect(result).toEqual(incompleteResponse)
    })

    it('should handle responses with additional fields', async () => {
      const extendedResponse = {
        job_id: 'job-123',
        status: 'completed',
        progress: 100,
        message: 'Done',
        created_at: '2024-01-01T10:00:00Z',
        extra_field: 'extra_value', // Additional field
        nested_data: {
          some_metric: 42,
        },
      }

      mockFetch.mockResolvedValue(mockResponse(extendedResponse))

      const result = await api.getJobStatus('job-123')

      expect(result).toEqual(extendedResponse)
      expect(result.extra_field).toBe('extra_value')
      expect(result.nested_data.some_metric).toBe(42)
    })
  })
})