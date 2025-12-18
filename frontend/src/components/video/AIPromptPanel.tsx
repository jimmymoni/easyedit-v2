import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Loader2,
  Sparkles,
  Eye,
  CheckCircle2,
  XCircle,
  AlertCircle
} from 'lucide-react';
import * as api from '../../services/api';

// ==========================================
// TYPES & INTERFACES
// ==========================================

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  preview?: AIPreviewResult;
  options?: AIEditOption[];
}

interface AIPreviewResult {
  operation: string;
  description: string;
  segments_affected: number;
  time_saved: number;
  new_duration: number;
  preview_data?: any;
}

interface AIEditOption {
  label: string;
  value: string;
  description?: string;
}

interface SuggestedPrompt {
  label: string;
  prompt: string;
  operation: string;
  icon?: React.ReactNode;
  description: string;
}

interface AIPromptPanelProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string;
  onApplyChanges: (changes: any) => void;
}

// ==========================================
// SUGGESTED PROMPTS CONFIGURATION
// ==========================================

const SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  {
    label: 'Remove repetitive takes',
    prompt: 'Remove all repeated takes and false starts from the video',
    operation: 'remove_repeated_takes',
    description: 'Automatically detect and remove repeated segments and false starts'
  },
  {
    label: 'Create 60s highlight reel',
    prompt: 'Create a 60-second highlight reel with the most engaging moments',
    operation: 'create_highlight',
    description: 'Extract the best 60 seconds of content based on engagement'
  },
  {
    label: 'Remove silence >2s',
    prompt: 'Remove all silences longer than 2 seconds',
    operation: 'remove_silence',
    description: 'Cut out long pauses to tighten the pacing'
  },
  {
    label: 'Keep only Speaker 1',
    prompt: 'Keep only segments where Speaker 1 is talking',
    operation: 'filter_speaker',
    description: 'Filter timeline to show only one speaker'
  },
  {
    label: 'Suggest stylish cut points',
    prompt: 'Analyze pacing and suggest where to place cuts for better rhythm',
    operation: 'suggest_cut_points',
    description: 'Get AI recommendations for dynamic cut placements'
  }
];

// ==========================================
// MAIN COMPONENT
// ==========================================

