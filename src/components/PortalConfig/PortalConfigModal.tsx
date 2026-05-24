import { useState, useEffect } from 'react';
import { X, Lock, Globe, Search } from 'lucide-react';

interface Portal {
  id: string;
  name: string;
  url: string;
  keywords: string;
  auth_method?: string;
  username?: string;
  password?: string;
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
  const [authMethod, setAuthMethod] = useState('public');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (editingPortal) {
      setName(editingPortal.name);
      setUrl(editingPortal.url);
      setKeywords(editingPortal.keywords);
      setAuthMethod(editingPortal.auth_method || 'public');
      setUsername(editingPortal.username || '');
      setPassword(editingPortal.password || '');
    } else {
      setName('');
      setUrl('');
      setKeywords('');
      setAuthMethod('public');
      setUsername('');
      setPassword('');
    }
  }, [editingPortal, isOpen]);

  if (!isOpen) return null;

  function handleSave() {
    onSave({
      id: editingPortal?.id ?? Math.random().toString(36).substr(2, 9),
      name,
      url,
      keywords,
      auth_method: authMethod,
      username,
      password
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
        backdropFilter: 'blur(4px)'
      }}
    >
      <div
        className="modal-content card glass"
        style={{
          width: '450px',
          padding: '25px',
          position: 'relative',
          backgroundColor: '#1e1e1e',
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
        <h3 style={{ marginTop: 0, color: '#fff' }}>{editingPortal ? 'Edit Portal' : 'Add New RFP Portal'}</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
              Portal Name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. SAM.gov, Rozee.pk"
              style={{ width: '100%', backgroundColor: '#2a2a2a', border: '1px solid #333', color: '#fff', padding: '10px', borderRadius: '4px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
              Base URL
            </label>
            <div style={{ position: 'relative' }}>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://..."
                style={{ width: '100%', backgroundColor: '#2a2a2a', border: '1px solid #333', color: '#fff', padding: '10px 10px 10px 35px', borderRadius: '4px' }}
              />
              <Globe size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: '#8b90a0' }} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
              Authentication Method
            </label>
            <select
              value={authMethod}
              onChange={(e) => setAuthMethod(e.target.value)}
              style={{ width: '100%', backgroundColor: '#2a2a2a', border: '1px solid #333', color: '#fff', padding: '10px', borderRadius: '4px' }}
            >
              <option value="public">Public (No Login)</option>
              <option value="credential">Username/Password</option>
            </select>
          </div>

          {authMethod === 'credential' && (
            <div style={{ padding: '15px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid #333', display: 'flex', flexDirection: 'column', gap: '10px' }}>
               <div>
                  <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.75rem', color: '#8b90a0' }}>Username / Email</label>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter username"
                    style={{ width: '100%', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', padding: '8px', borderRadius: '4px' }}
                  />
               </div>
               <div>
                  <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.75rem', color: '#8b90a0' }}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter password"
                      style={{ width: '100%', backgroundColor: '#1a1a1a', border: '1px solid #333', color: '#fff', padding: '8px 8px 8px 30px', borderRadius: '4px' }}
                    />
                    <Lock size={14} style={{ position: 'absolute', left: '8px', top: '10px', color: '#8b90a0' }} />
                  </div>
                  <span style={{ fontSize: '0.65rem', color: '#6366f1', marginTop: '5px', display: 'block' }}>🔐 Stored in SQLCipher encrypted vault</span>
               </div>
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
              Search Keywords
            </label>
            <div style={{ position: 'relative' }}>
              <input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="AI, Cyber, Cloud"
                style={{ width: '100%', backgroundColor: '#2a2a2a', border: '1px solid #333', color: '#fff', padding: '10px 10px 10px 35px', borderRadius: '4px' }}
              />
              <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: '#8b90a0' }} />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleSave} style={{ paddingLeft: '20px', paddingRight: '20px' }}>
              Save Portal
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
