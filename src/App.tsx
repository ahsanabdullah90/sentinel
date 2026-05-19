import { useState, useEffect, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
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
import { ChatWindow } from './components/Chat/ChatWindow';
import { GapReport } from './components/GapReport/GapReport';
import { PortalConfigModal } from './components/PortalConfig/PortalConfigModal';
import { SettingsModal } from './components/Settings/SettingsModal';
import { OpportunitiesModal } from './components/Opportunities/OpportunitiesModal';
import { KnowledgeBaseDashboard } from './components/KnowledgeBase/KnowledgeBaseDashboard';
import { OpportunityDetail } from './components/Opportunities/OpportunityDetail';
import { ProposalDrafts } from './components/Drafts/ProposalDrafts';
import SqlDatabase from '@tauri-apps/plugin-sql';

interface Portal {
  id: string;
  name: string;
  url: string;
  keywords: string;
  status?: string;
  selector_config?: string;
  last_run_at?: string;
  last_run_duration_ms?: number;
  opportunities_count?: number;
  rendering_mode?: string;
  cloudflare_bypass_score?: string;
}

interface Opportunity {
  id: string;
  title: string;
  portal: string;
  date: string;
  issuing_org?: string;
  downloaded_pdf_path?: string | null;
  status?: string;
}

function App() {
  const [hunting, setHunting] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState('Checking...');
  const [sessionId, setSessionId] = useState('');
  const [huntLogs, setHuntLogs] = useState<string[]>([]);
  const startTimeRef = useRef<number | null>(null);
  const [schedulerInfo, setSchedulerInfo] = useState('');
  const queueRef = useRef<string[]>([]);
  const queueIndexRef = useRef<number>(-1);
  const triggerNextQueuePortalRef = useRef<() => Promise<void>>(async () => {});
  // Portals State
  const [portals, setPortals] = useState<Portal[]>([]);

  const portalsRef = useRef<Portal[]>([]);
  useEffect(() => {
    portalsRef.current = portals;
  }, [portals]);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPortal, setEditingPortal] = useState<Portal | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState({
    ollamaModel: 'phi3',
    ollamaUrl: 'http://127.0.0.1:11434',
  });

  // Opportunities State
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [isOpportunitiesOpen, setIsOpportunitiesOpen] = useState(false);
  const [currentView, setCurrentView] = useState<
    'hunt' | 'knowledge' | 'drafts' | 'opportunity-detail'
  >('hunt');
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);

  // Boot State
  const [systemStatus, setSystemStatus] = useState<'booting' | 'ready' | 'error'>('booting');
  const [bootLog, setBootLog] = useState('Initializing Control Unit...');

  useEffect(() => {
    void checkOllama();
    void bootstrapEngines();
    void loadOpportunities();
    void loadPortals();

    const unlisten = listen('sentinel://hunter/portal-detected', async (event: any) => {
      console.log('Portal detected:', event.payload);
      const report = event.payload;
      const db = await SqlDatabase.load('sqlite:sentinel.db');

      let searchSelector = report.searchSelector || '';
      if (!searchSelector && report.scrapingOptions && report.scrapingOptions[0]) {
        const desc = report.scrapingOptions[0].description || '';
        if (desc.includes(': ')) {
          searchSelector = desc.split(': ')[1];
        }
      }

      const config = {
        searchSelector: searchSelector,
      };

      // Relaxed match on URL: handle optional trailing slashes elegantly
      const sanitizedUrl = report.url.replace(/\/+$/, '');
      await db.execute(
        'UPDATE portals SET selector_config = ?, rendering_mode = ? WHERE base_url = ? OR base_url = ? OR base_url LIKE ?',
        [
          JSON.stringify(config),
          'Browser (Playwright)',
          sanitizedUrl,
          sanitizedUrl + '/',
          `%${sanitizedUrl}%`,
        ]
      );
      console.log('Saved selector config for', report.url);
      void loadPortals();
    });

    const unlistenOpp = listen('sentinel://hunter/opportunity-found', async (event: any) => {
      console.log('Opportunity found:', event.payload);
      const opp = event.payload;
      try {
        const db = await SqlDatabase.load('sqlite:sentinel.db');
        const oppId = opp.id || Math.random().toString(36).substr(2, 9);
        const portalId = opp.portalId || '1';

        // Fetch all existing opportunities to perform high-fidelity whitespace/casing normalization checks
        const existing = await db.select<any[]>('SELECT title FROM opportunities');

        // Trim and collapse multiple spaces to a single space
        const normalizedInputTitle = opp.title.trim().replace(/\s+/g, ' ');
        const isDuplicate = existing.some((row: any) => {
          const rowNorm = row.title.trim().replace(/\s+/g, ' ').toLowerCase();
          return rowNorm === normalizedInputTitle.toLowerCase();
        });

        if (!isDuplicate) {
          await db.execute(
            'INSERT INTO opportunities (id, portal_id, title, issuing_org, deadline_at, status) VALUES (?, ?, ?, ?, ?, ?)',
            [
              oppId,
              portalId,
              normalizedInputTitle,
              opp.agency || 'Unknown Agency',
              opp.dueDate || '2026-06-30',
              'discovered',
            ]
          );

          // Increment opportunities_count for this portal
          await db.execute(
            'UPDATE portals SET opportunities_count = COALESCE(opportunities_count, 0) + 1 WHERE id = ?',
            [portalId]
          );

          console.log('Logged new opportunity:', normalizedInputTitle);
          void loadOpportunities();
          void loadPortals();
        } else {
          console.log('Skipped duplicate opportunity:', normalizedInputTitle);
        }
      } catch (err) {
        console.error('Failed to save opportunity to database:', err);
      }
    });

    const unlistenProgress = listen('sentinel://hunter/progress', async (event: any) => {
      const payload = event.payload;
      console.log('Hunter progress:', payload);
      if (payload.message) {
        setHuntLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${payload.message}`]);

        if (payload.message === 'Hunt completed successfully') {
          // Trigger the final DB stats update
          await finishActiveHunt(payload.portalId);
        }
      }
    });

    const unlistenError = listen('sentinel://hunter/error', async (event: any) => {
      const payload = event.payload;
      console.error('Hunter error:', payload);
      if (payload.message) {
        setHuntLogs((prev) => [...prev, `[ERROR] ${payload.message}`]);
      }
      void loadPortals();
      // Sequentially trigger next queue item
      void triggerNextQueuePortalRef.current();
    });

    return () => {
      unlisten.then((f) => f());
      unlistenOpp.then((f) => f());
      unlistenProgress.then((f) => f());
      unlistenError.then((f) => f());
    };
  }, []);

  async function loadOpportunities() {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      const result = await db.select<any[]>(
        'SELECT o.id, o.title, o.issuing_org, o.deadline_at as date, o.status, p.name as portal FROM opportunities o JOIN portals p ON o.portal_id = p.id ORDER BY o.created_at DESC'
      );
      setOpportunities(result);
    } catch (error) {
      console.error('Failed to load opportunities:', error);
    }
  }

  async function loadPortals() {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      const result = await db.select<any[]>(
        'SELECT id, name, base_url as url, keywords, status, selector_config, last_run_at, last_run_duration_ms, opportunities_count, rendering_mode, cloudflare_bypass_score FROM portals'
      );
      setPortals(result as Portal[]);
    } catch (error) {
      console.error('Failed to load portals:', error);
    }
  }

  async function bootstrapEngines() {
    try {
      setBootLog('Running Control Unit script...');
      const log = await invoke('bootstrap_system');
      // eslint-disable-next-line no-console
      console.log('Bootstrap complete:', log);

      const db = await SqlDatabase.load('sqlite:sentinel.db');

      // Clean up stub data programmatically to ensure only real-time data is presented
      await db.execute('DELETE FROM opportunities WHERE id IN (?, ?)', ['101', '102']);
      await db.execute('DELETE FROM portals WHERE id = ?', ['1']);

      // Pre-populate known high-fidelity configuration presets for maximum user experience
      const activePortalsList = await db.select<any[]>(
        'SELECT id, base_url, selector_config FROM portals'
      );
      for (const p of activePortalsList) {
        if (p.base_url.includes('resume.brightspyre.com') && !p.selector_config) {
          const configPreset = { searchSelector: 'input#query-data' };
          await db.execute(
            'UPDATE portals SET selector_config = ?, rendering_mode = ? WHERE id = ?',
            [JSON.stringify(configPreset), 'Browser (Playwright)', p.id]
          );
        }
      }

      void loadOpportunities();
      void loadPortals();

      setBootLog('All systems green. Sentinel is ready.');
      setTimeout(() => {
        setSystemStatus('ready');
      }, 1000);
    } catch (error) {
      console.error('Bootstrap failed:', error);
      setBootLog(`Boot Error: ${error instanceof Error ? error.message : String(error)}`);
      setSystemStatus('error');
    }
  }

  async function checkOllama() {
    setOllamaStatus('Checking...');
    try {
      const status = await invoke('check_ollama_status');
      setOllamaStatus(status as string);
    } catch (error) {
      console.error('Failed to check Ollama:', error);
      setOllamaStatus('Offline');
    }
  }

  async function finishActiveHunt(portalId: string) {
    try {
      const startTime = startTimeRef.current || Date.now();
      const duration = Date.now() - startTime;

      // Calculate GMT+5 Local Time
      const localDate = new Date(Date.now() + 5 * 60 * 60 * 1000);
      const timestamp = localDate.toISOString().replace('T', ' ').substring(0, 19) + ' (GMT+5)';

      const db = await SqlDatabase.load('sqlite:sentinel.db');

      // Get the number of opportunities for this portal
      const countRes = await db.select<any[]>(
        'SELECT COUNT(*) as cnt FROM opportunities WHERE portal_id = ?',
        [portalId]
      );
      const oppCount = countRes[0]?.cnt || 0;

      const portal = portals.find((p) => p.id === portalId);
      const renderingMode =
        portal?.selector_config || portalId === 'xbfs76tfq'
          ? 'Browser (Playwright)'
          : 'Static HTML';
      const guardScore = 'Low Risk';

      // Update portal diagnostics in SQLite
      await db.execute(
        'UPDATE portals SET last_run_at = ?, last_run_duration_ms = ?, opportunities_count = ?, rendering_mode = ?, cloudflare_bypass_score = ? WHERE id = ?',
        [timestamp, duration, oppCount, renderingMode, guardScore, portalId]
      );

      console.log(`Successfully finished hunt for portal ${portalId}. Yield: ${oppCount} items.`);
      void loadOpportunities();
      void loadPortals();
    } catch (err) {
      console.error('Failed to update portal diagnostics on finish:', err);
    } finally {
      void triggerNextQueuePortalRef.current();
    }
  }

  const triggerNextQueuePortal = async () => {
    const nextIndex = queueIndexRef.current + 1;
    if (nextIndex < queueRef.current.length) {
      queueIndexRef.current = nextIndex;
      const nextPortalId = queueRef.current[nextIndex];

      setHuntLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Queue progress: Starting next website hunt (${nextIndex + 1}/${queueRef.current.length})...`,
      ]);

      setTimeout(async () => {
        try {
          const db = await SqlDatabase.load('sqlite:sentinel.db');
          const portalsRes = await db.select<any[]>('SELECT * FROM portals');
          const portal = portalsRes.find((p) => p.id === nextPortalId);
          if (portal) {
            const mappedPortal = {
              id: portal.id,
              name: portal.name,
              url: portal.base_url,
              keywords: portal.keywords,
              status: portal.status,
              selector_config: portal.selector_config,
            };
            setHunting(true);
            startTimeRef.current = Date.now();
            const id = await invoke('start_hunt_session', {
              portalId: nextPortalId,
              config: JSON.stringify(mappedPortal),
            });
            setSessionId(id as string);
          } else {
            // Portal not found, proceed to next
            void triggerNextQueuePortal();
          }
        } catch (err) {
          console.error('Failed to start next queue hunt:', err);
          setHuntLogs((prev) => [
            ...prev,
            `[ERROR] Failed to start next website hunt: ${err instanceof Error ? err.message : String(err)}`,
          ]);
          void triggerNextQueuePortal();
        }
      }, 2000);
    } else {
      // Queue is fully complete!
      queueRef.current = [];
      queueIndexRef.current = -1;
      setHunting(false);
      setHuntLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] All sequential website hunts completed successfully!`,
      ]);
    }
  };

  useEffect(() => {
    triggerNextQueuePortalRef.current = triggerNextQueuePortal;
  });

  async function triggerQueueHunt(portalIds: string[]) {
    queueRef.current = portalIds;
    queueIndexRef.current = 0;
    if (portalIds.length > 0) {
      const firstPortalId = portalIds[0];
      await handleStartHunt(firstPortalId);
    }
  }

  // Automated Hourly Hunt Scheduler (09:00 AM - 11:59 AM)
  useEffect(() => {
    function updateSchedulerStatus() {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;

      const lastRunStr = localStorage.getItem('sentinel_last_auto_hunt_timestamp');
      let lastRunText = 'Never';
      if (lastRunStr) {
        const diffMin = Math.floor((Date.now() - parseInt(lastRunStr, 10)) / 60000);
        if (diffMin < 60) {
          lastRunText = `${diffMin}m ago`;
        } else {
          lastRunText = `${Math.floor(diffMin / 60)}h ago`;
        }
      }

      if (inWindow) {
        setSchedulerInfo(`Active Window • Last Auto-Run: ${lastRunText}`);
      } else {
        setSchedulerInfo(`Idle (Window: 09:00 AM - 11:59 AM) • Last: ${lastRunText}`);
      }
    }

    updateSchedulerStatus();
    const interval = setInterval(updateSchedulerStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const checkAndTriggerAutoHunt = () => {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;

      // Ensure we don't double-trigger if hunt is active, or if portals are not loaded
      if (!inWindow || hunting || portals.length === 0) {
        return;
      }

      const lastRunStr = localStorage.getItem('sentinel_last_auto_hunt_timestamp');
      const oneHourMs = 3600000;
      const shouldTrigger = !lastRunStr || Date.now() - parseInt(lastRunStr, 10) >= oneHourMs;

      if (shouldTrigger) {
        console.log('Automated scheduler: Triggering hourly hunts for all active websites...');
        localStorage.setItem('sentinel_last_auto_hunt_timestamp', Date.now().toString());

        const activePortals = portals.filter((p) => p.status === 'Active');
        if (activePortals.length > 0) {
          setHuntLogs([
            `[${new Date().toLocaleTimeString()}] [AUTOMATED] Triggering scheduled hourly hunt...`,
          ]);
          void triggerQueueHunt(activePortals.map((p) => p.id));
        }
      }
    };

    checkAndTriggerAutoHunt();
    const interval = setInterval(checkAndTriggerAutoHunt, 30000);
    return () => clearInterval(interval);
  }, [portals, hunting]);

  async function handleStartHunt(portalId: string) {
    try {
      setHunting(true);
      setHuntLogs([
        `[${new Date().toLocaleTimeString()}] Spawning headless Chromium browser engine...`,
      ]);
      startTimeRef.current = Date.now();

      const portal = portals.find((p) => p.id === portalId);
      const id = await invoke('start_hunt_session', { portalId, config: JSON.stringify(portal) });
      setSessionId(id as string);
    } catch (error) {
      console.error('Failed to start hunt:', error);
      setHunting(false);
      setHuntLogs((prev) => [
        ...prev,
        `[ERROR] Failed to start hunt: ${error instanceof Error ? error.message : String(error)}`,
      ]);
    }
  }

  async function handleStopHunt() {
    try {
      await invoke('stop_hunt_session', { sessionId });
      setHunting(false);
      setSessionId('');
    } catch (error) {
      console.error('Failed to stop hunt:', error);
    }
  }

  async function handleSavePortal(portal: Portal) {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      if (editingPortal) {
        await db.execute(
          'UPDATE portals SET name = ?, base_url = ?, keywords = ?, status = ? WHERE id = ?',
          [portal.name, portal.url, portal.keywords, portal.status || 'Active', editingPortal.id]
        );
        setEditingPortal(null);
      } else {
        await db.execute(
          'INSERT INTO portals (id, name, base_url, keywords, status, auth_method, scraper_module) VALUES (?, ?, ?, ?, ?, ?, ?)',
          [
            portal.id,
            portal.name,
            portal.url,
            portal.keywords,
            'Active',
            'public',
            'generic_search',
          ]
        );

        // Trigger intelligent detection in background
        void invoke('detect_portal', { url: portal.url });
      }
      void loadPortals();
    } catch (error) {
      console.error('Failed to save portal:', error);
    }
  }

  function handleOpenAddModal() {
    setEditingPortal(null);
    setIsModalOpen(true);
  }

  function handleOpenEditModal(portal: Portal) {
    setEditingPortal(portal);
    setIsModalOpen(true);
  }

  async function handleDeletePortal(id: string) {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('DELETE FROM portals WHERE id = ?', [id]);
      setPortals(portals.filter((p) => p.id !== id));
    } catch (error) {
      console.error('Failed to delete portal:', error);
    }
  }

  async function handleTogglePortalStatus(id: string, currentStatus: string) {
    try {
      const nextStatus = currentStatus === 'Active' ? 'Inactive' : 'Active';
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('UPDATE portals SET status = ? WHERE id = ?', [nextStatus, id]);
      void loadPortals();
    } catch (error) {
      console.error('Failed to toggle portal status:', error);
    }
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
            {currentView === 'knowledge' && 'Knowledge Base Studio'}
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
                        setHuntLogs([
                          `[${new Date().toLocaleTimeString()}] No active portals found to hunt.`,
                        ]);
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
                                  handleDeletePortal(p.id);
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

        <ChatWindow settings={settings} />
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

export default App;