export default function AIPromptPanel({
  isOpen,
  onClose,
  jobId,
  onApplyChanges
}: AIPromptPanelProps) {

  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentPreview, setCurrentPreview] = useState<AIPreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // ==========================================
  // HANDLERS
  // ==========================================

  const handleSendMessage = async (promptText: string) => {
    if (!promptText.trim() || isProcessing) return;

    setError(null);
    setIsProcessing(true);

    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: promptText,
      timestamp: Date.now()
    };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');

    try {
      // Send to video AI chat endpoint
      const response = await api.sendVideoAIChat(jobId, promptText);

      // Add AI response
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.message || 'I can help you edit this video.',
        timestamp: Date.now(),
        preview: response.preview
      };

      setMessages(prev => [...prev, assistantMessage]);

      // If there's a preview, set it as current
      if (response.preview) {
        setCurrentPreview(response.preview);
      }

    } catch (err: any) {
      console.error('AI chat error:', err);
      const errorMessage = err.response?.data?.error || 'Failed to process your request. Please try again.';
      setError(errorMessage);

      // Add error message to chat
      const errorChatMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ ${errorMessage}`,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, errorChatMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSuggestedPrompt = (prompt: SuggestedPrompt) => {
    handleSendMessage(prompt.prompt);
  };

  const handlePreview = async () => {
    if (!currentPreview) return;

    // TODO: Implement preview visualization on timeline
    console.log('Preview:', currentPreview);
  };

  const handleApply = async () => {
    if (!currentPreview) return;

    try {
      setIsProcessing(true);

      // Apply AI suggestions to timeline
      await onApplyChanges(currentPreview);

      // Add success message
      const successMessage: ChatMessage = {
        id: `success-${Date.now()}`,
        role: 'assistant',
        content: '✅ Changes applied successfully! You can now manually refine the timeline.',
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, successMessage]);
      setCurrentPreview(null);

    } catch (err: any) {
      console.error('Apply error:', err);
      setError('Failed to apply changes. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  // ==========================================
  // RENDER
  // ==========================================

  return (
    <>
      {/* Overlay backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onClose}
        />
      )}

      {/* Slide-out panel */}
      <div className={`
        fixed top-0 right-0 h-full w-[420px] bg-card border-l border-border
        transform transition-transform duration-300 ease-in-out z-50 shadow-2xl
        flex flex-col
        ${isOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border bg-[#181818]">
          <div className="flex items-center space-x-3">
            <div className="bg-primary/10 p-2 rounded-lg">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">AI Video Editor</h3>
              <p className="text-xs text-muted-foreground">Natural language editing</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-accent"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="bg-red-500/10 border-b border-red-500/20 px-6 py-3 flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-red-500">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500/70 hover:text-red-500"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-8">
              <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <MessageSquare className="h-8 w-8 text-primary" />
              </div>
              <h4 className="text-foreground font-semibold mb-2">Welcome to AI Video Editor</h4>
              <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                Use natural language to edit your video. Try the suggested prompts below or type your own.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={`
              flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}
            `}>
              <div className={`
                max-w-[85%] rounded-xl px-4 py-3 space-y-2
                ${message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-[#181818] text-foreground border border-border'
                }
              `}>
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                {/* Preview card for AI suggestions */}
                {message.preview && (
                  <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
                    <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                      <Eye className="h-3.5 w-3.5" />
                      <span>Preview available</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="bg-card/50 rounded-lg p-2">
                        <div className="text-muted-foreground mb-0.5">Segments</div>
                        <div className="font-semibold text-foreground">{message.preview.segments_affected}</div>
                      </div>
                      <div className="bg-card/50 rounded-lg p-2">
                        <div className="text-muted-foreground mb-0.5">Saved</div>
                        <div className="font-semibold text-foreground">{Math.round(message.preview.time_saved)}s</div>
                      </div>
                      <div className="bg-card/50 rounded-lg p-2">
                        <div className="text-muted-foreground mb-0.5">Duration</div>
                        <div className="font-semibold text-foreground">{Math.round(message.preview.new_duration)}s</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isProcessing && (
            <div className="flex justify-start">
              <div className="bg-[#181818] border border-border rounded-xl px-4 py-3 flex items-center space-x-2">
                <Loader2 className="h-4 w-4 text-primary animate-spin" />
                <span className="text-sm text-muted-foreground">AI is thinking...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Preview action buttons */}
        {currentPreview && !isProcessing && (
          <div className="border-t border-border bg-[#181818] px-6 py-4 space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Preview ready</span>
              <span className="text-primary font-medium">{currentPreview.operation}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={handlePreview}
                className="flex items-center justify-center space-x-2 bg-accent text-foreground hover:bg-accent/80 px-4 py-2.5 rounded-lg font-medium transition-colors text-sm"
              >
                <Eye className="h-4 w-4" />
                <span>Preview</span>
              </button>
              <button
                onClick={handleApply}
                className="flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2.5 rounded-lg font-medium transition-colors text-sm"
              >
                <CheckCircle2 className="h-4 w-4" />
                <span>Apply</span>
              </button>
            </div>
            <button
              onClick={() => setCurrentPreview(null)}
              className="w-full flex items-center justify-center space-x-2 text-muted-foreground hover:text-foreground transition-colors text-sm py-1"
            >
              <XCircle className="h-3.5 w-3.5" />
              <span>Cancel</span>
            </button>
          </div>
        )}

        {/* Suggested prompts */}
        {messages.length === 0 && !isProcessing && (
          <div className="border-t border-border bg-[#181818] px-6 py-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Quick Actions
            </p>
            <div className="space-y-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt.operation}
                  onClick={() => handleSuggestedPrompt(prompt)}
                  className="w-full text-left bg-card hover:bg-accent border border-border rounded-lg px-4 py-3 transition-colors group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-foreground text-sm mb-1 group-hover:text-primary transition-colors">
                        {prompt.label}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {prompt.description}
                      </div>
                    </div>
                    <Sparkles className="h-4 w-4 text-primary/50 group-hover:text-primary transition-colors flex-shrink-0 mt-0.5" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-border p-6">
          <div className="flex items-end space-x-3">
            <div className="flex-1">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your editing request..."
                disabled={isProcessing}
                className="w-full bg-[#181818] border border-border rounded-lg px-4 py-3 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            <button
              onClick={() => handleSendMessage(inputValue)}
              disabled={!inputValue.trim() || isProcessing}
              className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed p-3 rounded-lg transition-colors"
            >
              {isProcessing ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Press Enter to send • Shift+Enter for new line
          </p>
        </div>

      </div>
    </>
  );
}
