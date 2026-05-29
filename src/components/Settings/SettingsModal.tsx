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
  const [ollamaModel, setOllamaModel] = useState('');
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
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
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
                disabled={models.length === 0}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                  backgroundColor: models.length === 0 ? '#f0f0f0' : '#ffffff',
                  color: models.length === 0 ? '#888888' : '#000000',
                  boxSizing: 'border-box',
                  height: '38px',
                  fontWeight: '500',
                }}
              >
                {models.length > 0 ? (
                  models.map((m) => (
                    <option key={m} value={m} style={{ color: '#000000', backgroundColor: '#ffffff' }}>
                      {m}
                    </option>
                  ))
                ) : (
                  <option value="" style={{ color: '#888888', backgroundColor: '#ffffff' }}>
                    {loadingModels ? 'Fetching models...' : 'No models found (Ollama offline)'}
                  </option>
                )}
              </select>
              <button
                type="button"
                onClick={() => {
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
