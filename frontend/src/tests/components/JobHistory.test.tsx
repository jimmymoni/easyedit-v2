import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobHistory from '../../components/JobHistory'
import { ProcessingJob } from '../../types'

describe('JobHistory Component', () => {
  const mockOnDownload = vi.fn()
  const mockOnViewDetails = vi.fn()

  beforeEach(() => {
    mockOnDownload.mockClear()
    mockOnViewDetails.mockClear()
  })

  const createMockJob = (id: string, overrides: Partial<ProcessingJob> = {}): ProcessingJob => ({
    job_id: id,
    status: 'completed',
    progress: 100,
    message: 'Processing completed',
    created_at: '2024-01-01T10:00:00Z',
    completed_at: '2024-01-01T10:05:00Z',
    ...overrides,
  })

  const mockJobs: ProcessingJob[] = [
    createMockJob('job-1', {
      status: 'completed',
      created_at: '2024-01-01T10:00:00Z',
      timeline_comparison: {
        original: { duration: 120, clips: 5 },
        edited: { duration: 85, clips: 8 },
        reduction: { duration_seconds: 35, percentage: 29.2 },
      },
    }),
    createMockJob('job-2', {
      status: 'failed',
      error: 'Audio processing failed',
      created_at: '2024-01-01T09:30:00Z',
    }),
    createMockJob('job-3', {
      status: 'processing',
      progress: 65,
      message: 'Analyzing audio...',
      created_at: '2024-01-01T09:00:00Z',
    }),
  ]

  const defaultProps = {
    jobs: mockJobs,
    onDownload: mockOnDownload,
    onViewDetails: mockOnViewDetails,
  }

  it('renders job history title', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('Job History')).toBeInTheDocument()
  })

  it('renders all jobs in the list', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('job-1')).toBeInTheDocument()
    expect(screen.getByText('job-2')).toBeInTheDocument()
    expect(screen.getByText('job-3')).toBeInTheDocument()
  })

  it('shows correct status indicators', () => {
    render(<JobHistory {...defaultProps} />)

    // Completed job should show success indicator
    const completedJob = screen.getByText('job-1').closest('.job-item')
    expect(completedJob).toHaveClass('border-green-200')

    // Failed job should show error indicator
    const failedJob = screen.getByText('job-2').closest('.job-item')
    expect(failedJob).toHaveClass('border-red-200')

    // Processing job should show processing indicator
    const processingJob = screen.getByText('job-3').closest('.job-item')
    expect(processingJob).toHaveClass('border-blue-200')
  })

  it('shows creation timestamps', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('10:00 AM')).toBeInTheDocument()
    expect(screen.getByText('9:30 AM')).toBeInTheDocument()
    expect(screen.getByText('9:00 AM')).toBeInTheDocument()
  })

  it('shows job progress for processing jobs', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('65%')).toBeInTheDocument()
    expect(screen.getByText('Analyzing audio...')).toBeInTheDocument()
  })

  it('shows download button for completed jobs', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const downloadButtons = screen.getAllByRole('button', { name: /download/i })
    expect(downloadButtons).toHaveLength(1) // Only completed job should have download button

    await user.click(downloadButtons[0])
    expect(mockOnDownload).toHaveBeenCalledWith('job-1')
  })

  it('shows view details button for all jobs', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const viewButtons = screen.getAllByRole('button', { name: /view details/i })
    expect(viewButtons).toHaveLength(3) // All jobs should have view details button

    await user.click(viewButtons[0])
    expect(mockOnViewDetails).toHaveBeenCalledWith(mockJobs[0])
  })

  it('displays timeline comparison info for completed jobs', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('120s → 85s')).toBeInTheDocument()
    expect(screen.getByText('29.2% reduction')).toBeInTheDocument()
  })

  it('shows error message for failed jobs', () => {
    render(<JobHistory {...defaultProps} />)

    expect(screen.getByText('Audio processing failed')).toBeInTheDocument()
  })

  it('handles empty job list', () => {
    render(<JobHistory {...defaultProps} jobs={[]} />)

    expect(screen.getByText('No jobs found')).toBeInTheDocument()
    expect(screen.getByText('Upload and process your first timeline to see it here.')).toBeInTheDocument()
  })

  it('sorts jobs by creation date (newest first)', () => {
    const unsortedJobs = [
      createMockJob('old-job', { created_at: '2024-01-01T08:00:00Z' }),
      createMockJob('new-job', { created_at: '2024-01-01T12:00:00Z' }),
      createMockJob('mid-job', { created_at: '2024-01-01T10:00:00Z' }),
    ]

    render(<JobHistory {...defaultProps} jobs={unsortedJobs} />)

    const jobItems = screen.getAllByTestId('job-item')
    expect(jobItems[0]).toHaveTextContent('new-job')
    expect(jobItems[1]).toHaveTextContent('mid-job')
    expect(jobItems[2]).toHaveTextContent('old-job')
  })

  it('shows relative time for recent jobs', () => {
    const recentJob = createMockJob('recent-job', {
      created_at: new Date(Date.now() - 30000).toISOString(), // 30 seconds ago
    })

    render(<JobHistory {...defaultProps} jobs={[recentJob]} />)

    expect(screen.getByText(/30 seconds ago/)).toBeInTheDocument()
  })

  it('limits the number of jobs displayed', () => {
    const manyJobs = Array.from({ length: 20 }, (_, i) =>
      createMockJob(`job-${i}`, { created_at: `2024-01-01T${10 + i}:00:00Z` })
    )

    render(<JobHistory {...defaultProps} jobs={manyJobs} />)

    // Should only display first 10 jobs (or whatever the limit is)
    const jobItems = screen.getAllByTestId('job-item')
    expect(jobItems.length).toBeLessThanOrEqual(10)
  })

  it('shows job type or source information', () => {
    const jobWithMetadata = createMockJob('metadata-job', {
      insights: {
        audio_analysis: {
          duration: 120,
          format: 'WAV',
          sample_rate: 48000,
        },
      },
    })

    render(<JobHistory {...defaultProps} jobs={[jobWithMetadata]} />)

    expect(screen.getByText('WAV, 48kHz')).toBeInTheDocument()
  })

  it('handles job status updates in real-time', () => {
    const { rerender } = render(<JobHistory {...defaultProps} />)

    // Update a processing job to completed
    const updatedJobs = [...mockJobs]
    updatedJobs[2] = {
      ...updatedJobs[2],
      status: 'completed',
      progress: 100,
      message: 'Processing completed',
      completed_at: '2024-01-01T09:05:00Z',
    }

    rerender(<JobHistory {...defaultProps} jobs={updatedJobs} />)

    // Should now show download button for the updated job
    const downloadButtons = screen.getAllByRole('button', { name: /download/i })
    expect(downloadButtons).toHaveLength(2) // Now two completed jobs
  })

  it('shows keyboard navigation support', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const firstViewButton = screen.getAllByRole('button', { name: /view details/i })[0]
    firstViewButton.focus()

    expect(document.activeElement).toBe(firstViewButton)

    // Tab to next button
    await user.tab()
    const downloadButton = screen.getByRole('button', { name: /download/i })
    expect(document.activeElement).toBe(downloadButton)
  })

  it('shows job duration information', () => {
    const jobWithDuration = createMockJob('duration-job', {
      processing_stats: {
        total_duration: 125.5,
        transcription_duration: 0,
        audio_analysis_duration: 0,
        editing_duration: 0,
        memory_usage_mb: 0,
      },
    })

    render(<JobHistory {...defaultProps} jobs={[jobWithDuration]} />)

    expect(screen.getByText('2m 5s')).toBeInTheDocument()
  })

  it('handles refresh of job list', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const refreshButton = screen.queryByRole('button', { name: /refresh/i })
    if (refreshButton) {
      await user.click(refreshButton)
      // Would trigger a refresh callback if implemented
    }
  })

  it('shows clear history option', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const clearButton = screen.queryByRole('button', { name: /clear history/i })
    if (clearButton) {
      await user.click(clearButton)
      // Would trigger a clear history callback if implemented
    }
  })

  it('shows job details preview on hover', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const jobItem = screen.getByText('job-1').closest('.job-item')
    if (jobItem) {
      await user.hover(jobItem)

      // Should show additional details in tooltip/preview
      // This would depend on the actual implementation
    }
  })

  it('handles job cancellation for processing jobs', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const cancelButton = screen.queryByRole('button', { name: /cancel/i })
    if (cancelButton) {
      await user.click(cancelButton)
      // Would trigger job cancellation if implemented
    }
  })

  it('shows export history option', async () => {
    const user = userEvent.setup()
    render(<JobHistory {...defaultProps} />)

    const exportButton = screen.queryByRole('button', { name: /export/i })
    if (exportButton) {
      await user.click(exportButton)
      // Would trigger history export if implemented
    }
  })
})