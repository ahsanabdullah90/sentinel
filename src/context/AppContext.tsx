// src/context/AppContext.tsx
import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import SqlDatabase from '@tauri-apps/plugin-sql';
import { Portal, Opportunity } from '../types'; // We'll create a types file later

// Context shape
export interface AppContextProps {
  // State
  hunting: boolean;
  setHunting: React.Dispatch<React.SetStateAction<boolean>>;
  ollamaStatus: string;
  setOllamaStatus: React.Dispatch<React.SetStateAction<string>>;
  sessionId: string;
  setSessionId: React.Dispatch<React.SetStateAction<string>>;
  huntLogs: string[];
  setHuntLogs: React.Dispatch<React.SetStateAction<string[]>>;
  schedulerInfo: string;
  setSchedulerInfo: React.Dispatch<React.SetStateAction<string>>;
  portals: Portal[];
  setPortals: React.Dispatch<React.SetStateAction<Portal[]>>;
  opportunities: Opportunity[];
  setOpportunities: React.Dispatch<React.SetStateAction<Opportunity[]>>;
  isModalOpen: boolean;
  setIsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  editingPortal: Portal | null;
  setEditingPortal: React.Dispatch<React.SetStateAction<Portal | null>>;
  isSettingsOpen: boolean;
  setIsSettingsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  settings: { ollamaModel: string; ollamaUrl: string };
  setSettings: React.Dispatch<React.SetStateAction<{ ollamaModel: string; ollamaUrl: string }>>;
  isOpportunitiesOpen: boolean;
  setIsOpportunitiesOpen: React.Dispatch<React.SetStateAction<boolean>>;
  selectedOpportunityId: string | null;
  setSelectedOpportunityId: React.Dispatch<React.SetStateAction<string | null>>;
  systemStatus: 'booting' | 'ready' | 'error';
  setSystemStatus: React.Dispatch<React.SetStateAction<'booting' | 'ready' | 'error'>>;
  bootLog: string;
  setBootLog: React.Dispatch<React.SetStateAction<string>>;
  // Refs
  startTimeRef: React.MutableRefObject<number | null>;
  queueRef: React.MutableRefObject<string[]>;
  queueIndexRef: React.MutableRefObject<number>;
  triggerNextQueuePortalRef: React.MutableRefObject<() => Promise<void>>;
  // Functions
  handleStartHunt: (portalId: string) => Promise<void>;
  handleStopHunt: () => Promise<void>;
  handleSavePortal: (portal: Portal) => Promise<void>;
  handleDeletePortal: (id: string) => Promise<void>;
  handleTogglePortalStatus: (id: string, currentStatus: string) => Promise<void>;
  triggerQueueHunt: (portalIds: string[]) => Promise<void>;
  loadPortals: () => Promise<void>;
  loadOpportunities: () => Promise<void>;
  bootstrapEngines: () => Promise<void>;
  checkOllama: () => Promise<void>;
}

const AppContext = createContext<AppContextProps | undefined>(undefined);

export const useAppContext = (): AppContextProps => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used within AppProvider');
  return ctx;
};

