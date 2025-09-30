import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProcessingStatus from '../../components/ProcessingStatus'
import { ProcessingJob } from '../../types'

describe('ProcessingStatus Component', () => {
  const mockOnDownload = vi.fn()

  beforeEach(() => {
    mockOnDownload.mockClear()
  })

  const createMockJob = (overrides: Partial<ProcessingJob> = {}): ProcessingJob => ({
    job_id: 'test-job-123',
    status: 'processing',
    progress: 50,
    message: 'Processing audio...',
    created_at: '2024-01-01T10:00:00Z',
    completed_at: undefined,
    error: undefined,
    insights: undefined,
    timeline_comparison: undefined,
    processing_stats: undefined,
    ...overrides,
  })

  const defaultProps = {
    job: createMockJob(),
    onDownload: mockOnDownload,
  }

  it('renders processing job correctly', () => {
    render(<ProcessingStatus {...defaultProps} />)

    expect(screen.getByText('Processing Status')).toBeInTheDocument()
    expect(screen.getByText('Processing audio...')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('shows uploaded status', () => {
    const uploadedJob = createMockJob({
      status: 'uploaded',
      progress: 10,
      message: 'Files uploaded successfully',
    })

    render(<ProcessingStatus {...defaultProps} job={uploadedJob} />)

    expect(screen.getByText('Files uploaded successfully')).toBeInTheDocument()
    expect(screen.getByText('10%')).toBeInTheDocument()
  })

  it('shows completed status with download button', async () => {
    const user = userEvent.setup()
    const completedJob = createMockJob({
      status: 'completed',
      progress: 100,
      message: 'Processing completed successfully',
      completed_at: '2024-01-01T10:05:00Z',
    })

    render(<ProcessingStatus {...defaultProps} job={completedJob} />)

    expect(screen.getByText('Processing completed successfully')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()

    const downloadButton = screen.getByRole('button', { name: /download/i })
    expect(downloadButton).toBeInTheDocument()
    expect(downloadButton).not.toBeDisabled()

    await user.click(downloadButton)
    expect(mockOnDownload).toHaveBeenCalledWith('test-job-123')
  })

  it('shows failed status with error message', () => {
    const failedJob = createMockJob({
      status: 'failed',
      progress: 30,
      message: 'Processing failed',
      error: 'Audio file could not be processed',
    })

    render(<ProcessingStatus {...defaultProps} job={failedJob} />)

    expect(screen.getByText('Processing failed')).toBeInTheDocument()
    expect(screen.getByText('Audio file could not be processed')).toBeInTheDocument()
    expect(screen.getByText('30%')).toBeInTheDocument()
  })

  it('shows correct progress bar color for different statuses', () => {
    const { rerender } = render(<ProcessingStatus {...defaultProps} />)

    // Processing - should show blue/primary color
    let progressBar = screen.getByRole('progressbar')
    expect(progressBar.querySelector('.bg-primary-600')).toBeInTheDocument()

    // Completed - should show green color
    const completedJob = createMockJob({ status: 'completed', progress: 100 })
    rerender(<ProcessingStatus {...defaultProps} job={completedJob} />)

    progressBar = screen.getByRole('progressbar')
    expect(progressBar.querySelector('.bg-green-600')).toBeInTheDocument()

    // Failed - should show red color
    const failedJob = createMockJob({ status: 'failed', progress: 50 })
    rerender(<ProcessingStatus {...defaultProps} job={failedJob} />)

    progressBar = screen.getByRole('progressbar')
    expect(progressBar.querySelector('.bg-red-600')).toBeInTheDocument()
  })

  it('shows job timeline comparison when available', () => {
    const jobWithComparison = createMockJob({
      status: 'completed',
      timeline_comparison: {
        original: { duration: 120, clips: 5 },
        edited: { duration: 85, clips: 8 },
        reduction: { duration_seconds: 35, percentage: 29.2 },
      },
    })

    render(<ProcessingStatus {...defaultProps} job={jobWithComparison} />)

    expect(screen.getByText('Timeline Comparison')).toBeInTheDocument()
    expect(screen.getByText('Original: 120s (5 clips)')).toBeInTheDocument()
    expect(screen.getByText('Edited: 85s (8 clips)')).toBeInTheDocument()
    expect(screen.getByText('Reduction: 35s (29.2%)')).toBeInTheDocument()
  })

  it('shows processing insights when available', () => {
    const jobWithInsights = createMockJob({
      status: 'completed',
      insights: {
        transcription: {
          speakers_detected: 2,
          words_transcribed: 150,
          confidence_score: 0.94,
        },
        audio_analysis: {
          silence_segments_removed: 8,
          total_silence_duration: 45.5,
          energy_based_cuts: 12,
        },
        recommendations: {
          quality_assessment: 'high',
          suggested_improvements: ['Add background music', 'Adjust audio levels'],
        },
      },
    })

    render(<ProcessingStatus {...defaultProps} job={jobWithInsights} />)

    expect(screen.getByText('Processing Insights')).toBeInTheDocument()
    expect(screen.getByText('2 speakers detected')).toBeInTheDocument()
    expect(screen.getByText('150 words transcribed')).toBeInTheDocument()
    expect(screen.getByText('94% confidence')).toBeInTheDocument()
    expect(screen.getByText('8 silence segments removed')).toBeInTheDocument()
  })

  it('shows processing statistics when available', () => {
    const jobWithStats = createMockJob({
      status: 'completed',
      processing_stats: {
        total_duration: 125.5,
        transcription_duration: 45.2,
        audio_analysis_duration: 35.8,
        editing_duration: 44.5,
        memory_usage_mb: 256,
      },
    })

    render(<ProcessingStatus {...defaultProps} job={jobWithStats} />)

    expect(screen.getByText('Processing Statistics')).toBeInTheDocument()
    expect(screen.getByText('Total time: 2m 5s')).toBeInTheDocument()
    expect(screen.getByText('Memory used: 256 MB')).toBeInTheDocument()
  })

  it('shows elapsed time for current processing', () => {
    const processingJob = createMockJob({
      status: 'processing',
      created_at: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
    })

    render(<ProcessingStatus {...defaultProps} job={processingJob} />)

    expect(screen.getByText(/Elapsed time: 1m/)).toBeInTheDocument()
  })

  it('shows completion time for finished jobs', () => {
    const completedJob = createMockJob({
      status: 'completed',
      created_at: '2024-01-01T10:00:00Z',
      completed_at: '2024-01-01T10:05:00Z',
    })

    render(<ProcessingStatus {...defaultProps} job={completedJob} />)

    expect(screen.getByText('Completed at: 10:05 AM')).toBeInTheDocument()
    expect(screen.getByText('Duration: 5m 0s')).toBeInTheDocument()
  })

  it('shows retry button for failed jobs', async () => {
    const user = userEvent.setup()
    const failedJob = createMockJob({
      status: 'failed',
      error: 'Network error occurred',
    })

    render(<ProcessingStatus {...defaultProps} job={failedJob} />)

    const retryButton = screen.getByRole('button', { name: /retry/i })
    expect(retryButton).toBeInTheDocument()

    // Note: retry functionality would need to be implemented
  })

  it('disables download button when job is not completed', () => {
    const processingJob = createMockJob({
      status: 'processing',
    })

    render(<ProcessingStatus {...defaultProps} job={processingJob} />)

    const downloadButton = screen.queryByRole('button', { name: /download/i })
    expect(downloadButton).not.toBeInTheDocument()
  })

  it('shows job ID for debugging', () => {
    render(<ProcessingStatus {...defaultProps} />)

    expect(screen.getByText('Job ID: test-job-123')).toBeInTheDocument()
  })

  it('handles missing optional data gracefully', () => {
    const minimalJob = createMockJob({
      timeline_comparison: undefined,
      insights: undefined,
      processing_stats: undefined,
    })

    render(<ProcessingStatus {...defaultProps} job={minimalJob} />)

    // Should render without crashing
    expect(screen.getByText('Processing Status')).toBeInTheDocument()
    expect(screen.getByText('Processing audio...')).toBeInTheDocument()
  })

  it('formats duration correctly', () => {
    const jobWithStats = createMockJob({
      status: 'completed',
      processing_stats: {
        total_duration: 3725.5, // 1h 2m 5s
        transcription_duration: 0,
        audio_analysis_duration: 0,
        editing_duration: 0,
        memory_usage_mb: 0,
      },
    })

    render(<ProcessingStatus {...defaultProps} job={jobWithStats} />)

    expect(screen.getByText('Total time: 1h 2m 5s')).toBeInTheDocument()
  })

  it('shows live progress updates', () => {
    const { rerender } = render(<ProcessingStatus {...defaultProps} />)

    // Update progress
    const updatedJob = createMockJob({
      progress: 75,
      message: 'Finalizing timeline...',
    })

    rerender(<ProcessingStatus {...defaultProps} job={updatedJob} />)

    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('Finalizing timeline...')).toBeInTheDocument()
  })

  it('handles download button click correctly', async () => {
    const user = userEvent.setup()
    const completedJob = createMockJob({
      status: 'completed',
      job_id: 'specific-job-456',
    })

    render(<ProcessingStatus {...defaultProps} job={completedJob} />)

    const downloadButton = screen.getByRole('button', { name: /download/i })
    await user.click(downloadButton)

    expect(mockOnDownload).toHaveBeenCalledWith('specific-job-456')
    expect(mockOnDownload).toHaveBeenCalledTimes(1)
  })
})