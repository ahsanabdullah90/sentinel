import { useState, useRef, useEffect } from 'react';
import { X, Search, ChevronUp, ChevronDown, Sparkles, ExternalLink, Trash2, Plus } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { openUrl } from '@tauri-apps/plugin-opener';

export interface Opportunity {
  id: string;
  title: string;
  portal: string;
  date: string;
  issuing_org?: string;
  downloaded_pdf_path?: string | null;
  status?: string;
  url?: string | null;
  portal_base_url?: string | null;
  description?: string | null;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => void;
  opportunities: Opportunity[];
  onSelectOpportunity?: (id: string) => void;
}

export function OpportunitiesModal({
  isOpen,
  onClose,
  onRefresh,
  opportunities,
  onSelectOpportunity,
}: Props) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  // Manual creation states
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newPortalId, setNewPortalId] = useState('');
  const [newIssuingOrg, setNewIssuingOrg] = useState('');
  const [newDeadline, setNewDeadline] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [addError, setAddError] = useState<string | null>(null);
  const [addSuccess, setAddSuccess] = useState<string | null>(null);
  const [portals, setPortals] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    if (isOpen) {
      invoke<{ id: string; name: string }[]>('get_portals')
        .then(setPortals)
        .catch((err) => console.error('Failed to load portals in modal:', err));
    }
  }, [isOpen]);

  const sanitizeInput = (val: string): string => {
    if (!val) return '';
    return val.replace(/<\/?[^>]+(>|$)/g, "").trim();
  };

  const handleAddOpportunity = async () => {
    const cleanTitle = sanitizeInput(newTitle);
    const cleanPortalId = newPortalId;
    const cleanIssuingOrg = sanitizeInput(newIssuingOrg);
    const cleanDeadline = sanitizeInput(newDeadline);
    const cleanUrl = sanitizeInput(newUrl);
    const cleanDescription = sanitizeInput(newDescription);

    if (!cleanTitle) {
      setAddError('Title is required');
      return;
    }
    if (!cleanPortalId) {
      setAddError('Please select a Portal');
      return;
    }
    if (cleanUrl && !/^https?:\/\/[^\s$.?#].[^\s]*$/i.test(cleanUrl)) {
      setAddError('Invalid URL format. Must start with http:// or https://');
      return;
    }

    setAddError(null);
    setAddSuccess(null);
    try {
      const isOk = await invoke<boolean>('create_opportunity', {
        portalId: cleanPortalId,
        title: cleanTitle,
        issuingOrg: cleanIssuingOrg,
        deadlineAt: cleanDeadline,
        url: cleanUrl,
        description: cleanDescription,
      });
      if (isOk) {
        setAddSuccess('Opportunity added successfully!');
        setNewTitle('');
        setNewPortalId('');
        setNewIssuingOrg('');
        setNewDeadline('');
        setNewUrl('');
        setNewDescription('');
        setIsAdding(false);
        onRefresh();
      } else {
        setAddError('Opportunity with this title already exists.');
      }
    } catch (err: any) {
      console.error('Failed to create opportunity:', err);
      setAddError(err?.message || String(err) || 'Failed to save opportunity');
    }
  };
  const tableContainerRef = useRef<HTMLDivElement>(null);

  // Custom scroll states
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollHeight, setScrollHeight] = useState(0);
  const [clientHeight, setClientHeight] = useState(0);

  // Monitor scroll position for UI scrollbars / indicators
  const handleScroll = () => {
    if (tableContainerRef.current) {
      setScrollTop(tableContainerRef.current.scrollTop);
      setScrollHeight(tableContainerRef.current.scrollHeight);
      setClientHeight(tableContainerRef.current.clientHeight);
    }
  };

  useEffect(() => {
    if (isOpen) {
      // Small timeout to let the DOM render before checking height
      setTimeout(handleScroll, 100);
    }
  }, [isOpen, opportunities]);

  if (!isOpen) return null;

  // Programmatic Scroll Controls
  const scrollTable = (direction: 'up' | 'down') => {
    if (tableContainerRef.current) {
      const scrollAmount = direction === 'up' ? -180 : 180;
      tableContainerRef.current.scrollBy({
        top: scrollAmount,
        behavior: 'smooth',
      });
      // Force trigger scroll handler updating
      setTimeout(handleScroll, 200);
    }
  };

  // Status badges count mapping
  const statusCounts = opportunities.reduce(
    (acc, opp) => {
      const status = opp.status || 'discovered';
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  // Filtered Opportunities
  const filtered = opportunities.filter((opp) => {
    const matchesSearch =
      opp.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      opp.portal.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (opp.issuing_org || '').toLowerCase().includes(searchQuery.toLowerCase());

    if (selectedStatus === 'all') return matchesSearch;
    return matchesSearch && (opp.status || 'discovered') === selectedStatus;
  });

  // Handler to update status of an opportunity in the DB
  const handleStatusChange = async (oppId: string, newStatus: string) => {
    try {
      await invoke('update_opportunity_status', { id: oppId, status: newStatus });
      onRefresh(); // reload parent data
    } catch (err) {
      console.error('Failed to update opportunity status:', err);
    }
  };

  // Scroll completion progress percentage
  const scrollPercent =
    scrollHeight > clientHeight ? Math.round((scrollTop / (scrollHeight - clientHeight)) * 100) : 0;

  return (
    <div
      className="modal-backdrop"
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
        zIndex: 1000,
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
    >
      <div
        className="modal-content card glass"
        style={{
          width: '90%',
          maxWidth: '1080px',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          padding: '25px',
          position: 'relative',
          backgroundColor: '#111112',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
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
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#fff';
            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = '#8b90a0';
            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
          }}
        >
          <X size={16} />
        </button>

        {/* Modal Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <Sparkles size={22} style={{ color: 'var(--accent-color)' }} />
          <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600, color: '#fff' }}>
            Discovered Opportunities Center
          </h2>
          <span
            style={{
              fontSize: '0.8rem',
              backgroundColor: 'rgba(0,122,255,0.15)',
              color: 'var(--accent-color)',
              padding: '2px 8px',
              borderRadius: '12px',
              fontWeight: '500',
            }}
          >
            {opportunities.length} total
          </span>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setIsAdding(!isAdding)}
            style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px' }}
          >
            <Plus size={14} />
            {isAdding ? 'Cancel Add' : 'Add Opportunity'}
          </button>
        </div>

        {/* Filter Controls Area */}
        <div
          style={{
            display: 'flex',
            gap: '15px',
            flexWrap: 'wrap',
            marginBottom: '20px',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {/* Left: Search input */}
          <div style={{ position: 'relative', flex: '1', minWidth: '280px' }}>
            <Search
              size={18}
              style={{ position: 'absolute', left: '12px', top: '11px', color: '#8b90a0' }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
              }}
              placeholder="Search by title, portal or issuing organization..."
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '15px',
                backgroundColor: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '0.9rem',
                outline: 'none',
                height: '40px',
              }}
            />
          </div>

          {/* Right: Scroll Programmatic Buttons & Indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: '2px',
              }}
            >
              <span style={{ fontSize: '0.75rem', color: '#8b90a0' }}>Scroll Gauge</span>
              <div
                style={{
                  width: '80px',
                  height: '4px',
                  backgroundColor: 'rgba(255,255,255,0.05)',
                  borderRadius: '2px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${scrollPercent}%`,
                    height: '100%',
                    backgroundColor: 'var(--accent-color)',
                    transition: 'width 0.2s',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '5px' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  scrollTable('up');
                }}
                title="Scroll Table Up"
                style={{ padding: '8px', borderRadius: '6px' }}
                disabled={scrollTop <= 0}
              >
                <ChevronUp size={16} />
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  scrollTable('down');
                }}
                title="Scroll Table Down"
                style={{ padding: '8px', borderRadius: '6px' }}
                disabled={scrollHeight - scrollTop <= clientHeight + 1}
              >
                <ChevronDown size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Status Tabs Filter */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            overflowX: 'auto',
            paddingBottom: '10px',
            marginBottom: '15px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          <button
            onClick={() => {
              setSelectedStatus('all');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: '20px',
              border: 'none',
              backgroundColor:
                selectedStatus === 'all' ? 'var(--accent-color)' : 'rgba(255,255,255,0.04)',
              color: selectedStatus === 'all' ? '#fff' : '#8b90a0',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 500,
              transition: 'all 0.2s',
            }}
          >
            All <span style={{ opacity: 0.7, marginLeft: '4px' }}>({opportunities.length})</span>
          </button>

          {['discovered', 'downloaded', 'ingested', 'drafted', 'submitted'].map((st) => {
            const count = statusCounts[st] || 0;
            const active = selectedStatus === st;
            return (
              <button
                key={st}
                onClick={() => {
                  setSelectedStatus(st);
                }}
                style={{
                  padding: '6px 12px',
                  borderRadius: '20px',
                  border: 'none',
                  backgroundColor: active ? 'var(--accent-color)' : 'rgba(255,255,255,0.04)',
                  color: active ? '#fff' : '#8b90a0',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  transition: 'all 0.2s',
                  textTransform: 'capitalize',
                }}
              >
                {st} <span style={{ opacity: 0.7, marginLeft: '4px' }}>({count})</span>
              </button>
            );
          })}
        </div>

        {/* Manual Addition Form */}
        {isAdding && (
          <div
            className="card glass"
            style={{
              padding: '15px',
              marginBottom: '20px',
              border: '1px solid rgba(0, 122, 255, 0.3)',
              backgroundColor: 'rgba(0,0,0,0.3)',
              borderRadius: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              animation: 'fadeIn 0.2s',
            }}
          >
            <h4 style={{ margin: 0, color: '#fff', fontSize: '1rem', fontWeight: 600 }}>
              Manually Enter Opportunity
            </h4>
            
            {addError && (
              <div style={{ color: '#ff453a', fontSize: '0.85rem', backgroundColor: 'rgba(255, 69, 58, 0.1)', padding: '8px', borderRadius: '4px' }}>
                {addError}
              </div>
            )}
            {addSuccess && (
              <div style={{ color: '#30d158', fontSize: '0.85rem', backgroundColor: 'rgba(48, 209, 88, 0.1)', padding: '8px', borderRadius: '4px' }}>
                {addSuccess}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Opportunity Title *</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Health Sector IT Support Services"
                  style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Source Portal *</label>
                <select
                  value={newPortalId}
                  onChange={(e) => setNewPortalId(e.target.value)}
                  style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff', height: '38px' }}
                >
                  <option value="">-- Select Portal --</option>
                  {portals.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Issuing Organization</label>
                <input
                  type="text"
                  value={newIssuingOrg}
                  onChange={(e) => setNewIssuingOrg(e.target.value)}
                  placeholder="e.g. Department of Health"
                  style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Deadline Date</label>
                <input
                  type="text"
                  value={newDeadline}
                  onChange={(e) => setNewDeadline(e.target.value)}
                  placeholder="e.g. 2026-08-30"
                  style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Opportunity URL</label>
              <input
                type="text"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="e.g. https://portal.gov/rfp-details"
                style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#8b90a0', marginBottom: '4px' }}>Description</label>
              <textarea
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Enter details about this opportunity..."
                rows={3}
                style={{ width: '100%', padding: '8px', backgroundColor: '#181819', border: '1px solid #333', borderRadius: '4px', color: '#fff', resize: 'vertical' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '5px' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setIsAdding(false);
                  setAddError(null);
                }}
              >
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleAddOpportunity}>
                Save Opportunity
              </button>
            </div>
          </div>
        )}

        {/* Scrollable Table Area */}
        <div
          ref={tableContainerRef}
          onScroll={handleScroll}
          style={{
            flex: 1,
            overflowY: 'auto',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.05)',
            backgroundColor: 'rgba(0,0,0,0.2)',
            maxHeight: '420px',
          }}
          className="opportunities-list-container"
        >
          {/* Card list */}
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#8b90a0' }}>
              No opportunities matching the filters found.
            </div>
          ) : (
            filtered.map((opp) => {
              const statusVal = opp.status || 'discovered';
              return (
                <div
                  key={opp.id}
                  className="card glass"
                  style={{
                    marginBottom: '12px',
                    padding: '16px',
                    border: '1px solid rgba(255,255,255,0.08)',
                    backgroundColor: '#111112',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <h3 style={{ color: '#fff', margin: 0, fontSize: '1rem' }}>{opp.title}</h3>
                    <span style={{ color: '#8b90a0', fontSize: '0.85rem' }}>
                      Deadline: {opp.date || 'No Date'}
                    </span>
                  </div>
                  <div style={{ color: '#8b90a0', fontSize: '0.85rem' }}>
                    <strong>Issuing Org:</strong> {opp.issuing_org || 'N/A'}
                  </div>
                  <div style={{ color: '#8b90a0', fontSize: '0.85rem' }}>
                    <strong>Portal:</strong> {opp.portal}
                  </div>
                  {opp.description && (
                    <div style={{ color: '#c0c5d0', fontSize: '0.85rem', marginTop: '4px', fontStyle: 'italic', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {opp.description}
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <select
                      value={statusVal}
                      onChange={(e) => {
                        void handleStatusChange(opp.id, e.target.value);
                      }}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: '#e5e2e3',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                      }}
                    >
                      <option value="discovered" style={{ backgroundColor: '#1c1b1c' }}>
                        Discovered
                      </option>
                      <option value="downloaded" style={{ backgroundColor: '#1c1b1c' }}>
                        Downloaded
                      </option>
                      <option value="ingested" style={{ backgroundColor: '#1c1b1c' }}>
                        Ingested
                      </option>
                      <option value="drafted" style={{ backgroundColor: '#1c1b1c' }}>
                        Drafted
                      </option>
                      <option value="submitted" style={{ backgroundColor: '#1c1b1c' }}>
                        Submitted
                      </option>
                    </select>
                    <button
                      onClick={() => {
                        const link = opp.url || opp.portal_base_url || '';
                        if (link) {
                          openUrl(link).catch(console.error);
                        }
                      }}
                      className="btn btn-sm btn-ghost"
                      style={{
                        display: 'inline-flex',
                        gap: '4px',
                        alignItems: 'center',
                        fontSize: '0.75rem',
                        color: 'var(--accent-color)',
                        cursor: 'pointer',
                        backgroundColor: 'transparent',
                        border: 'none',
                        padding: '4px 8px'
                      }}
                    >
                      <ExternalLink size={12} />
                      Go to Web
                    </button>
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={() => {
                        if (onSelectOpportunity) {
                          onSelectOpportunity(opp.id);
                          onClose();
                        }
                      }}
                      style={{
                        display: 'inline-flex',
                        gap: '4px',
                        alignItems: 'center',
                        fontSize: '0.75rem',
                      }}
                    >
                      <Sparkles size={12} style={{ color: 'var(--accent-color)' }} />
                      Evaluate RFP
                    </button>
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={async () => {
                        if (!confirm('Are you sure you want to delete this opportunity?')) return;
                        try {
                          await invoke('delete_opportunity', { id: opp.id });
                          onRefresh();
                        } catch (err) {
                          console.error('Failed to delete opportunity:', err);
                        }
                      }}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '4px',
                        color: '#ff3b30',
                        borderRadius: '6px',
                        marginLeft: 'auto',
                      }}
                      title="Delete Opportunity"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Area */}
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
          <span style={{ fontSize: '0.8rem', color: '#8b90a0' }}>
            Showing {filtered.length} of {opportunities.length} opportunities
          </span>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Close Window
          </button>
        </div>
      </div>
    </div>
  );
}