export const AppProvider = ({ children }: { children: ReactNode }) => {
  // ---------- State ----------
  const [hunting, setHunting] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState('Checking...');
  const [sessionId, setSessionId] = useState('');
  const [huntLogs, setHuntLogs] = useState<string[]>([]);
  const [schedulerInfo, setSchedulerInfo] = useState('');
  const [portals, setPortals] = useState<Portal[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPortal, setEditingPortal] = useState<Portal | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('sentinel_settings');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error('Failed to parse settings from localStorage:', e);
    }
    return { ollamaModel: '', ollamaUrl: 'http://127.0.0.1:11434' };
  });

  useEffect(() => {
    localStorage.setItem('sentinel_settings', JSON.stringify(settings));
  }, [settings]);

  const [isOpportunitiesOpen, setIsOpportunitiesOpen] = useState(false);
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [systemStatus, setSystemStatus] = useState<'booting' | 'ready' | 'error'>('booting');
  const [bootLog, setBootLog] = useState('Initializing Control Unit...');

  // ---------- Refs ----------
  const startTimeRef = useRef<number | null>(null);
  const queueRef = useRef<string[]>([]);
  const queueIndexRef = useRef<number>(-1);
  const triggerNextQueuePortalRef = useRef<() => Promise<void>>(async () => {});

  // ---------- Service Wrappers (will be delegated to services later) ----------
  const loadPortals = async () => {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      const result = await db.select<any[]>(
        'SELECT id, name, base_url as url, scraper_module, keywords, status, selector_config, last_run_at, last_run_duration_ms, opportunities_count, rendering_mode, cloudflare_bypass_score FROM portals'
      );
      setPortals(result as Portal[]);
    } catch (error) {
      console.error('Failed to load portals:', error);
    }
  };

  const loadOpportunities = async () => {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      const result = await db.select<any[]>(
        'SELECT o.id, o.title, o.issuing_org, o.deadline_at as date, o.status, p.name as portal FROM opportunities o JOIN portals p ON o.portal_id = p.id ORDER BY o.created_at DESC'
      );
      setOpportunities(result as Opportunity[]);
    } catch (error) {
      console.error('Failed to load opportunities:', error);
    }
  };

  // ---------- Core Functions (extracted from original App.tsx) ----------
  const handleStartHunt = async (portalId: string) => {
    try {
      setHunting(true);
      setHuntLogs([
        `[${new Date().toLocaleTimeString()}] Spawning headless Chromium browser engine...`,
      ]);
      startTimeRef.current = Date.now();

      const portal = portals.find(p => p.id === portalId);
      const id = await invoke('start_hunt_session', { portalId, config: JSON.stringify(portal) });
      setSessionId(id as string);
    } catch (error) {
      console.error('Failed to start hunt:', error);
      setHunting(false);
      setHuntLogs(prev => [
        ...prev,
        `[ERROR] Failed to start hunt: ${error instanceof Error ? error.message : String(error)}`,
      ]);
    }
  };

  const handleStopHunt = async () => {
    try {
      await invoke('stop_hunt_session', { sessionId });
      setHunting(false);
      setSessionId('');
    } catch (error) {
      console.error('Failed to stop hunt:', error);
    }
  };

  const handleSavePortal = async (portal: Portal) => {
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
        void invoke('detect_portal', { url: portal.url });
      }
      void loadPortals();
    } catch (error) {
      console.error('Failed to save portal:', error);
    }
  };

  const handleDeletePortal = async (id: string) => {
    try {
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('DELETE FROM portals WHERE id = ?', [id]);
      setPortals(prev => prev.filter(p => p.id !== id));
    } catch (error) {
      console.error('Failed to delete portal:', error);
    }
  };

  const handleTogglePortalStatus = async (id: string, currentStatus: string) => {
    try {
      const nextStatus = currentStatus === 'Active' ? 'Inactive' : 'Active';
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('UPDATE portals SET status = ? WHERE id = ?', [nextStatus, id]);
      void loadPortals();
    } catch (error) {
      console.error('Failed to toggle portal status:', error);
    }
  };

  const finishActiveHunt = async (portalId: string) => {
    try {
      const startTime = startTimeRef.current || Date.now();
      const duration = Date.now() - startTime;
      const localDate = new Date(Date.now() + 5 * 60 * 60 * 1000);
      const timestamp = localDate.toISOString().replace('T', ' ').substring(0, 19) + ' (GMT+5)';

      const db = await SqlDatabase.load('sqlite:sentinel.db');
      const countRes = await db.select<any[]>(
        'SELECT COUNT(*) as cnt FROM opportunities WHERE portal_id = ?',
        [portalId]
      );
      const oppCount = countRes[0]?.cnt || 0;

      const portal = portals.find(p => p.id === portalId);
      const renderingMode = portal?.selector_config || portalId === 'xbfs76tfq'
        ? 'Browser (Playwright)'
        : 'Static HTML';
      const guardScore = 'Low Risk';

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
  };

  const triggerNextQueuePortal = async () => {
    const nextIndex = queueIndexRef.current + 1;
    if (nextIndex < queueRef.current.length) {
      queueIndexRef.current = nextIndex;
      const nextPortalId = queueRef.current[nextIndex];
      setHuntLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Queue progress: Starting next website hunt (${nextIndex + 1}/${queueRef.current.length})...`,
      ]);

      setTimeout(async () => {
        try {
          const db = await SqlDatabase.load('sqlite:sentinel.db');
          const portalsRes = await db.select<any[]>('SELECT * FROM portals');
          const portal = portalsRes.find(p => p.id === nextPortalId);
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
            void triggerNextQueuePortal();
          }
        } catch (err) {
          console.error('Failed to start next queue hunt:', err);
          setHuntLogs(prev => [
            ...prev,
            `[ERROR] Failed to start next website hunt: ${err instanceof Error ? err.message : String(err)}`,
          ]);
          void triggerNextQueuePortal();
        }
      }, 2000);
    } else {
      queueRef.current = [];
      queueIndexRef.current = -1;
      setHunting(false);
      setHuntLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] All sequential website hunts completed successfully!`,
      ]);
    }
  };

  const triggerQueueHunt = async (portalIds: string[]) => {
    queueRef.current = portalIds;
    queueIndexRef.current = 0;
    if (portalIds.length > 0) {
      const firstPortalId = portalIds[0];
      await handleStartHunt(firstPortalId);
    }
  };

  const bootstrapEngines = async () => {
    try {
      setBootLog('Running Control Unit script...');
      const log = await invoke('bootstrap_system');
      console.log('Bootstrap complete:', log);
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      await db.execute('DELETE FROM opportunities WHERE id IN (?, ?)', ['101', '102']);
      await db.execute("DELETE FROM opportunities WHERE title LIKE 'Found result for %'");
      await db.execute('DELETE FROM portals WHERE id = ?', ['1']);

      const activePortalsList = await db.select<any[]>('SELECT id, base_url, selector_config FROM portals');
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
      setTimeout(() => setSystemStatus('ready'), 1000);
    } catch (error) {
      console.error('Bootstrap failed:', error);
      setBootLog(`Boot Error: ${error instanceof Error ? error.message : String(error)}`);
      setSystemStatus('error');
    }
  };

  const checkOllama = async () => {
    setOllamaStatus('Checking...');
    try {
      const status = await invoke('check_ollama_status', { url: settings.ollamaUrl });
      setOllamaStatus(status as string);
      if (status === 'Online') {
        const modelList = await invoke<string[]>('get_ollama_models', { url: settings.ollamaUrl });
        if (modelList.length > 0) {
          setSettings((prev: { ollamaModel: string; ollamaUrl: string }) => ({
            ...prev,
            ollamaModel: modelList.includes(prev.ollamaModel) ? prev.ollamaModel : modelList[0],
          }));
        }
      }
    } catch (error) {
      console.error('Failed to check Ollama:', error);
      setOllamaStatus('Offline');
    }
  };

  // ---------- Tauri Event Listeners ----------
  useEffect(() => {
    const isTauri = typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS?.transformCallback;
    if (!isTauri) return;

    const unlistenPortal = listen('sentinel://hunter/portal-detected', async (event: any) => {
      const report = event.payload;
      const db = await SqlDatabase.load('sqlite:sentinel.db');
      let searchSelector = report.searchSelector || '';
      if (!searchSelector && report.scrapingOptions && report.scrapingOptions[0]) {
        const desc = report.scrapingOptions[0].description || '';
        if (desc.includes(': ')) {
          searchSelector = desc.split(': ')[1];
        }
      }
      const config = { searchSelector };
      const sanitizedUrl = report.url.replace(/\/+$/, '');
      await db.execute(
        'UPDATE portals SET selector_config = ?, rendering_mode = ? WHERE base_url = ? OR base_url = ? OR base_url LIKE ?',
        [JSON.stringify(config), 'Browser (Playwright)', sanitizedUrl, sanitizedUrl + '/', `%${sanitizedUrl}%`]
      );
      void loadPortals();
    });

    const unlistenOpp = listen('sentinel://hunter/opportunity-found', async (event: any) => {
      const opp = event.payload;
      try {
        const db = await SqlDatabase.load('sqlite:sentinel.db');
        const oppId = opp.id || Math.random().toString(36).substr(2, 9);
        const portalId = opp.portalId || '1';
        const existing = await db.select<any[]>('SELECT title FROM opportunities');
        const normalizedInputTitle = opp.title.trim().replace(/\\s+/g, ' ');
        const isDuplicate = existing.some(row => row.title.trim().replace(/\\s+/g, ' ').toLowerCase() === normalizedInputTitle.toLowerCase());
        if (!isDuplicate) {
          await db.execute(
            'INSERT INTO opportunities (id, portal_id, title, issuing_org, deadline_at, status) VALUES (?, ?, ?, ?, ?, ?)',
            [oppId, portalId, normalizedInputTitle, opp.agency || 'Unknown Agency', opp.dueDate || '2026-06-30', 'discovered']
          );
          await db.execute('UPDATE portals SET opportunities_count = COALESCE(opportunities_count, 0) + 1 WHERE id = ?', [portalId]);
          void loadOpportunities();
          void loadPortals();
        }
      } catch (e) {
        console.error('Error handling opportunity-found event', e);
      }
    });

    const unlistenProgress = listen('sentinel://hunter/progress', async (event: any) => {
      const payload = event.payload;
      if (payload.message) {
        setHuntLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${payload.message}`]);
        if (payload.message === 'Hunt completed successfully') {
          await finishActiveHunt(payload.portalId);
        }
      }
    });

    const unlistenError = listen('sentinel://hunter/error', async (event: any) => {
      const payload = event.payload;
      if (payload.message) {
        setHuntLogs(prev => [...prev, `[ERROR] ${payload.message}`]);
      }
      void loadPortals();
      void triggerNextQueuePortalRef.current();
    });

    return () => {
      unlistenPortal.then(f => f?.());
      unlistenOpp.then(f => f?.());
      unlistenProgress.then(f => f?.());
      unlistenError.then(f => f?.());
    };
  }, []);

  // ---------- Scheduler UI Updates ----------
  useEffect(() => {
    function updateSchedulerStatus() {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;
      const lastRunStr = localStorage.getItem('sentinel_last_auto_hunt_timestamp');
      let lastRunText = 'Never';
      if (lastRunStr) {
        const diffMin = Math.floor((Date.now() - parseInt(lastRunStr, 10)) / 60000);
        if (diffMin < 60) lastRunText = `${diffMin}m ago`;
        else lastRunText = `${Math.floor(diffMin / 60)}h ago`;
      }
      if (inWindow) setSchedulerInfo(`Active Window • Last Auto-Run: ${lastRunText}`);
      else setSchedulerInfo(`Idle (Window: 09:00 AM - 11:59 AM) • Last: ${lastRunText}`);
    }
    updateSchedulerStatus();
    const interval = setInterval(updateSchedulerStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // ---------- Automated Hourly Hunt ----------
  useEffect(() => {
    const checkAndTriggerAutoHunt = () => {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;
      if (!inWindow || hunting || portals.length === 0) return;
      const lastRunStr = localStorage.getItem('sentinel_last_auto_hunt_timestamp');
      const oneHourMs = 3600000;
      const shouldTrigger = !lastRunStr || Date.now() - parseInt(lastRunStr, 10) >= oneHourMs;
      if (shouldTrigger) {
        console.log('Automated scheduler: Triggering hourly hunts for all active websites...');
        localStorage.setItem('sentinel_last_auto_hunt_timestamp', Date.now().toString());
        const activePortals = portals.filter(p => p.status === 'Active');
        if (activePortals.length > 0) {
          setHuntLogs([`[${new Date().toLocaleTimeString()}] [AUTOMATED] Triggering scheduled hourly hunt...`]);
          void triggerQueueHunt(activePortals.map(p => p.id));
        }
      }
    };
    checkAndTriggerAutoHunt();
    const interval = setInterval(checkAndTriggerAutoHunt, 30000);
    return () => clearInterval(interval);
  }, [portals, hunting]);

  // Keep triggerNextQueuePortalRef up‑to‑date and trigger boot sequence
  useEffect(() => {
    triggerNextQueuePortalRef.current = triggerNextQueuePortal;
    void bootstrapEngines();
    void checkOllama();
  }, []);

  const contextValue: AppContextProps = {
    hunting,
    setHunting,
    ollamaStatus,
    setOllamaStatus,
    sessionId,
    setSessionId,
    huntLogs,
    setHuntLogs,
    schedulerInfo,
    setSchedulerInfo,
    portals,
    setPortals,
    opportunities,
    setOpportunities,
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
    setSystemStatus,
    bootLog,
    setBootLog,
    startTimeRef,
    queueRef,
    queueIndexRef,
    triggerNextQueuePortalRef,
    handleStartHunt,
    handleStopHunt,
    handleSavePortal,
    handleDeletePortal,
    handleTogglePortalStatus,
    triggerQueueHunt,
    loadPortals,
    loadOpportunities,
    bootstrapEngines,
    checkOllama,
  };

  return <AppContext.Provider value={contextValue}>{children}</AppContext.Provider>;
};
