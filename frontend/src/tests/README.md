# Frontend Testing Suite

This directory contains comprehensive tests for the easyedit-v2 React frontend application.

## Test Structure

### Component Tests
- `components/FileDropzone.test.tsx` - File upload and drag-and-drop functionality
- `components/ProcessingOptions.test.tsx` - Processing configuration options
- `components/ProcessingStatus.test.tsx` - Job status display and progress tracking
- `components/JobHistory.test.tsx` - Job history management and interaction
- `App.test.tsx` - Main application integration tests

### Service Tests
- `services/api.test.ts` - API service layer tests with mocked HTTP requests

### Test Configuration
- `setup.ts` - Test environment setup and global configuration

## Running Tests

### Prerequisites
Install test dependencies:
```bash
npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event vitest jsdom @types/jest msw
```

### Running Tests
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui
```

### Running Specific Tests
```bash
# Run specific component tests
npm test -- FileDropzone
npm test -- ProcessingOptions

# Run all component tests
npm test -- --testPathPattern=components

# Run API tests
npm test -- --testPathPattern=api.test
```

## Test Categories

### Unit Tests
Test individual components in isolation:
- **Component Rendering**: Verify components render with correct content
- **Props Handling**: Test component behavior with different props
- **Event Handling**: Test user interactions and callbacks
- **State Management**: Test internal component state changes

### Integration Tests
Test component interactions and data flow:
- **File Upload Flow**: End-to-end file selection and upload process
- **Processing Workflow**: Complete job lifecycle from upload to download
- **API Integration**: Frontend-backend communication patterns
- **Error Handling**: Graceful handling of API failures

### User Interaction Tests
Test real user scenarios:
- **File Drag & Drop**: Drag files onto upload zones
- **Form Interactions**: Checkboxes, inputs, and option changes
- **Button Clicks**: Action triggers and state changes
- **Keyboard Navigation**: Accessibility and keyboard-only usage

## Testing Patterns

### Component Testing Pattern
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MyComponent from '../MyComponent'

describe('MyComponent', () => {
  const mockHandler = vi.fn()

  beforeEach(() => {
    mockHandler.mockClear()
  })

  const defaultProps = {
    onAction: mockHandler,
    data: 'test-data'
  }

  it('renders correctly', () => {
    render(<MyComponent {...defaultProps} />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const user = userEvent.setup()
    render(<MyComponent {...defaultProps} />)

    const button = screen.getByRole('button', { name: /action/i })
    await user.click(button)

    expect(mockHandler).toHaveBeenCalledWith('expected-argument')
  })
})
```

### API Testing Pattern
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as api from '../services/api'

const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Service', () => {
  beforeEach(() => {
    mockFetch.mockClear()
  })

  it('makes correct API request', async () => {
    const mockResponse = { success: true, data: 'test' }
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    })

    const result = await api.someMethod()

    expect(mockFetch).toHaveBeenCalledWith('/expected-endpoint')
    expect(result).toEqual(mockResponse)
  })
})
```

## Test Data and Mocks

### File Mocks
```typescript
const createMockAudioFile = (name = 'test.wav') =>
  new File(['audio content'], name, { type: 'audio/wav' })

const createMockDRTFile = (name = 'timeline.drt') =>
  new File(['<?xml version="1.0"?><timeline></timeline>'], name, { type: 'application/xml' })
```

### API Response Mocks
```typescript
const mockJobResponse = {
  job_id: 'test-job-123',
  status: 'completed',
  progress: 100,
  message: 'Processing completed',
  created_at: '2024-01-01T10:00:00Z'
}
```

## Coverage Goals

### Target Coverage Metrics
- **Statements**: > 90%
- **Branches**: > 85%
- **Functions**: > 95%
- **Lines**: > 90%

### Coverage Commands
```bash
# Generate coverage report
npm run test:coverage

# View coverage report
open coverage/index.html
```

## Debugging Tests

### Debug Individual Tests
```bash
# Run single test file with debug output
npm test -- --testNamePattern="specific test name" --verbose
```

### Debug in Browser
```bash
# Open test UI for interactive debugging
npm run test:ui
```

### Common Debugging Techniques
1. **Use `screen.debug()`** to see current DOM state
2. **Add `console.log()`** statements in tests
3. **Use `waitFor()`** for async operations
4. **Check `mockFn.mock.calls`** to verify function calls

## Accessibility Testing

### Screen Reader Testing
```typescript
it('provides proper ARIA labels', () => {
  render(<Component />)

  const button = screen.getByRole('button', { name: /upload files/i })
  expect(button).toBeInTheDocument()
  expect(button).toHaveAttribute('aria-label')
})
```

### Keyboard Navigation
```typescript
it('supports keyboard navigation', async () => {
  const user = userEvent.setup()
  render(<Component />)

  await user.tab()
  expect(screen.getByRole('button')).toHaveFocus()
})
```

## Performance Testing

### Component Render Performance
```typescript
it('renders efficiently with large datasets', () => {
  const largeJobList = Array.from({ length: 100 }, (_, i) => ({ id: i, ...mockJob }))

  const startTime = performance.now()
  render(<JobHistory jobs={largeJobList} />)
  const endTime = performance.now()

  expect(endTime - startTime).toBeLessThan(100) // Should render in < 100ms
})
```

## Error Boundary Testing

```typescript
it('handles component errors gracefully', () => {
  const ThrowError = () => {
    throw new Error('Test error')
  }

  render(
    <ErrorBoundary>
      <ThrowError />
    </ErrorBoundary>
  )

  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
})
```

## Continuous Integration

### GitHub Actions Configuration
```yaml
- name: Run Frontend Tests
  run: |
    cd frontend
    npm ci
    npm run test:coverage

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./frontend/coverage/lcov.info
```

### Pre-commit Hooks
```json
{
  "husky": {
    "hooks": {
      "pre-commit": "cd frontend && npm test -- --passWithNoTests"
    }
  }
}
```

## Test Environment

### Environment Variables
```bash
# Test configuration
VITE_API_BASE_URL=http://localhost:5000
VITE_TEST_MODE=true
```

### Browser Testing
Tests run in jsdom by default. For browser-specific testing:
```bash
# Run tests in actual browser (if configured)
npm test -- --browser
```

## Best Practices

### Test Naming
- Use descriptive test names: `it('shows error message when upload fails')`
- Group related tests with `describe` blocks
- Use consistent naming patterns

### Test Structure
- **Arrange**: Set up test data and mocks
- **Act**: Trigger the behavior being tested
- **Assert**: Verify the expected outcome

### Mock Management
- Clear mocks between tests with `beforeEach`
- Mock external dependencies but avoid over-mocking
- Use realistic test data that matches production scenarios

### Async Testing
- Always await user interactions: `await user.click(button)`
- Use `waitFor()` for async state changes
- Test loading and error states

### Accessibility
- Test with screen readers in mind
- Verify keyboard navigation
- Check ARIA attributes and roles
- Test color contrast and visual indicators

## Troubleshooting

### Common Issues

1. **Tests timeout**: Increase timeout or check for unresolved promises
2. **Mock not working**: Verify mock is set up before component render
3. **Elements not found**: Use `screen.debug()` to inspect DOM
4. **Async issues**: Ensure proper `await` and `waitFor` usage

### Getting Help
- Check Testing Library documentation
- Review Vitest configuration
- Examine similar test patterns in the codebase
- Use test debugging tools and browser dev tools