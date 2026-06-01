import { useState, useEffect } from 'react';
import { X, AlertCircle, CheckCircle2 } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';

interface Portal {
  id: string;
  name: string;
  url: string;
  keywords: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (portal: Portal) => void;
  editingPortal?: Portal | null;
}

export function PortalConfigModal({ isOpen, onClose, onSave, editingPortal }: Props) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [keywords, setKeywords] = useState('');
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testSuccess, setTestSuccess] = useState(false);

  useEffect(() => {
    setTestError(null);
    setTestSuccess(false);
    setTesting(false);
    if (editingPortal) {
      setName(editingPortal.name);
      setUrl(editingPortal.url);
      setKeywords(editingPortal.keywords);
    } else {
      setName('');
      setUrl('');
      setKeywords('');
    }
  }, [editingPortal, isOpen]);

  if (!isOpen) return null;

  async function handleTestConnection() {
    if (!url.trim()) {
      setTestError('Please enter a URL first.');
      return;
    }
    setTesting(true);
    setTestError(null);
    setTestSuccess(false);
    try {
      await invoke('detect_portal', { url });
      setTestSuccess(true);
    } catch (err: any) {
      console.error('Portal detection failed:', err);
      setTestError(err?.message || String(err) || 'Failed to detect portal.');
    } finally {
      setTesting(false);
    }
  }

  function handleSave() {
    onSave({
      id: editingPortal?.id ?? Math.random().toString(36).substr(2, 9),
      name,
      url,
      keywords,
    });
    onClose();
  }

  return (
    <div
      className="modal-backdrop"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(0,0,0,0.7)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
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
        <h3 style={{ marginTop: 0 }}>{editingPortal ? 'Edit Portal' : 'Add Portal'}</h3>
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
              Portal Name
            </label>
            <input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
              placeholder="e.g. SAM.gov"
              style={{ width: '100%' }}
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
              URL
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                }}
                placeholder="https://..."
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleTestConnection}
                disabled={testing}
                style={{ whiteSpace: 'nowrap', padding: '6px 12px' }}
              >
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
            {testSuccess && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--success-color)', fontSize: '0.75rem', marginTop: '6px' }}>
                <CheckCircle2 size={12} />
                <span>Portal detected successfully!</span>
              </div>
            )}
            {testError && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#ff453a', fontSize: '0.75rem', marginTop: '6px' }}>
                <AlertCircle size={12} />
                <span>{testError}</span>
              </div>
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
              Keywords
            </label>
            <input
              value={keywords}
              onChange={(e) => {
                setKeywords(e.target.value);
              }}
              placeholder="e.g. AI, Cyber, Cloud"
              style={{ width: '100%' }}
            />
            <span
              style={{
                display: 'block',
                marginTop: '6px',
                fontSize: '0.75rem',
                color: '#6366f1',
                lineHeight: '1.4',
              }}
            >
              💡 Separate keywords using commas (e.g. <code>RFP, Media, Cloud</code>). The agent
              will sequentially hunt for each keyword during search operations.
            </span>
          </div>
          <div
            style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}
          >
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleSave}>
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
