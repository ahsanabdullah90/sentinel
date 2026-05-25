import { useState, useRef, useEffect } from 'react';
import { X, Search, ChevronUp, ChevronDown, Sparkles } from 'lucide-react';
import SqlDatabase from '@tauri-apps/plugin-sql';

export interface Opportunity {
  id: string;
  title: string;
  portal: string;
  date: string;
  issuing_org?: string;
  downloaded_pdf_path?: string | null;
  status?: string;
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
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('UPDATE opportunities SET status = ? WHERE id = ?', [newStatus, oppId]);
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
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
            filtered.map((opp, idx) => {
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ color: '#fff', margin: 0, fontSize: '1rem' }}>{opp.title}</h3>
                    <span style={{ color: '#8b90a0', fontSize: '0.85rem' }}>{opp.date || 'No Date'}</span>
                  </div>
                  <div style={{ color: '#8b90a0', fontSize: '0.85rem' }}>
                    <strong>Issuing Org:</strong> {opp.issuing_org || 'N/A'}
                  </div>
                  <div style={{ color: '#8b90a0', fontSize: '0.85rem' }}>
                    <strong>Portal:</strong> {opp.portal}
                  </div>
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
