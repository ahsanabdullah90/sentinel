import { useState, useEffect } from 'react';
import { X, RefreshCw } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: { ollamaModel: string; ollamaUrl: string }) => void;
  currentSettings: { ollamaModel: string; ollamaUrl: string };
}

export function SettingsModal({ isOpen, onClose, onSave, currentSettings }: Props) {
  const [ollamaModel, setOllamaModel] = useState('phi3');
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
  const [customModel, setCustomModel] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const fetchModels = async (url: string) => {
    setLoadingModels(true);
    setModelError(null);
    try {
      const modelList = await invoke<string[]>('get_ollama_models', { url });
      setModels(modelList);
      if (modelList.length > 0) {
        if (!modelList.includes(ollamaModel)) {
          setOllamaModel(modelList[0]);
        }
      }
    } catch (err) {
      console.error('Error fetching Ollama models:', err);
      setModelError('Offline or unreachable');
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    if (currentSettings) {
      setOllamaModel(currentSettings.ollamaModel);
      setOllamaUrl(currentSettings.ollamaUrl);
    }
  }, [currentSettings, isOpen]);

  useEffect(() => {
    if (isOpen) {
      void fetchModels(ollamaUrl);
    }
  }, [isOpen, ollamaUrl]);

  const handleSave = () => {
    const finalModel = showCustomInput ? customModel : ollamaModel;
    onSave({ ollamaModel: finalModel, ollamaUrl });
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
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {!showCustomInput && models.length > 0 ? (
                <select
                  value={ollamaModel}
                  onChange={(e) => {
                    if (e.target.value === '__custom__') {
                      setShowCustomInput(true);
                    } else {
                      setOllamaModel(e.target.value);
                    }
                  }}
                  style={{
                    flex: 1,
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid #333',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    boxSizing: 'border-box',
                    height: '38px',
                  }}
                >
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                  <option value="__custom__">+ Enter Custom Model Name...</option>
                </select>
              ) : (
                <input
                  value={showCustomInput ? customModel : ollamaModel}
                  onChange={(e) => {
                    if (showCustomInput) {
                      setCustomModel(e.target.value);
                    } else {
                      setOllamaModel(e.target.value);
                    }
                  }}
                  placeholder="e.g. phi3, llama3"
                  style={{
                    flex: 1,
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid #333',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    boxSizing: 'border-box',
                    height: '38px',
                  }}
                />
              )}
              <button
                type="button"
                onClick={() => {
                  setShowCustomInput(false);
                  void fetchModels(ollamaUrl);
                }}
                disabled={loadingModels}
                style={{
                  height: '38px',
                  padding: '0 12px',
                  borderRadius: '4px',
                  border: '1px solid #333',
                  backgroundColor: '#2a2a2a',
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title="Refresh Model List"
              >
                <RefreshCw
                  size={14}
                  style={{
                    animation: loadingModels ? 'spin 1s linear infinite' : 'none',
                  }}
                />
              </button>
            </div>
            {showCustomInput && (
              <div style={{ marginTop: '8px' }}>
                <input
                  value={customModel}
                  onChange={(e) => setCustomModel(e.target.value)}
                  placeholder="Enter custom model name..."
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
                <button
                  type="button"
                  onClick={() => setShowCustomInput(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#007aff',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    marginTop: '5px',
                    padding: 0,
                  }}
                >
                  Back to List
                </button>
              </div>
            )}
            {modelError && (
              <span
                style={{
                  fontSize: '0.75rem',
                  color: '#ff3b30',
                  marginTop: '4px',
                  display: 'block',
                }}
              >
                Ollama status: {modelError} (Check model tags)
              </span>
            )}
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
          <div
            style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}
          >
            <button className="btn btn-secondary" onClick={onClose} style={{ padding: '8px 15px' }}>
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
