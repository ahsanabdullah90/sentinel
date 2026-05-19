import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: { ollamaModel: string; ollamaUrl: string }) => void;
  currentSettings: { ollamaModel: string; ollamaUrl: string };
}

export function SettingsModal({ isOpen, onClose, onSave, currentSettings }: Props) {
  const [ollamaModel, setOllamaModel] = useState('phi3');
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');

  useEffect(() => {
    if (currentSettings) {
      setOllamaModel(currentSettings.ollamaModel);
      setOllamaUrl(currentSettings.ollamaUrl);
    }
  }, [currentSettings, isOpen]);

  const handleSave = () => {
    onSave({ ollamaModel, ollamaUrl });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        className="modal-content card glass"
        style={{
          width: '400px',
          padding: '20px',
          position: 'relative',
          backgroundColor: '#1e1e1e',
          color: '#fff',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '15px',
            right: '15px',
            background: 'none',
            border: 'none',
            color: '#8b90a0',
            cursor: 'pointer',
          }}
        >
          <X size={18} />
        </button>
        <h3 style={{ marginTop: 0 }}>System Settings</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '15px' }}>
          <div>
            <label
              style={{
                display: 'block',
                marginBottom: '5px',
                fontSize: '0.85rem',
                color: '#8b90a0',
              }}
            >
              Ollama Model Name
            </label>
            <input
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              placeholder="e.g. phi3, llama3"
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid #333',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label
              style={{
                display: 'block',
                marginBottom: '5px',
                fontSize: '0.85rem',
                color: '#8b90a0',
              }}
            >
              Ollama API URL
            </label>
            <input
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="e.g. http://127.0.0.1:11434"
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid #333',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button
              className="btn btn-secondary"
              onClick={onClose}
              style={{ padding: '8px 15px' }}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSave}
              style={{ padding: '8px 15px' }}
            >
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
