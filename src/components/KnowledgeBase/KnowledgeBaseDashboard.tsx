import { useState, useEffect } from 'react';
import {
  Database,
  Plus,
  Trash2,
  Tag,
  Calendar,
  Eye,
  X,
  BookOpen,
  AlertCircle,
  Paperclip,
  RefreshCw,
  Image,
} from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';

export interface KnowledgeItem {
  id: string;
  title: string;
  content: string;
  type: string; // 'text' | 'file'
  tags: string;
  created_at: string;
}

export interface KnowledgeBaseProps {
  settings?: {
    ollamaModel: string;
    ollamaUrl: string;
  };
}

export function KnowledgeBaseDashboard({ settings }: KnowledgeBaseProps) {
  const ollamaModel = settings?.ollamaModel || 'phi3';
  const ollamaUrl = settings?.ollamaUrl || 'http://127.0.0.1:11434';

  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Add item form state
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newTags, setNewTags] = useState('');
  const [newType, setNewType] = useState('text');

  // File attachments state
  const [attachedFileBytes, setAttachedFileBytes] = useState<Uint8Array | null>(null);
  const [attachedFileName, setAttachedFileName] = useState('');
  const [isExtractingPdf, setIsExtractingPdf] = useState(false);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);

  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAttachedFileName(file.name);
    setIsAnalyzingImage(true);

    if (!newTitle.trim()) {
      setNewTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
    setNewType('file');

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const arrayBuffer = event.target?.result as ArrayBuffer;
        const bytes = new Uint8Array(arrayBuffer);
        setAttachedFileBytes(bytes);

        // Invoke local vision model to describe the diagram or image
        const description = await invoke<string>('generate_vision_description', {
          imageBytes: Array.from(bytes),
          model: ollamaModel,
          url: ollamaUrl,
        });
        setNewContent(description);
      } catch (err) {
        console.error('Failed to extract image content:', err);
      } finally {
        setIsAnalyzingImage(false);
      }
    };
    reader.readAsArrayBuffer(file);
  };

  // Preview item state
  const [previewItem, setPreviewItem] = useState<KnowledgeItem | null>(null);

  useEffect(() => {
  void loadKnowledgeItems();
}, []);

