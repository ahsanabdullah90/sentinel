import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

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

  useEffect(() => {
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
              onChange={(e) => { setName(e.target.value); }}
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
            <input
              value={url}
              onChange={(e) => { setUrl(e.target.value); }}
              placeholder="https://..."
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
              Keywords
            </label>
            <input
              value={keywords}
              onChange={(e) => { setKeywords(e.target.value); }}
              placeholder="e.g. AI, Cyber, Cloud"
              style={{ width: '100%' }}
            />
            <span style={{ display: 'block', marginTop: '6px', fontSize: '0.75rem', color: '#6366f1', lineHeight: '1.4' }}>
              💡 Separate keywords using commas (e.g. <code>RFP, Media, Cloud</code>). The agent will sequentially hunt for each keyword during search operations.
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
