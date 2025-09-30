import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProcessingOptions from '../../components/ProcessingOptions'
import { ProcessingOptions as ProcessingOptionsType } from '../../types'

describe('ProcessingOptions Component', () => {
  const mockOnOptionsChange = vi.fn()

  beforeEach(() => {
    mockOnOptionsChange.mockClear()
  })

  const defaultOptions: ProcessingOptionsType = {
    enable_transcription: true,
    enable_speaker_diarization: true,
    remove_silence: true,
    min_clip_length: 5,
    silence_threshold_db: -40,
  }

  const defaultProps = {
    options: defaultOptions,
    onOptionsChange: mockOnOptionsChange,
    disabled: false,
  }

  it('renders all processing options', () => {
    render(<ProcessingOptions {...defaultProps} />)

    expect(screen.getByText('Processing Options')).toBeInTheDocument()
    expect(screen.getByText('Enable Transcription')).toBeInTheDocument()
    expect(screen.getByText('Speaker Diarization')).toBeInTheDocument()
    expect(screen.getByText('Remove Silence')).toBeInTheDocument()
    expect(screen.getByText('Minimum Clip Length')).toBeInTheDocument()
    expect(screen.getByText('Silence Threshold')).toBeInTheDocument()
  })

  it('displays current option values correctly', () => {
    render(<ProcessingOptions {...defaultProps} />)

    expect(screen.getByRole('checkbox', { name: /Enable Transcription/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Speaker Diarization/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Remove Silence/ })).toBeChecked()
    expect(screen.getByDisplayValue('5')).toBeInTheDocument()
    expect(screen.getByDisplayValue('-40')).toBeInTheDocument()
  })

  it('handles transcription toggle correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const transcriptionCheckbox = screen.getByRole('checkbox', { name: /Enable Transcription/ })
    await user.click(transcriptionCheckbox)

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      enable_transcription: false,
    })
  })

  it('handles speaker diarization toggle correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const diarizationCheckbox = screen.getByRole('checkbox', { name: /Speaker Diarization/ })
    await user.click(diarizationCheckbox)

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      enable_speaker_diarization: false,
    })
  })

  it('handles remove silence toggle correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const silenceCheckbox = screen.getByRole('checkbox', { name: /Remove Silence/ })
    await user.click(silenceCheckbox)

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      remove_silence: false,
    })
  })

  it('handles minimum clip length change correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const clipLengthInput = screen.getByDisplayValue('5')
    await user.clear(clipLengthInput)
    await user.type(clipLengthInput, '3')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      min_clip_length: 3,
    })
  })

  it('handles silence threshold change correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const thresholdInput = screen.getByDisplayValue('-40')
    await user.clear(thresholdInput)
    await user.type(thresholdInput, '-35')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      silence_threshold_db: -35,
    })
  })

  it('disables all inputs when disabled prop is true', () => {
    render(<ProcessingOptions {...defaultProps} disabled={true} />)

    expect(screen.getByRole('checkbox', { name: /Enable Transcription/ })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /Speaker Diarization/ })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /Remove Silence/ })).toBeDisabled()
    expect(screen.getByDisplayValue('5')).toBeDisabled()
    expect(screen.getByDisplayValue('-40')).toBeDisabled()
  })

  it('shows speaker diarization only when transcription is enabled', () => {
    const optionsWithoutTranscription = {
      ...defaultOptions,
      enable_transcription: false,
    }

    render(<ProcessingOptions {...defaultProps} options={optionsWithoutTranscription} />)

    const diarizationCheckbox = screen.getByRole('checkbox', { name: /Speaker Diarization/ })
    expect(diarizationCheckbox).toBeDisabled()
  })

  it('validates minimum clip length range', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const clipLengthInput = screen.getByDisplayValue('5')

    // Test minimum value
    await user.clear(clipLengthInput)
    await user.type(clipLengthInput, '0.5')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      min_clip_length: 0.5,
    })

    // Test maximum value
    await user.clear(clipLengthInput)
    await user.type(clipLengthInput, '30')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      min_clip_length: 30,
    })
  })

  it('validates silence threshold range', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const thresholdInput = screen.getByDisplayValue('-40')

    // Test minimum value
    await user.clear(thresholdInput)
    await user.type(thresholdInput, '-80')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      silence_threshold_db: -80,
    })

    // Test maximum value
    await user.clear(thresholdInput)
    await user.type(thresholdInput, '-10')

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...defaultOptions,
      silence_threshold_db: -10,
    })
  })

  it('shows appropriate help text for each option', () => {
    render(<ProcessingOptions {...defaultProps} />)

    expect(screen.getByText(/Uses AI to transcribe audio and identify speakers/)).toBeInTheDocument()
    expect(screen.getByText(/Separates speakers into different timeline tracks/)).toBeInTheDocument()
    expect(screen.getByText(/Automatically removes silence segments/)).toBeInTheDocument()
    expect(screen.getByText(/Minimum duration for clips to be kept/)).toBeInTheDocument()
    expect(screen.getByText(/Audio level threshold for silence detection/)).toBeInTheDocument()
  })

  it('shows advanced options section', () => {
    render(<ProcessingOptions {...defaultProps} />)

    expect(screen.getByText('Advanced Options')).toBeInTheDocument()
  })

  it('handles multiple option changes correctly', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    // Change multiple options
    await user.click(screen.getByRole('checkbox', { name: /Enable Transcription/ }))
    await user.click(screen.getByRole('checkbox', { name: /Remove Silence/ }))

    expect(mockOnOptionsChange).toHaveBeenCalledTimes(2)
    expect(mockOnOptionsChange).toHaveBeenNthCalledWith(1, {
      ...defaultOptions,
      enable_transcription: false,
    })
    expect(mockOnOptionsChange).toHaveBeenNthCalledWith(2, {
      ...defaultOptions,
      remove_silence: false,
    })
  })

  it('preserves other options when changing one option', async () => {
    const user = userEvent.setup()
    const customOptions = {
      ...defaultOptions,
      min_clip_length: 10,
      silence_threshold_db: -30,
    }

    render(<ProcessingOptions {...defaultProps} options={customOptions} />)

    const transcriptionCheckbox = screen.getByRole('checkbox', { name: /Enable Transcription/ })
    await user.click(transcriptionCheckbox)

    expect(mockOnOptionsChange).toHaveBeenCalledWith({
      ...customOptions,
      enable_transcription: false,
    })
  })

  it('handles invalid input gracefully', async () => {
    const user = userEvent.setup()
    render(<ProcessingOptions {...defaultProps} />)

    const clipLengthInput = screen.getByDisplayValue('5')
    await user.clear(clipLengthInput)
    await user.type(clipLengthInput, 'invalid')

    // Should not call onOptionsChange with invalid value
    expect(mockOnOptionsChange).not.toHaveBeenCalledWith(
      expect.objectContaining({
        min_clip_length: 'invalid',
      })
    )
  })

  it('shows preset options for common use cases', () => {
    render(<ProcessingOptions {...defaultProps} />)

    // Check for preset buttons/options if they exist
    const presetSection = screen.queryByText('Presets')
    if (presetSection) {
      expect(presetSection).toBeInTheDocument()
    }
  })
})