import React, { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface PromptInputProps {
  onSubmit: (prompt: string) => void;
  isProcessing: boolean;
}

const PromptInput: React.FC<PromptInputProps> = ({ onSubmit, isProcessing }) => {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isProcessing) {
      onSubmit(prompt.trim());
    }
  };

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
      <h3 className="text-lg font-semibold text-[#EAEAEA] mb-4">
        💬 AI Command Prompt
      </h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isProcessing}
            placeholder="Describe your edit... (e.g., 'Make a montage of every time I say money in the bank' or 'Remove all silence above 2 seconds')"
            className="w-full bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg px-4 py-3 text-[#EAEAEA] placeholder-[#EAEAEA]/40 focus:outline-none focus:border-[#FF6B35] transition-colors resize-none disabled:opacity-50"
            rows={3}
          />
        </div>

        <button
          type="submit"
          disabled={!prompt.trim() || isProcessing}
          className="w-full flex items-center justify-center space-x-2 bg-[#FF6B35] hover:bg-[#FF6B35]/90 disabled:bg-[#2A2A2A] disabled:text-[#EAEAEA]/30 text-white px-6 py-3 rounded-lg font-medium transition-colors"
        >
          {isProcessing ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Processing AI Edit...</span>
            </>
          ) : (
            <>
              <Send className="h-5 w-5" />
              <span>Execute AI Edit</span>
            </>
          )}
        </button>
      </form>

      {/* Example Prompts */}
      <div className="mt-6 pt-6 border-t border-[#2A2A2A]">
        <p className="text-sm text-[#EAEAEA]/70 mb-3">Example prompts:</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {[
            "Make a montage of 'money in the bank'",
            "Remove silence above 2 seconds",
            "Keep only Speaker 1",
            "Remove filler words (um, uh, you know)",
          ].map((example, i) => (
            <button
              key={i}
              onClick={() => setPrompt(example)}
              disabled={isProcessing}
              className="text-left text-sm text-[#FF6B35] hover:text-[#FF6B35]/80 disabled:opacity-30 transition-colors"
            >
              → {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PromptInput;
