import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FileDropzone from '../../components/FileDropzone'

describe('FileDropzone Component', () => {
  const mockOnFilesSelected = vi.fn()

  beforeEach(() => {
    mockOnFilesSelected.mockClear()
  })

  const defaultProps = {
    onFilesSelected: mockOnFilesSelected,
    audioFile: null,
    drtFile: null,
    isUploading: false,
  }

  it('renders correctly with no files selected', () => {
    render(<FileDropzone {...defaultProps} />)

    expect(screen.getByText('Drag & drop your files here')).toBeInTheDocument()
    expect(screen.getByText('or click to select files')).toBeInTheDocument()
    expect(screen.getByText('Supported audio formats: WAV, MP3, M4A, AAC, FLAC')).toBeInTheDocument()
    expect(screen.getByText('DaVinci Resolve timeline files: .drt, .xml')).toBeInTheDocument()
  })

  it('displays selected audio file', () => {
    const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })

    render(<FileDropzone {...defaultProps} audioFile={audioFile} />)

    expect(screen.getByText('test.wav')).toBeInTheDocument()
    expect(screen.getByText('Audio File')).toBeInTheDocument()
  })

  it('displays selected DRT file', () => {
    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.drt', { type: 'application/xml' })

    render(<FileDropzone {...defaultProps} drtFile={drtFile} />)

    expect(screen.getByText('timeline.drt')).toBeInTheDocument()
    expect(screen.getByText('DRT Timeline')).toBeInTheDocument()
  })

  it('shows both files when selected', () => {
    const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.drt', { type: 'application/xml' })

    render(<FileDropzone {...defaultProps} audioFile={audioFile} drtFile={drtFile} />)

    expect(screen.getByText('test.wav')).toBeInTheDocument()
    expect(screen.getByText('timeline.drt')).toBeInTheDocument()
    expect(screen.getByText('Audio File')).toBeInTheDocument()
    expect(screen.getByText('DRT Timeline')).toBeInTheDocument()
  })

  it('handles file removal correctly', async () => {
    const user = userEvent.setup()
    const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.drt', { type: 'application/xml' })

    render(<FileDropzone {...defaultProps} audioFile={audioFile} drtFile={drtFile} />)

    // Remove audio file
    const removeAudioButton = screen.getAllByLabelText('Remove file')[0]
    await user.click(removeAudioButton)

    expect(mockOnFilesSelected).toHaveBeenCalledWith(null, drtFile)
  })

  it('disables dropzone when uploading', () => {
    render(<FileDropzone {...defaultProps} isUploading={true} />)

    const dropzone = screen.getByRole('button', { hidden: true })
    expect(dropzone).toHaveAttribute('aria-disabled', 'true')
  })

  it('shows uploading state correctly', () => {
    const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.drt', { type: 'application/xml' })

    render(<FileDropzone {...defaultProps} audioFile={audioFile} drtFile={drtFile} isUploading={true} />)

    expect(screen.getByText('Uploading files...')).toBeInTheDocument()
  })

  it('handles drag and drop correctly', async () => {
    render(<FileDropzone {...defaultProps} />)

    const audioFile = new File(['audio content'], 'test.wav', { type: 'audio/wav' })
    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.drt', { type: 'application/xml' })

    const dropzone = screen.getByTestId('dropzone')

    await waitFor(() => {
      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [audioFile, drtFile],
        },
      })
    })

    expect(mockOnFilesSelected).toHaveBeenCalledWith(audioFile, drtFile)
  })

  it('handles single audio file drop', async () => {
    render(<FileDropzone {...defaultProps} />)

    const audioFile = new File(['audio content'], 'test.mp3', { type: 'audio/mp3' })
    const dropzone = screen.getByTestId('dropzone')

    await waitFor(() => {
      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [audioFile],
        },
      })
    })

    expect(mockOnFilesSelected).toHaveBeenCalledWith(audioFile, null)
  })

  it('handles single DRT file drop', async () => {
    render(<FileDropzone {...defaultProps} />)

    const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], 'timeline.xml', { type: 'text/xml' })
    const dropzone = screen.getByTestId('dropzone')

    await waitFor(() => {
      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [drtFile],
        },
      })
    })

    expect(mockOnFilesSelected).toHaveBeenCalledWith(null, drtFile)
  })

  it('ignores unsupported file types', async () => {
    render(<FileDropzone {...defaultProps} />)

    const unsupportedFile = new File(['document content'], 'document.pdf', { type: 'application/pdf' })
    const dropzone = screen.getByTestId('dropzone')

    await waitFor(() => {
      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [unsupportedFile],
        },
      })
    })

    expect(mockOnFilesSelected).toHaveBeenCalledWith(null, null)
  })

  it('handles multiple audio files by keeping the last one', async () => {
    render(<FileDropzone {...defaultProps} />)

    const audioFile1 = new File(['audio content 1'], 'test1.wav', { type: 'audio/wav' })
    const audioFile2 = new File(['audio content 2'], 'test2.mp3', { type: 'audio/mp3' })
    const dropzone = screen.getByTestId('dropzone')

    await waitFor(() => {
      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [audioFile1, audioFile2],
        },
      })
    })

    // Should use the last audio file encountered
    expect(mockOnFilesSelected).toHaveBeenCalledWith(audioFile2, null)
  })

  it('shows correct file size formatting', () => {
    const audioFile = new File(['a'.repeat(1024 * 1024)], 'large.wav', { type: 'audio/wav' }) // 1MB

    render(<FileDropzone {...defaultProps} audioFile={audioFile} />)

    expect(screen.getByText(/1\.0 MB/)).toBeInTheDocument()
  })

  it('shows drag active state', async () => {
    render(<FileDropzone {...defaultProps} />)

    const dropzone = screen.getByTestId('dropzone')

    fireEvent.dragOver(dropzone)

    expect(dropzone).toHaveClass('border-primary-400')
    expect(dropzone).toHaveClass('bg-primary-50')
  })

  it('supports all specified audio formats', async () => {
    render(<FileDropzone {...defaultProps} />)

    const formats = [
      { name: 'test.wav', type: 'audio/wav' },
      { name: 'test.mp3', type: 'audio/mp3' },
      { name: 'test.m4a', type: 'audio/mp4' },
      { name: 'test.aac', type: 'audio/aac' },
      { name: 'test.flac', type: 'audio/flac' },
    ]

    for (const format of formats) {
      const audioFile = new File(['audio content'], format.name, { type: format.type })
      const dropzone = screen.getByTestId('dropzone')

      await waitFor(() => {
        fireEvent.drop(dropzone, {
          dataTransfer: {
            files: [audioFile],
          },
        })
      })

      expect(mockOnFilesSelected).toHaveBeenCalledWith(audioFile, null)
      mockOnFilesSelected.mockClear()
    }
  })

  it('supports DRT and XML file formats', async () => {
    render(<FileDropzone {...defaultProps} />)

    const formats = [
      { name: 'timeline.drt', type: 'application/xml' },
      { name: 'timeline.xml', type: 'text/xml' },
    ]

    for (const format of formats) {
      const drtFile = new File(['<?xml version="1.0"?><timeline></timeline>'], format.name, { type: format.type })
      const dropzone = screen.getByTestId('dropzone')

      await waitFor(() => {
        fireEvent.drop(dropzone, {
          dataTransfer: {
            files: [drtFile],
          },
        })
      })

      expect(mockOnFilesSelected).toHaveBeenCalledWith(null, drtFile)
      mockOnFilesSelected.mockClear()
    }
  })
})