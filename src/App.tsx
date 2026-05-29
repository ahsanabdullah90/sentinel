// src/App.tsx
import { useState } from 'react';
import {
  Shield,
  Search,
  FileText,
  Settings,
  Play,
  Square,
  Wifi,
  Database,
  Activity,
  Plus,
  Trash2,
  Edit,
  Loader,
} from 'lucide-react';
import './App.css';
import { GapReport } from './components/GapReport/GapReport';
import { PortalConfigModal } from './components/PortalConfig/PortalConfigModal';
import { SettingsModal } from './components/Settings/SettingsModal';
import { OpportunitiesModal } from './components/Opportunities/OpportunitiesModal';
import { KnowledgeBaseDashboard } from './components/KnowledgeBase/KnowledgeBaseDashboard';
import { OpportunityDetail } from './components/Opportunities/OpportunityDetail';
import { ProposalDrafts } from './components/Drafts/ProposalDrafts';
import { AppProvider, useAppContext } from './context/AppContext';
import { Portal } from './types';

function App() {
  const [currentView, setCurrentView] = useState<'hunt' | 'knowledge' | 'drafts' | 'opportunity-detail'>('hunt');

  const {
    hunting,
    ollamaStatus,
    huntLogs,
    schedulerInfo,
    portals,
    opportunities,
    isModalOpen,
    setIsModalOpen,
    editingPortal,
    setEditingPortal,
    isSettingsOpen,
    setIsSettingsOpen,
    settings,
    setSettings,
    isOpportunitiesOpen,
    setIsOpportunitiesOpen,
    selectedOpportunityId,
    setSelectedOpportunityId,
    systemStatus,
    bootLog,
    handleStopHunt,
    handleSavePortal,
    handleDeletePortal,
    handleTogglePortalStatus,
    triggerQueueHunt,
    loadOpportunities,
    bootstrapEngines,
    checkOllama,
  } = useAppContext();

  function handleOpenAddModal() {
    setEditingPortal(null);
    setIsModalOpen(true);
  }

  function handleOpenEditModal(portal: Portal) {
    setEditingPortal(portal);
    setIsModalOpen(true);
  }

  if (systemStatus !== 'ready') {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          backgroundColor: '#0a0a0a',
          color: '#fff',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        <Shield
          size={64}
          style={{
            color: 'var(--accent-color)',
            marginBottom: '20px',
            animation: systemStatus === 'booting' ? 'pulse 2s infinite' : 'none',
          }}
        />
        <h2>Sentinel Boot Sequence</h2>
        <div
          style={{
            marginTop: '20px',
            padding: '15px',
            backgroundColor: 'rgba(255,255,255,0.05)',
            borderRadius: '8px',
            width: '400px',
            textAlign: 'center',
          }}
        >
          {systemStatus === 'booting' ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
              }}
            >
              <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ color: '#8b90a0' }}>{bootLog}</span>
            </div>
          ) : (
            <div style={{ color: '#ff4d4f' }}>
              <p>{bootLog}</p>
              <button
                className="btn btn-primary"
                onClick={() => {
                  void bootstrapEngines();
                }}
                style={{ marginTop: '10px' }}
              >
                Retry Boot Sequence
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <Shield className="brand-icon" />
          <span>Sentinel</span>
        </div>
        <nav className="nav-links">
          <a
            href="#"
            className={`nav-link ${currentView === 'hunt' || currentView === 'opportunity-detail' ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              setCurrentView('hunt');
            }}
          >
            <Search size={18} /> Hunt
          </a>
          <a
            href="#"
            className={`nav-link ${currentView === 'knowledge' ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              setCurrentView('knowledge');
            }}
          >
            <Database size={18} /> Knowledge Base
          </a>
          <a
            href="#"
            className={`nav-link ${currentView === 'drafts' ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              setCurrentView('drafts');
            }}
          >
            <FileText size={18} /> Saved Drafts
          </a>
          <a
            href="#"
            className="nav-link"
            onClick={(e) => {
              e.preventDefault();
              setIsSettingsOpen(true);
            }}
          >
            <Settings size={18} /> Settings
          </a>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="header">
          <h1>
            {currentView === 'hunt' && 'Radar Hunt Dashboard'}
            {currentView === 'drafts' && 'Saved Proposal Drafts'}
            {currentView === 'opportunity-detail' && 'RFP Evaluation Canvas'}
          </h1>
          <div className="system-status-pills">
            <button
              className={`pill ${ollamaStatus === 'Online' ? 'online' : ''}`}
              onClick={() => {
                void checkOllama();
              }}
            >
              <Wifi size={14} /> Ollama: {ollamaStatus}
            </button>
            <div className="pill online">
              <Database size={14} /> ChromaDB Connected
            </div>
          </div>
        </header>

        {currentView === 'hunt' && (
          <>
            {/* Hero Banner */}
            <div className={`hero-banner ${hunting ? 'hunting' : 'ready'}`}>
              <div className="hero-content">
                <Activity className={`status-icon ${hunting ? 'pulse' : ''}`} size={32} />
                <div>
                  <h2>{hunting ? 'HUNTING ACTIVE' : 'SYSTEM READY'}</h2>
                  <p>
                    {hunting
                      ? 'Scanning portals for opportunities...'
                      : 'All systems operational. Privacy-first mode enabled.'}
                  </p>
                </div>
              </div>
            </div>

            {/* Real-time Diagnostic Scouting Console */}
            {hunting && (
              <div
                className="card glass"
                style={{
                  marginTop: '15px',
                  border: '1px solid rgba(0, 240, 255, 0.25)',
                  padding: '15px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '10px',
                  }}
                >
                  <div
                    className="pulse-dot"
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: '#00f0ff',
                      boxShadow: '0 0 8px #00f0ff',
                    }}
                  ></div>
                  <h4
                    style={{
                      margin: 0,
                      color: '#00f0ff',
                      fontSize: '0.85rem',
                      letterSpacing: '0.05em',
                      fontWeight: 'bold',
                    }}
                  >
                    LIVE SCOUTING CONSOLE
                  </h4>
                </div>
                <div
                  style={{
                    fontFamily: 'Consolas, Monaco, monospace',
                    fontSize: '0.8rem',
                    color: '#39ff14',
                    backgroundColor: 'rgba(0, 0, 0, 0.45)',
                    padding: '12px',
                    borderRadius: '8px',
                    maxHeight: '160px',
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    textAlign: 'left',
                  }}
                >
                  {huntLogs.map((log, i) => (
                    <div key={i}>{log}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Portals Management */}
            <div className="card glass">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '20px',
                  flexWrap: 'wrap',
                  gap: '15px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    textAlign: 'left',
                  }}
                >
                  <h3 style={{ margin: 0 }}>Target Portals & Websites</h3>
                  {schedulerInfo && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '0.78rem',
                        color: '#a0aec0',
                      }}
                    >
                      <span
                        className="pulse-dot"
                        style={{
                          width: '6px',
                          height: '6px',
                          backgroundColor: schedulerInfo.includes('Active') ? '#39ff14' : '#8b90a0',
                          boxShadow: schedulerInfo.includes('Active') ? '0 0 6px #39ff14' : 'none',
                        }}
                      ></span>
                      <span>{schedulerInfo}</span>
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      const activePortals = portals.filter((p) => p.status === 'Active');
                      if (activePortals.length > 0) {
                        void triggerQueueHunt(activePortals.map((p) => p.id));
                      } else {
                        // eslint-disable-next-line no-console
                        console.log('No active portals found to hunt.');
                      }
                    }}
                    disabled={hunting}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
                      border: 'none',
                      color: '#fff',
                      boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)',
                      opacity: hunting ? 0.6 : 1,
                      cursor: hunting ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <span>🚀 Hunt All Active</span>
                  </button>
                  <button className="btn btn-primary" onClick={handleOpenAddModal}>
                    <Plus size={16} /> Add Portal
                  </button>
                </div>
              </div>

              {/* Portals Table */}
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Website Details</th>
                      <th>Keywords</th>
                      <th>Search Configuration</th>
                      <th>Operational Diagnostics</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portals.map((p) => {
                      let searchSelector = '';
                      try {
                        if (p.selector_config) {
                          const cfg = JSON.parse(p.selector_config);
                          if (cfg && cfg.searchSelector) {
                            searchSelector = cfg.searchSelector;
                          }
                        }
                      } catch (e) {
                        console.error('Failed to parse selector_config:', e);
                      }

                      const isActive = p.status === 'Active';

                      return (
                        <tr key={p.id}>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                              <span style={{ fontWeight: 600, color: '#fff', fontSize: '0.95rem' }}>
                                {p.name}
                              </span>
                              <a
                                href={p.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                  fontSize: '0.8rem',
                                  color: '#8b90a0',
                                  textDecoration: 'none',
                                }}
                              >
                                {p.url}
                              </a>
                              <div style={{ display: 'flex', gap: '6px', marginTop: '3px' }}>
                                <span
                                  className="badge badge-secondary"
                                  style={{ fontSize: '0.65rem', padding: '2px 6px' }}
                                >
                                  Engine: {p.rendering_mode || 'Static HTML'}
                                </span>
                                <span
                                  className={`badge ${p.cloudflare_bypass_score === 'High Risk' ? 'badge-warning' : 'badge-success'}`}
                                  style={{ fontSize: '0.65rem', padding: '2px 6px' }}
                                >
                                  Guard: {p.cloudflare_bypass_score || 'Low Risk'}
                                </span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span style={{ fontSize: '0.85rem', color: '#e5e2e3' }}>
                              {p.keywords || 'None'}
                            </span>
                          </td>
                          <td>
                            {searchSelector ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <span
                                  className="badge badge-success"
                                  style={{ width: 'fit-content' }}
                                >
                                  <span className="pulse-dot"></span> Ready (CSS Match)
                                </span>
                                <code
                                  style={{
                                    fontSize: '0.75rem',
                                    color: '#8b90a0',
                                    fontFamily: 'monospace',
                                  }}
                                >
                                  {searchSelector}
                                </code>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <span
                                  className="badge badge-warning"
                                  style={{ width: 'fit-content' }}
                                >
                                  Pending Detection
                                </span>
                                <span style={{ fontSize: '0.75rem', color: '#8b90a0' }}>
                                  Will auto-detect on first hunt
                                </span>
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  fontSize: '0.8rem',
                                  color: '#8b90a0',
                                }}
                              >
                                <span>Last Crawl:</span>
                                <span style={{ color: '#fff', fontWeight: 500 }}>
                                  {p.last_run_at ? p.last_run_at : 'Never'}
                                </span>
                                {p.last_run_duration_ms ? (
                                  <span
                                    style={{
                                      color: 'var(--accent-color)',
                                      fontSize: '0.75rem',
                                      fontWeight: 600,
                                    }}
                                  >
                                    ({(p.last_run_duration_ms / 1000).toFixed(1)}s)
                                  </span>
                                ) : null}
                              </div>
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  fontSize: '0.8rem',
                                  color: '#8b90a0',
                                }}
                              >
                                <span>Yield:</span>
                                <span
                                  className="badge badge-success"
                                  style={{ fontSize: '0.65rem', padding: '2px 6px' }}
                                >
                                  {p.opportunities_count || 0} Opportunities
                                </span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <label className="switch">
                                <input
                                  type="checkbox"
                                  checked={isActive}
                                  onChange={() => {
                                    void handleTogglePortalStatus(p.id, p.status || 'Active');
                                  }}
                                />
                                <span className="slider"></span>
                              </label>
                              <span
                                className={
                                  isActive ? 'badge badge-success' : 'badge badge-secondary'
                                }
                                style={{ minWidth: '70px', justifyContent: 'center' }}
                              >
                                {p.status || 'Active'}
                              </span>
                            </div>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '5px' }}>
                              {!hunting ? (
                                <button
                                  className="btn btn-sm btn-primary"
                                  onClick={() => {
                                    void triggerQueueHunt([p.id]);
                                  }}
                                  disabled={!isActive}
                                  style={{
                                    opacity: isActive ? 1 : 0.5,
                                    cursor: isActive ? 'pointer' : 'not-allowed',
                                  }}
                                  title={
                                    isActive
                                      ? 'Start hunting opportunities'
                                      : 'Activate portal to start hunt'
                                  }
                                >
                                  <Play size={12} />
                                </button>
                              ) : (
                                <button
                                  className="btn btn-sm btn-danger"
                                  onClick={() => {
                                    void handleStopHunt();
                                  }}
                                >
                                  <Square size={12} />
                                </button>
                              )}
                              <button
                                className="btn btn-sm btn-secondary"
                                onClick={() => {
                                  handleOpenEditModal(p);
                                }}
                              >
                                <Edit size={12} />
                              </button>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => {
                                  void handleDeletePortal(p.id);
                                }}
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Opportunities Feed */}
            <div className="card glass opportunities-feed">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '15px',
                }}
              >
                <h3 style={{ margin: 0 }}>Discovered Opportunities</h3>
                {opportunities.length > 0 && (
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => {
                      setIsOpportunitiesOpen(true);
                    }}
                    style={{
                      borderColor: 'rgba(0, 122, 255, 0.4)',
                      color: 'var(--accent-color)',
                      fontWeight: 600,
                      fontSize: '0.75rem',
                      letterSpacing: '0.02em',
                      textTransform: 'uppercase',
                      padding: '4px 10px',
                      borderRadius: '12px',
                    }}
                  >
                    See More
                  </button>
                )}
              </div>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: '80px' }}>S.No.</th>
                      <th>Title</th>
                      <th>Portal</th>
                      <th>Date</th>
                      <th style={{ textAlign: 'center' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opportunities.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', color: '#8b90a0' }}>
                          No opportunities discovered yet. Start a hunt to populate.
                        </td>
                      </tr>
                    ) : (
                      opportunities.slice(0, 5).map((o, idx) => (
                        <tr
                          key={o.id}
                          style={{ cursor: 'pointer', transition: 'background-color 0.15s' }}
                          onClick={() => {
                            setSelectedOpportunityId(o.id);
                            setCurrentView('opportunity-detail');
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <td style={{ color: '#8b90a0', fontWeight: '500' }}>{idx + 1}</td>
                          <td
                            style={{ fontWeight: 500, color: '#fff', transition: 'color 0.15s' }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.color = 'var(--accent-color)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.color = '#fff';
                            }}
                          >
                            {o.title}
                          </td>
                          <td>{o.portal}</td>
                          <td>{o.date}</td>
                          <td style={{ textAlign: 'center' }}>
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedOpportunityId(o.id);
                                setCurrentView('opportunity-detail');
                              }}
                              style={{
                                display: 'inline-flex',
                                gap: '4px',
                                alignItems: 'center',
                                fontSize: '0.75rem',
                              }}
                            >
                              Evaluate RFP
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {currentView === 'knowledge' && <KnowledgeBaseDashboard />}

        {currentView === 'drafts' && <ProposalDrafts />}

        {currentView === 'opportunity-detail' && selectedOpportunityId && (
          <OpportunityDetail
            opportunityId={selectedOpportunityId}
            onBack={() => setCurrentView('hunt')}
            onRefresh={loadOpportunities}
            settings={settings}
            onViewDrafts={() => setCurrentView('drafts')}
          />
        )}

        <GapReport />

        <PortalConfigModal
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
          }}
          onSave={handleSavePortal}
          editingPortal={editingPortal}
        />

        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => {
            setIsSettingsOpen(false);
          }}
          onSave={(newSettings) => {
            setSettings(newSettings);
          }}
          currentSettings={settings}
        />

        <OpportunitiesModal
          isOpen={isOpportunitiesOpen}
          onClose={() => {
            setIsOpportunitiesOpen(false);
          }}
          onRefresh={loadOpportunities}
          opportunities={opportunities}
          onSelectOpportunity={(id) => {
            setSelectedOpportunityId(id);
            setCurrentView('opportunity-detail');
          }}
        />
      </main>
    </div>
  );
}

export default function WrappedApp() {
  return (
    <AppProvider>
      <App />
    </AppProvider>
  );
}