useEffect(() => {
  return () => {
    setPreviewItem(null);
  };
}, []);







  async function loadKnowledgeItems() {
    setLoading(true);
    try {
      const result = await invoke<KnowledgeItem[]>('get_knowledge_base');
      setItems(result);
    } catch (err) {
      console.error('Failed to load knowledge base items:', err);
    } finally {
      setLoading(false);
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAttachedFileName(file.name);
    setIsExtractingPdf(true);

    if (!newTitle.trim()) {
      setNewTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
    setNewType('file');

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const arrayBuffer = event.target?.result as ArrayBuffer;
        const bytes = new Uint8Array(arrayBuffer);
        setAttachedFileBytes(bytes);

        // Extract text from bytes by converting Uint8Array to a normal standard array
        const text = await invoke<string>('extract_pdf_text_from_bytes', {
          bytes: Array.from(bytes),
        });
        setNewContent(text);
      } catch (err) {
        console.error('Failed to extract PDF text:', err);
      } finally {
        setIsExtractingPdf(false);
      }
    };
    reader.readAsArrayBuffer(file);
  };

  async function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;

    try {
      const id = Math.random().toString(36).substring(2, 11);
      // Note: Backend automatically generates timestamp on insert, so we don't need to pass it
      await invoke('save_knowledge_item', {
        id,
        title: newTitle.trim(),
        content: newContent.trim(),
        itemType: newType,
        tags: newTags.trim() || null,
        fileName: attachedFileName || null,
        fileBytes: attachedFileBytes ? Array.from(attachedFileBytes) : null,
      });

      // Reset form
      setNewTitle('');
      setNewContent('');
      setNewTags('');
      setAttachedFileBytes(null);
      setAttachedFileName('');
      setIsAdding(false);

      // Reload
      void loadKnowledgeItems();
    } catch (err) {
      console.error('Failed to add knowledge item:', err);
    }
  }

  async function handleDeleteItem(id: string) {
    if (
      !confirm(
        'Are you sure you want to delete this knowledge profile? This will remove it from context used in draft proposals.'
      )
    ) {
      return;
    }
    try {
      await invoke('delete_knowledge_item', { id });
      void loadKnowledgeItems();
      if (previewItem?.id === id) {
        setPreviewItem(null);
      }
    } catch (err) {
      console.error('Failed to delete knowledge item:', err);
    }
  }

  const filteredItems = items.filter((item) => {
    const query = searchQuery.toLowerCase();
    return (
      item.title.toLowerCase().includes(query) ||
      item.content.toLowerCase().includes(query) ||
      item.tags.toLowerCase().includes(query)
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Title block */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '15px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Database size={24} style={{ color: 'var(--accent-color)' }} />
          <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 600, color: '#fff' }}>
            Knowledge Base Studio
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
              className="btn btn-primary"
              onClick={() => setIsAdding(!isAdding)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'linear-gradient(135deg, #007aff 0%, #0051b3 100%)',
                border: 'none',
              }}
            >
              {isAdding ? <X size={16} /> : <Plus size={16} />}
              {isAdding ? 'Cancel' : 'Add Knowledge Profile'}
            </button>
        </div>
      </div>

      {/* Description Banner */}
      <div
        className="card glass"
        style={{
          border: '1px solid rgba(0, 122, 255, 0.15)',
          padding: '15px 20px',
          display: 'flex',
          gap: '15px',
          alignItems: 'center',
        }}
      >
        <BookOpen size={28} style={{ color: 'var(--accent-color)', flexShrink: 0 }} />
        <div style={{ textAlign: 'left' }}>
          <h4 style={{ margin: '0 0 4px 0', color: '#fff', fontSize: '0.95rem' }}>
            Proposal Drafting Context System
          </h4>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8b90a0', lineHeight: '1.4' }}>
            Feed Sentinel your company's core competencies, personnel bios, technical capabilities,
            case studies, and past performance reviews. When generating proposal drafts for new
            opportunities, select which items to attach to the AI context to craft highly customized
            and factual bids.
          </p>
        </div>
      </div>

      {/* Adding form */}
      {isAdding && (
        <div
          className="card glass"
          style={{ border: '1px solid var(--accent-color)', animation: 'fadeIn 0.2s' }}
        >
          <h3
            style={{
              margin: '0 0 15px 0',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              paddingBottom: '10px',
            }}
          >
            Create Knowledge Profile
          </h3>
          <form
            onSubmit={handleAddItem}
            style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}
          >
            <div className="input-group" style={{ margin: 0 }}>
              <label
                style={{
                  fontSize: '0.85rem',
                  color: '#8b90a0',
                  marginBottom: '5px',
                  textAlign: 'left',
                }}
              >
                Profile Title
              </label>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g., Company Overview & Core Services, Cybersecurity Case Study..."
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div className="input-group" style={{ margin: 0 }}>
                <label
                  style={{
                    fontSize: '0.85rem',
                    color: '#8b90a0',
                    marginBottom: '5px',
                    textAlign: 'left',
                  }}
                >
                  Information Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  style={{
                    color: '#000000',
                    backgroundColor: '#ffffff',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    padding: '10px',
                    borderRadius: '8px',
                    outline: 'none',
                    fontWeight: '500',
                  }}
                >
                  <option value="text" style={{ color: '#000000', backgroundColor: '#ffffff' }}>General Text / Capability Statement</option>
                  <option value="resume" style={{ color: '#000000', backgroundColor: '#ffffff' }}>Resume / Core Personnel Bio</option>
                  <option value="case-study" style={{ color: '#000000', backgroundColor: '#ffffff' }}>Case Study / Past Performance</option>
                  <option value="proposal-template" style={{ color: '#000000', backgroundColor: '#ffffff' }}>Proposal Shell / Boilerplate</option>
                </select>
              </div>
              <div className="input-group" style={{ margin: 0 }}>
                <label
                  style={{
                    fontSize: '0.85rem',
                    color: '#8b90a0',
                    marginBottom: '5px',
                    textAlign: 'left',
                  }}
                >
                  Search Tags (Comma-separated)
                </label>
                <input
                  type="text"
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  placeholder="e.g., cloud, software, aws, key-personnel"
                />
              </div>
            </div>

            <div className="input-group" style={{ margin: 0 }}>
              <label
                style={{
                  fontSize: '0.85rem',
                  color: '#8b90a0',
                  marginBottom: '5px',
                  textAlign: 'left',
                }}
              >
                Or Attach PDF / Image Source File
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => document.getElementById('kb-pdf-file-upload')?.click()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                  disabled={isExtractingPdf || isAnalyzingImage}
                >
                  <Paperclip size={14} />
                  Attach PDF
                </button>
                <input
                  type="file"
                  id="kb-pdf-file-upload"
                  accept=".pdf"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => document.getElementById('kb-img-file-upload')?.click()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                  disabled={isExtractingPdf || isAnalyzingImage}
                >
                  <Image size={14} />
                  Attach Image
                </button>
                <input
                  type="file"
                  id="kb-img-file-upload"
                  accept="image/*"
                  onChange={handleImageChange}
                  style={{ display: 'none' }}
                />

                {attachedFileName && (
                  <span
                    style={{
                      fontSize: '0.85rem',
                      color: '#30d158',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                    }}
                  >
                    ✓ {attachedFileName}
                  </span>
                )}
                {isExtractingPdf && (
                  <span
                    style={{
                      fontSize: '0.85rem',
                      color: 'var(--accent-color)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                    }}
                  >
                    <RefreshCw
                      size={14}
                      className="spin"
                      style={{ animation: 'spin 1s linear infinite' }}
                    />
                    Extracting PDF text locally...
                  </span>
                )}
                {isAnalyzingImage && (
                  <span
                    style={{
                      fontSize: '0.85rem',
                      color: 'var(--accent-color)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                    }}
                  >
                    <RefreshCw
                      size={14}
                      className="spin"
                      style={{ animation: 'spin 1s linear infinite' }}
                    />
                    Analyzing image layout locally...
                  </span>
                )}
              </div>
            </div>

            <div className="input-group" style={{ margin: 0 }}>
              <label
                style={{
                  fontSize: '0.85rem',
                  color: '#8b90a0',
                  marginBottom: '5px',
                  textAlign: 'left',
                }}
              >
                Profile Content (The underlying basis for the draft proposals)
              </label>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="Paste the core details, company credentials, or project descriptions here..."
                required
                style={{
                  minHeight: '200px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: '#fff',
                  padding: '12px',
                  fontFamily: 'inherit',
                  fontSize: '0.9rem',
                  outline: 'none',
                  resize: 'vertical',
                }}
              />
            </div>

            <div
              style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '5px' }}
            >
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsAdding(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Save to Database
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Main Panel Search & Grid */}
      <div className="card glass" style={{ minHeight: '400px' }}>
        {/* Search */}
        <div style={{ display: 'flex', position: 'relative', marginBottom: '20px' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search knowledge profiles by title, tags or content..."
            style={{ width: '100%', paddingLeft: '15px' }}
          />
        </div>

        {loading ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: '#8b90a0' }}>
            Loading knowledge profiles...
          </div>
        ) : filteredItems.length === 0 ? (
          <div
            style={{
              padding: '80px 0',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <AlertCircle size={32} style={{ color: '#8b90a0' }} />
            <span style={{ color: '#8b90a0' }}>
              {searchQuery
                ? 'No profiles match your search filter.'
                : 'Your Knowledge Base is empty.'}
            </span>
            {!isAdding && !searchQuery && (
              <button
                className="btn btn-sm btn-ghost"
                style={{ marginTop: '10px' }}
                onClick={() => setIsAdding(true)}
              >
                Add your first profile
              </button>
            )}
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
              gap: '20px',
              textAlign: 'left',
            }}
          >
            {filteredItems.map((item) => (
              <div
                key={item.id}
                className="card"
                style={{
                  margin: 0,
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '15px',
                  transition: 'all 0.25s',
                  position: 'relative',
                  overflow: 'hidden',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent-color)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                {/* Header info */}
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: '8px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.7rem',
                        backgroundColor: 'rgba(0,122,255,0.1)',
                        color: 'var(--accent-color)',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                        letterSpacing: '0.05em',
                      }}
                    >
                      {item.type}
                    </span>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button
                        onClick={() => setPreviewItem(item)}
                        title="View Full Profile"
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#8b90a0',
                          cursor: 'pointer',
                          padding: '2px',
                        }}
                      >
                        <Eye size={16} />
                      </button>
                      <button
                        onClick={() => void handleDeleteItem(item.id)}
                        title="Delete Profile"
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#ff3b30',
                          cursor: 'pointer',
                          padding: '2px',
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>

                  <h4
                    style={{
                      margin: '0 0 10px 0',
                      fontSize: '1.05rem',
                      color: '#fff',
                      fontWeight: 600,
                    }}
                  >
                    {item.title}
                  </h4>

                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.85rem',
                      color: '#8b90a0',
                      lineHeight: '1.45',
                      display: '-webkit-box',
                      WebkitLineClamp: 4,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {item.content}
                  </p>
                </div>

                {/* Footer metadata */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    paddingTop: '10px',
                  }}
                >
                  {item.tags && (
                    <div
                      style={{
                        display: 'flex',
                        gap: '5px',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                      }}
                    >
                      <Tag size={12} style={{ color: '#8b90a0' }} />
                      {item.tags.split(',').map((tag, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: '0.7rem',
                            color: '#8b90a0',
                            backgroundColor: 'rgba(255,255,255,0.05)',
                            padding: '1px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          {tag.trim()}
                        </span>
                      ))}
                    </div>
                  )}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontSize: '0.72rem',
                      color: '#8b90a0',
                    }}
                  >
                    <Calendar size={12} />
                    <span>Added {item.created_at}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* View full content Modal overlay */}
      {previewItem && ( 
        <div
          onClick={() => setPreviewItem(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0,0,0,0.85)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1100,
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
          }}
        >
          <div
            className="card glass"
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '90%',
              maxWidth: '700px',
              maxHeight: '80vh',
              display: 'flex',
              flexDirection: 'column',
              padding: '25px',
              backgroundColor: '#111112',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              overflow: 'hidden',
            }}
          >
        
            {/* Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '15px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                paddingBottom: '10px',
                textAlign: 'left',
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: '0.7rem',
                    backgroundColor: 'rgba(0,122,255,0.1)',
                    color: 'var(--accent-color)',
                    padding: '2px 8px',
                    borderRadius: '10px',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                  }}
                >
                  {previewItem.type}
                </span>
                <h3 style={{ margin: '5px 0 0 0', fontSize: '1.3rem', color: '#fff' }}>
                  {previewItem.title}
                </h3>
              </div>
              <button
                onClick={() => setPreviewItem(null)}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  color: '#8b90a0',
                  cursor: 'pointer',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Scrollable body */}
            <div style={{ flex: 1, overflowY: 'auto', textAlign: 'left', paddingRight: '10px' }}>
              <div
                style={{
                  fontSize: '0.95rem',
                  color: '#e5e2e3',
                  whiteSpace: 'pre-wrap',
                  lineHeight: '1.6',
                  fontFamily: 'inherit',
                }}
              >
                {previewItem.content}
              </div>
            </div>

            {/* Footer */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '20px',
                paddingTop: '15px',
                borderTop: '1px solid rgba(255,255,255,0.05)',
                fontSize: '0.8rem',
                color: '#8b90a0',
              }}
            >
              <span>Created: {previewItem.created_at}</span>
              <button className="btn btn-secondary btn-sm" onClick={() => setPreviewItem(null)}>
                Close View
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
