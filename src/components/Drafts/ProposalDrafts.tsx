import { useState, useEffect } from 'react';
import { FileText, Calendar, Eye, Trash2, Edit3, X, Copy, Check, Save } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';

export interface ProposalDraft {
  id: string;
  opportunity_id: string;
  title: string;
  content: string;
  created_at: string;
  opp_title?: string;
  opp_portal?: string;
  opp_org?: string;
}

export function ProposalDrafts() {
  const [drafts, setDrafts] = useState<ProposalDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Interactive editing and preview
  const [activeDraft, setActiveDraft] = useState<ProposalDraft | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [copySuccess, setCopySuccess] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    void loadDrafts();
  }, []);

  async function loadDrafts() {
    setLoading(true);
    try {
      const result = await invoke<ProposalDraft[]>('get_proposal_drafts');
      setDrafts(result);
    } catch (err) {
      console.error('Failed to load proposal drafts:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteDraft(id: string) {
    if (
      !confirm('Are you sure you want to delete this proposal draft? This action cannot be undone.')
    ) {
      return;
    }
    try {
      await invoke('delete_proposal_draft', { id });
      void loadDrafts();
      if (activeDraft?.id === id) {
        setActiveDraft(null);
      }
    } catch (err) {
      console.error('Failed to delete proposal draft:', err);
    }
  }

  async function handleUpdateDraft() {
    if (!activeDraft) return;
    try {
      await invoke('update_proposal_draft', {
        id: activeDraft.id,
        title: editTitle,
        content: editContent,
      });

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      setIsEditing(false);

      // Update local state
      setDrafts((prev) =>
        prev.map((d) =>
          d.id === activeDraft.id ? { ...d, title: editTitle, content: editContent } : d
        )
      );
      setActiveDraft((prev) => (prev ? { ...prev, title: editTitle, content: editContent } : null));
    } catch (err) {
      console.error('Failed to update draft:', err);
    }
  }

  const handleOpenDraft = (draft: ProposalDraft) => {
    setActiveDraft(draft);
    setEditContent(draft.content);
    setEditTitle(draft.title);
    setIsEditing(false);
  };

  const handleCopy = () => {
    if (!activeDraft) return;
    navigator.clipboard.writeText(editContent);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const filteredDrafts = drafts.filter((draft) => {
    const query = searchQuery.toLowerCase();
    return (
      draft.title.toLowerCase().includes(query) ||
      draft.content.toLowerCase().includes(query) ||
      (draft.opp_title && draft.opp_title.toLowerCase().includes(query)) ||
      (draft.opp_org && draft.opp_org.toLowerCase().includes(query))
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', textAlign: 'left' }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <FileText size={24} style={{ color: 'var(--accent-color)' }} />
        <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 600, color: '#fff' }}>
          Saved Proposal Drafts
        </h2>
      </div>

      {/* Main Container */}
      <div className="card glass" style={{ minHeight: '450px' }}>
        {/* Search Input */}
        <div style={{ display: 'flex', position: 'relative', marginBottom: '20px' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search proposal drafts by keyword, client or opportunity title..."
            style={{ width: '100%', paddingLeft: '15px' }}
          />
        </div>

        {loading ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: '#8b90a0' }}>
            Loading proposal drafts...
          </div>
        ) : filteredDrafts.length === 0 ? (
          <div style={{ padding: '80px 0', textAlign: 'center', color: '#8b90a0' }}>
            {searchQuery
              ? 'No proposal drafts match your search filter.'
              : 'No proposal drafts found. Explore an opportunity and select "Compose Custom AI Draft" to save your first bid proposal.'}
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '20px',
            }}
          >
            {filteredDrafts.map((draft) => (
              <div
                key={draft.id}
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
                        fontSize: '0.68rem',
                        backgroundColor: 'rgba(57, 255, 20, 0.1)',
                        color: 'var(--success-color)',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        fontWeight: 600,
                      }}
                    >
                      Proposal Response
                    </span>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button
                        onClick={() => handleOpenDraft(draft)}
                        title="View / Edit Draft"
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
                        onClick={() => void handleDeleteDraft(draft.id)}
                        title="Delete Draft"
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
                      margin: '0 0 5px 0',
                      fontSize: '1.05rem',
                      color: '#fff',
                      fontWeight: 600,
                    }}
                  >
                    {draft.title}
                  </h4>

                  {draft.opp_title && (
                    <span
                      style={{
                        fontSize: '0.78rem',
                        color: 'var(--accent-color)',
                        display: 'block',
                        marginBottom: '10px',
                      }}
                    >
                      Opportunity: {draft.opp_title}
                    </span>
                  )}

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
                    {draft.content}
                  </p>
                </div>

                {/* Footer */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    paddingTop: '10px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.72rem',
                      color: '#8b90a0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <Calendar size={12} />
                      <span>Saved {draft.created_at}</span>
                    </div>
                    {draft.opp_org && (
                      <span
                        style={{
                          maxWidth: '140px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {draft.opp_org}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Slide-over or Modal view for active draft */}
      {activeDraft && (
        <div
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
            style={{
              width: '95%',
              maxWidth: '850px',
              height: '85vh',
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
                alignItems: 'flex-start',
                marginBottom: '15px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                paddingBottom: '10px',
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: '0.7rem',
                    backgroundColor: 'rgba(57, 255, 20, 0.1)',
                    color: 'var(--success-color)',
                    padding: '2px 8px',
                    borderRadius: '10px',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                  }}
                >
                  Active Proposal Draft
                </span>

                {isEditing ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    style={{
                      fontSize: '1.4rem',
                      fontWeight: 600,
                      color: '#fff',
                      backgroundColor: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '4px',
                      padding: '4px 8px',
                      marginTop: '8px',
                      width: '100%',
                      maxWidth: '500px',
                    }}
                  />
                ) : (
                  <h3
                    style={{
                      margin: '5px 0 0 0',
                      fontSize: '1.4rem',
                      color: '#fff',
                      fontWeight: 600,
                    }}
                  >
                    {activeDraft.title}
                  </h3>
                )}

                {activeDraft.opp_title && (
                  <span
                    style={{
                      fontSize: '0.8rem',
                      color: '#8b90a0',
                      display: 'block',
                      marginTop: '4px',
                    }}
                  >
                    Opportunity RFP: {activeDraft.opp_title} ({activeDraft.opp_org || 'Unknown'})
                  </span>
                )}
              </div>
              <button
                onClick={() => setActiveDraft(null)}
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

            {/* Content Area */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {isEditing ? (
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  style={{
                    flex: 1,
                    backgroundColor: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '8px',
                    color: '#fff',
                    padding: '15px',
                    fontFamily: 'Consolas, Courier, monospace',
                    fontSize: '0.9rem',
                    lineHeight: '1.6',
                    outline: 'none',
                    resize: 'none',
                  }}
                />
              ) : (
                <div
                  style={{
                    flex: 1,
                    overflowY: 'auto',
                    backgroundColor: 'rgba(0,0,0,0.15)',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.03)',
                    padding: '20px',
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.6',
                    fontSize: '0.92rem',
                    color: '#e5e2e3',
                  }}
                >
                  {activeDraft.content}
                </div>
              )}
            </div>

            {/* Footer Control Panel */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '20px',
                paddingTop: '15px',
                borderTop: '1px solid rgba(255,255,255,0.05)',
              }}
            >
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleCopy}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  {copySuccess ? (
                    <Check size={14} style={{ color: 'var(--success-color)' }} />
                  ) : (
                    <Copy size={14} />
                  )}
                  {copySuccess ? 'Copied!' : 'Copy Draft'}
                </button>
                {isEditing ? (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => void handleUpdateDraft()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'var(--accent-color)',
                      border: 'none',
                    }}
                  >
                    <Save size={14} /> Save Changes
                  </button>
                ) : (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setIsEditing(true)}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <Edit3 size={14} /> Edit Draft Content
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                {saveSuccess && (
                  <span style={{ fontSize: '0.8rem', color: 'var(--success-color)' }}>
                    Draft Saved Successfully!
                  </span>
                )}
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveDraft(null)}>
                  Close Draft
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
