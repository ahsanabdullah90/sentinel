import { useState, useEffect } from 'react';
import { X, Cpu, Cloud, Key } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: any) => void;
  currentSettings: any;
}

export function SettingsModal({ isOpen, onClose, onSave, currentSettings }: Props) {
  const [ollamaModel, setOllamaModel] = useState('phi3');
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
  const [processingMode, setProcessingMode] = useState<'local' | 'cloud'>('local');
  const [cloudProvider, setCloudProvider] = useState<'gemini' | 'claude' | 'deepseek'>('gemini');
  const [apiKey, setApiKey] = useState('');

  useEffect(() => {
    if (currentSettings) {
      setOllamaModel(currentSettings.ollamaModel || 'phi3');
      setOllamaUrl(currentSettings.ollamaUrl || 'http://127.0.0.1:11434');
      setProcessingMode(currentSettings.processingMode || 'local');
      setCloudProvider(currentSettings.cloudProvider || 'gemini');
      setApiKey(currentSettings.apiKey || '');
    }
  }, [currentSettings, isOpen]);

  const handleSave = () => {
    onSave({
      ollamaModel,
      ollamaUrl,
      processingMode,
      cloudProvider,
      apiKey
    });
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
          width: '450px',
          padding: '25px',
          position: 'relative',
          backgroundColor: '#1e1e1e',
          color: '#fff',
          fontFamily: 'Inter, sans-serif',
          maxHeight: '90vh',
          overflowY: 'auto'
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
        <h3 style={{ marginTop: 0, marginBottom: '20px' }}>System Settings</h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Processing Mode Toggle */}
          <div>
            <label style={{ display: 'block', marginBottom: '10px', fontSize: '0.85rem', color: '#8b90a0' }}>
              Processing Mode
            </label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => setProcessingMode('local')}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: '6px',
                  border: '1px solid ' + (processingMode === 'local' ? 'var(--accent-color)' : '#333'),
                  backgroundColor: processingMode === 'local' ? 'rgba(0,122,255,0.1)' : '#2a2a2a',
                  color: processingMode === 'local' ? 'var(--accent-color)' : '#8b90a0',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  fontWeight: 600
                }}
              >
                <Cpu size={16} /> Local (Privacy)
              </button>
              <button
                onClick={() => setProcessingMode('cloud')}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: '6px',
                  border: '1px solid ' + (processingMode === 'cloud' ? 'var(--accent-color)' : '#333'),
                  backgroundColor: processingMode === 'cloud' ? 'rgba(0,122,255,0.1)' : '#2a2a2a',
                  color: processingMode === 'cloud' ? 'var(--accent-color)' : '#8b90a0',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  fontWeight: 600
                }}
              >
                <Cloud size={16} /> Cloud (Power)
              </button>
            </div>
          </div>

          {processingMode === 'local' ? (
            <>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
                  Ollama Model Name
                </label>
                <input
                  value={ollamaModel}
                  onChange={(e) => setOllamaModel(e.target.value)}
                  placeholder="e.g. phi3, llama3"
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '4px',
                    border: '1px solid #333',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
                  Ollama API URL
                </label>
                <input
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  placeholder="e.g. http://127.0.0.1:11434"
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '4px',
                    border: '1px solid #333',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
                  Cloud Provider
                </label>
                <select
                  value={cloudProvider}
                  onChange={(e) => setCloudProvider(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '4px',
                    border: '1px solid #333',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="claude">Anthropic Claude</option>
                  <option value="deepseek">DeepSeek</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
                  API Key
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your API key"
                    style={{
                      width: '100%',
                      padding: '10px 10px 10px 35px',
                      borderRadius: '4px',
                      border: '1px solid #333',
                      backgroundColor: '#2a2a2a',
                      color: '#fff',
                      boxSizing: 'border-box',
                    }}
                  />
                  <Key size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: '#8b90a0' }} />
                </div>
              </div>
            </>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button className="btn btn-secondary" onClick={onClose} style={{ padding: '10px 20px' }}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSave}
              style={{ padding: '10px 20px' }}
            >
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
