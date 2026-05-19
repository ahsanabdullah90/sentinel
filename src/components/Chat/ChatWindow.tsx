import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Send, Bot, User, Loader } from 'lucide-react';
import sentinelKnowledge from './sentinel_knowledge.md?raw';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  settings: {
    ollamaModel: string;
    ollamaUrl: string;
  };
}

export function ChatWindow({ settings }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I am your AI assistant. How can I help you with RFPs today?',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const systemPrompt = `You are the Sentinel AI Assistant. Refer to the official Sentinel Product Guide below to guide the user on Sentinel's capabilities and limitations. Keep your answers concise, helpful, and technically accurate.

======================================
SENTINEL PRODUCT GUIDE:
${sentinelKnowledge}
======================================`;

      const fullPrompt = `${systemPrompt}\n\nUser Question: ${input}\n\nAssistant Response:`;

      const response = await invoke('generate_chat_response', {
        prompt: fullPrompt,
        model: settings.ollamaModel,
        url: settings.ollamaUrl,
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: response as string }]);
    } catch (error) {
      console.error('Chat failed:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: Failed to get response from AI.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="card glass chat-window"
      style={{ display: 'flex', flexDirection: 'column', height: '400px' }}
    >
      <h3>AI Assistant</h3>
      <div
        className="messages"
        style={{
          flex: 1,
          overflowY: 'auto',
          marginBottom: '10px',
          padding: '10px',
          backgroundColor: 'rgba(0,0,0,0.2)',
          borderRadius: '8px',
        }}
      >
        {messages.map((msg, index) => (
          <div
            key={index}
            style={{ display: 'flex', gap: '10px', marginBottom: '10px', alignItems: 'flex-start' }}
          >
            {msg.role === 'assistant' ? (
              <Bot size={18} style={{ color: 'var(--accent-color)' }} />
            ) : (
              <User size={18} />
            )}
            <div
              style={{
                backgroundColor:
                  msg.role === 'assistant' ? 'rgba(255,255,255,0.05)' : 'rgba(0,122,255,0.1)',
                padding: '8px 12px',
                borderRadius: '8px',
                maxWidth: '80%',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <Bot size={18} style={{ color: 'var(--accent-color)' }} />
            <div
              style={{
                backgroundColor: 'rgba(255,255,255,0.05)',
                padding: '8px 12px',
                borderRadius: '8px',
              }}
            >
              <Loader size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />{' '}
              Thinking...
            </div>
          </div>
        )}
      </div>
      <div className="input-group" style={{ display: 'flex', gap: '10px' }}>
        <input
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
          }}
          placeholder="Ask a question..."
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              void handleSend();
            }
          }}
          style={{ flex: 1 }}
          disabled={loading}
        />
        <button
          className="btn btn-primary"
          onClick={() => {
            void handleSend();
          }}
          disabled={loading}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
