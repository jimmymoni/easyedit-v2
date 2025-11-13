import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import * as api from '../../services/api';
import { GodLoadingIndicator } from './GodLoadingIndicator';
import { ContentAnalysis } from '../../types';

interface Message {
  id: string;
  sender: 'user' | 'god';
  text: string;
  timestamp: Date;
  options?: AIOption[];
  previewData?: any;
}

interface AIOption {
  id: string;
  label: string;
  description: string;
  params: Record<string, any> | null;
}

interface ChatInterfaceProps {
  jobId: string;
  onEditExecuted: (result: any) => void;
  contentAnalysis?: ContentAnalysis | null;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ jobId, onEditExecuted, contentAnalysis }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [selectedOption, setSelectedOption] = useState<AIOption | null>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [isLoadingGreeting, setIsLoadingGreeting] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch intelligent greeting on mount
  useEffect(() => {
    const fetchGreeting = async () => {
      try {
        setIsLoadingGreeting(true);
        const greetingData = await api.getIntelligentGreeting(jobId);

        // Add greeting as first message from God
        const greetingMessage: Message = {
          id: 'greeting',
          sender: 'god',
          text: greetingData.greeting,
          timestamp: new Date(),
          options: greetingData.options || [],
        };

        setMessages([greetingMessage]);
      } catch (error: any) {
        console.error('Failed to load intelligent greeting:', error);

        // Fallback to generic greeting
        const fallbackMessage: Message = {
          id: 'greeting-fallback',
          sender: 'god',
          text: '👋 How can I help you edit this timeline?\n\nI can help you:\n• Create **Instagram Reels / TikTok** videos\n• Make **montages** of specific phrases\n• Remove **silence** and long pauses\n• Filter by **speaker**\n\nWhat would you like to do?',
          timestamp: new Date(),
          options: [],
        };

        setMessages([fallbackMessage]);
      } finally {
        setIsLoadingGreeting(false);
      }
    };

    fetchGreeting();
  }, [jobId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isThinking) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsThinking(true);

    try {
      // Send message to AI chat endpoint
      const response = await api.sendChatMessage(jobId, inputValue);

      const godMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'god',
        text: response.message,
        timestamp: new Date(),
        options: response.options || [],
        previewData: response.preview_data,
      };

      setMessages(prev => [...prev, godMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'god',
        text: `Error: ${error.response?.data?.error || 'Failed to process message'}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsThinking(false);
      inputRef.current?.focus();
    }
  };

  const handleOptionClick = async (option: AIOption) => {
    if (!option.params) {
      // Option requires more input (e.g., "Different threshold")
      setSelectedOption(option);
      return;
    }

    setSelectedOption(option);

    // Check if this is a repurposing option (from intelligent greeting)
    const action = (option.params as any).action;
    if (action === 'apply_repurposing') {
      // Execute repurposing directly without preview
      setIsExecuting(true);

      try {
        // Add user selection message
        const userMessage: Message = {
          id: Date.now().toString(),
          sender: 'user',
          text: `Apply: ${option.label}`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, userMessage]);

        // Execute the repurposing
        const result = await api.submitAIEdit(jobId, 'Apply repurposing option', option.params);

        const confirmMessage: Message = {
          id: (Date.now() + 1).toString(),
          sender: 'god',
          text: `✅ ${result.message || 'Repurposing completed successfully!'}`,
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, confirmMessage]);

        // Notify parent component
        onEditExecuted(result);

        // Reset state
        setSelectedOption(null);
        setPreviewData(null);
      } catch (error: any) {
        const errorMessage: Message = {
          id: Date.now().toString(),
          sender: 'god',
          text: `❌ ${error.response?.data?.error || 'Repurposing failed'}`,
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, errorMessage]);
      } finally {
        setIsExecuting(false);
      }

      return;
    }

    // Standard flow: Get preview for other options
    try {
      setIsThinking(true);
      const response = await api.getAIPreview(jobId, option.params);
      setPreviewData(response.preview);

      const previewMessage: Message = {
        id: Date.now().toString(),
        sender: 'god',
        text: generatePreviewMessage(response.preview),
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, previewMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        sender: 'god',
        text: `Preview error: ${error.response?.data?.error || 'Failed to generate preview'}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleExecuteEdit = async () => {
    if (!selectedOption || !selectedOption.params) return;

    setIsExecuting(true);

    try {
      // Execute AI edit using the prompt and full params from selected option
      const result = await api.submitAIEdit(jobId, selectedOption.params.prompt, selectedOption.params);

      const confirmMessage: Message = {
        id: Date.now().toString(),
        sender: 'god',
        text: `✅ ${result.message || 'Edit completed successfully!'}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, confirmMessage]);

      // Notify parent component
      onEditExecuted(result);

      // Reset state
      setSelectedOption(null);
      setPreviewData(null);
    } catch (error: any) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        sender: 'god',
        text: `❌ ${error.response?.data?.error || 'Execution failed'}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsExecuting(false);
    }
  };

  const generatePreviewMessage = (preview: any): string => {
    if (preview.operation === 'montage') {
      const mode = preview.mode === 'tight' ? 'Tight' : preview.mode === 'normal' ? 'Normal' : 'Loose';
      return `**Preview: ${mode} Cut Montage**\n\n• **${preview.total_clips} clips**, ${preview.total_duration.toFixed(1)}s total\n• **${preview.compression.toFixed(1)}% compression**\n\nClips:\n${preview.clips.slice(0, 5).map((clip: any, i: number) =>
        `${clip.index}. ${formatTime(clip.start)}-${formatTime(clip.end)} "${clip.text}"`
      ).join('\n')}${preview.clips.length > 5 ? `\n... and ${preview.clips.length - 5} more` : ''}`;
    }
    return preview.message || 'Preview generated';
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-[#181818] px-6 py-3 border-b border-[#2A2A2A]">
        <h3 className="text-base font-semibold text-[#EAEAEA] flex items-center space-x-2">
          <span>⚡</span>
          <span>Chat with God</span>
        </h3>
      </div>

      {/* Messages Container */}
      <div className="p-6 h-[400px] overflow-y-auto space-y-4 bg-[#0A0A0A] chat-messages">
        {messages.length === 0 && isLoadingGreeting && (
          <div className="text-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-[#FF6B35] mx-auto mb-3" />
            <p className="text-[#EAEAEA]/70 text-sm">
              Analyzing your content...
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 border ${
                message.sender === 'user'
                  ? 'bg-[#2A2A2A] border-[#3A3A3A]'
                  : 'bg-[#181818] border-[#2A2A2A]'
              }`}
            >
              <div className={`whitespace-pre-wrap text-sm ${
                message.sender === 'user' ? 'text-[#EAEAEA]' : 'text-[#FF6B35]'
              }`}>
                {message.text.split('\n').map((line, i) => {
                  if (line.startsWith('**') && line.endsWith('**')) {
                    return <div key={i} className="font-bold mb-1">{line.slice(2, -2)}</div>;
                  }
                  if (line.startsWith('• ')) {
                    return <div key={i} className="ml-2">{line}</div>;
                  }
                  return <div key={i}>{line}</div>;
                })}
              </div>

              {/* Options */}
              {message.options && message.options.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {message.options.map((option) => (
                    <button
                      key={option.id}
                      onClick={() => handleOptionClick(option)}
                      className="w-full text-left bg-[#2A2A2A] hover:bg-[#3A3A3A] border border-[#3A3A3A] hover:border-[#FF6B35]/50 rounded-lg px-3 py-1.5 transition-all"
                    >
                      <div className="font-semibold text-sm text-[#EAEAEA]">{option.label}</div>
                      <div className="text-xs text-[#EAEAEA]/60">{option.description}</div>
                    </button>
                  ))}
                </div>
              )}

              <div className={`text-xs mt-2 ${
                message.sender === 'user' ? 'text-[#EAEAEA]/50' : 'text-[#FF6B35]/50'
              }`}>
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex justify-center w-full">
            <GodLoadingIndicator />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Execute Button (shown when preview is ready) */}
      {previewData && selectedOption && (
        <div className="px-6 py-3 bg-[#0A0A0A] border-t border-[#2A2A2A]">
          <button
            onClick={handleExecuteEdit}
            disabled={isExecuting}
            className="w-full bg-gradient-to-r from-[#FF6B35] to-[#FF8555] hover:from-[#FF8555] hover:to-[#FF6B35] text-white font-semibold py-3 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            {isExecuting ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Executing Edit...</span>
              </>
            ) : (
              <>
                <span>✅</span>
                <span>Execute AI Edit</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Input Box */}
      <div className="px-6 py-4 bg-[#181818] border-t border-[#2A2A2A]">
        <div className="flex items-center space-x-3">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            disabled={isThinking || isExecuting}
            className="flex-1 bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg px-4 py-3 text-[#EAEAEA] placeholder-[#EAEAEA]/30 focus:outline-none focus:border-[#FF6B35] disabled:opacity-50"
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isThinking || isExecuting}
            className="bg-[#FF6B35] hover:bg-[#FF8555] text-white p-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
