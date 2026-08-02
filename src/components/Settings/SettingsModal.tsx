import { useState, useEffect } from 'react';
import { X, RefreshCw } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { AppSettings } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: AppSettings) => void;
  currentSettings: AppSettings;
}

export function SettingsModal({ isOpen, onClose, onSave, currentSettings }: Props) {
  const [provider, setProvider] = useState<'google' | 'ollama'>('google');
  const [googleApiKey, setGoogleApiKey] = useState('');
  const [googleModel, setGoogleModel] = useState('gemini-2.5-flash');
  const [ollamaModel, setOllamaModel] = useState('');
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const fetchModels = async (prov: 'google' | 'ollama') => {
    setLoadingModels(true);
    setModelError(null);
    try {
      if (prov === 'google') {
        if (!googleApiKey) {
          setModels([]);
          setModelError('Enter a Google Studio API key first');
          return;
        }
        const modelList = await invoke<string[]>('get_llm_models', {
          provider: 'google',
          ollamaUrl,
          googleApiKey,
        });
        setModels(modelList);
      } else {
        const modelList = await invoke<string[]>('get_llm_models', {
          provider: 'ollama',
          ollamaUrl,
          googleApiKey: '',
        });
        setModels(modelList);
      }
    } catch (err) {
      console.error('Error fetching models:', err);
      setModelError('Offline or unreachable');
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    if (currentSettings) {
      setProvider(currentSettings.provider === 'ollama' ? 'ollama' : 'google');
      setGoogleApiKey(currentSettings.googleApiKey || '');
      setGoogleModel(currentSettings.googleModel || 'gemini-2.5-flash');
      setOllamaModel(currentSettings.ollamaModel || '');
      setOllamaUrl(currentSettings.ollamaUrl || 'http://127.0.0.1:11434');
    }
  }, [currentSettings, isOpen]);

  useEffect(() => {
    if (isOpen) {
      void fetchModels(provider);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, provider, googleApiKey, ollamaUrl]);

  const handleSave = () => {
    onSave({
      provider,
      googleApiKey: googleApiKey.trim(),
      googleModel: googleModel.trim() || 'gemini-2.5-flash',
      ollamaModel,
      ollamaUrl,
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
          width: '440px',
          maxWidth: '92vw',
          padding: '20px',
          position: 'relative',
          backgroundColor: '#1e1e1e',
          color: '#fff',
          fontFamily: 'Inter, sans-serif',
          maxHeight: '90vh',
          overflowY: 'auto',
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
              AI Provider
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setProvider('google')}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '4px',
                  border: provider === 'google' ? '1px solid #4285F4' : '1px solid #333',
                  backgroundColor: provider === 'google' ? 'rgba(66,133,244,0.15)' : '#2a2a2a',
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                Google Gemini
              </button>
              <button
                onClick={() => setProvider('ollama')}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '4px',
                  border: provider === 'ollama' ? '1px solid #7C3AED' : '1px solid #333',
                  backgroundColor: provider === 'ollama' ? 'rgba(124,58,237,0.15)' : '#2a2a2a',
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                Ollama (Local)
              </button>
            </div>
          </div>

          {provider === 'google' ? (
            <>
              <div>
                <label
                  style={{
                    display: 'block',
                    marginBottom: '5px',
                    fontSize: '0.85rem',
                    color: '#8b90a0',
                  }}
                >
                  Google Studio API Key
                </label>
                <input
                  type="password"
                  value={googleApiKey}
                  onChange={(e) => setGoogleApiKey(e.target.value)}
                  placeholder="Paste your Google AI Studio API key"
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
                  Gemini Model
                </label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    value={googleModel}
                    onChange={(e) => setGoogleModel(e.target.value)}
                    placeholder="e.g. gemini-2.5-flash"
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
                  <button
                    type="button"
                    onClick={() => void fetchModels('google')}
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
                      style={{ animation: loadingModels ? 'spin 1s linear infinite' : 'none' }}
                    />
                  </button>
                </div>
                {models.length > 0 && (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '8px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#8b90a0' }}>Or select:</span>
                    <select
                      value={models.includes(googleModel) ? googleModel : ''}
                      onChange={(e) => {
                        if (e.target.value) setGoogleModel(e.target.value);
                      }}
                      style={{
                        flex: 1,
                        padding: '4px',
                        borderRadius: '4px',
                        border: '1px solid #333',
                        backgroundColor: '#2a2a2a',
                        color: '#fff',
                        fontSize: '0.8rem',
                        height: '30px',
                      }}
                    >
                      <option value="">-- Choose model --</option>
                      {models.map((m) => (
                        <option key={m} value={m} style={{ color: '#ffffff', backgroundColor: '#2a2a2a' }}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {modelError && (
                  <span style={{ fontSize: '0.75rem', color: '#ff3b30', marginTop: '4px', display: 'block' }}>
                    Google status: {modelError}
                  </span>
                )}
              </div>
            </>
          ) : (
            <>
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <input
                      value={ollamaModel}
                      onChange={(e) => setOllamaModel(e.target.value)}
                      placeholder="e.g. llama3.1:8b or custom-model"
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
                    <button
                      type="button"
                      onClick={() => void fetchModels('ollama')}
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
                        style={{ animation: loadingModels ? 'spin 1s linear infinite' : 'none' }}
                      />
                    </button>
                  </div>
                  {models.length > 0 && (
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.75rem', color: '#8b90a0' }}>Or select pulled model:</span>
                      <select
                        value={models.includes(ollamaModel) ? ollamaModel : ''}
                        onChange={(e) => {
                          if (e.target.value) setOllamaModel(e.target.value);
                        }}
                        style={{
                          flex: 1,
                          padding: '4px',
                          borderRadius: '4px',
                          border: '1px solid #333',
                          backgroundColor: '#2a2a2a',
                          color: '#fff',
                          fontSize: '0.8rem',
                          height: '30px',
                        }}
                      >
                        <option value="">-- Choose dynamic model --</option>
                        {models.map((m) => (
                          <option key={m} value={m} style={{ color: '#ffffff', backgroundColor: '#2a2a2a' }}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
                {modelError && (
                  <span style={{ fontSize: '0.75rem', color: '#ff3b30', marginTop: '4px', display: 'block' }}>
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
            </>
          )}

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
