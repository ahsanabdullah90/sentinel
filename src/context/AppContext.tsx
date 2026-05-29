// src/context/AppContext.tsx
import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Portal, Opportunity } from '../types';

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
  const [lastAutoHuntTimestamp, setLastAutoHuntTimestamp] = useState<string | null>(null);
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

  // ---------- Private Refs ----------
  const startTimeRef = useRef<number | null>(null);
  const queueRef = useRef<string[]>([]);
  const queueIndexRef = useRef<number>(-1);
  const triggerNextQueuePortalRef = useRef<() => Promise<void>>(async () => {});

  // ---------- Persistent Scheduler Time Helpers ----------
  const loadSchedulerTimestamp = async (): Promise<string | null> => {
    try {
      const ts = await invoke<string | null>('get_scheduler_timestamp');
      setLastAutoHuntTimestamp(ts);
      return ts;
    } catch (e) {
      console.error('Failed to load scheduler timestamp from SQLite:', e);
      return null;
    }
  };

  const persistSchedulerTimestamp = async (ts: string) => {
    try {
      await invoke('set_scheduler_timestamp', { timestamp: ts });
      setLastAutoHuntTimestamp(ts);
    } catch (e) {
      console.error('Failed to set scheduler timestamp to SQLite:', e);
    }
  };

  // ---------- Service Wrappers (Delegating raw SQL to native Rust commands) ----------
  const loadPortals = async () => {
    try {
      const result = await invoke<Portal[]>('get_portals');
      setPortals(result);
    } catch (error) {
      console.error('Failed to load portals:', error);
    }
  };

  const loadOpportunities = async () => {
    try {
      const result = await invoke<Opportunity[]>('get_opportunities_list');
      setOpportunities(result);
    } catch (error) {
      console.error('Failed to load opportunities:', error);
    }
  };

  // ---------- Core Functions ----------
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
      const mappedPortal = {
        ...portal,
        id: editingPortal ? editingPortal.id : portal.id,
      };
      await invoke('save_portal', { portal: mappedPortal, isEdit: !!editingPortal });
      setEditingPortal(null);
      void loadPortals();
    } catch (error) {
      console.error('Failed to save portal:', error);
    }
  };

  const handleDeletePortal = async (id: string) => {
    try {
      await invoke('delete_portal', { id });
      setPortals(prev => prev.filter(p => p.id !== id));
    } catch (error) {
      console.error('Failed to delete portal:', error);
    }
  };

  const handleTogglePortalStatus = async (id: string, currentStatus: string) => {
    try {
      await invoke('toggle_portal_status', { id, currentStatus });
      void loadPortals();
    } catch (error) {
      console.error('Failed to toggle portal status:', error);
    }
  };

  const finishActiveHunt = async (portalId: string) => {
    try {
      const startTime = startTimeRef.current || Date.now();
      const duration = Date.now() - startTime;

      const countRes = opportunities.filter(o => o.portal === portals.find(p => p.id === portalId)?.name).length;
      const portal = portals.find(p => p.id === portalId);
      const renderingMode = portal?.selector_config || portalId === 'xbfs76tfq'
        ? 'Browser (Playwright)'
        : 'Static HTML';

      await invoke('finish_active_hunt', {
        portalId,
        durationMs: duration,
        oppCount: countRes,
        renderingMode,
      });

      console.log(`Successfully finished hunt for portal ${portalId}.`);
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
          const list = await invoke<Portal[]>('get_portals');
          const portal = list.find(p => p.id === nextPortalId);
          if (portal) {
            setHunting(true);
            startTimeRef.current = Date.now();
            const id = await invoke('start_hunt_session', {
              portalId: nextPortalId,
              config: JSON.stringify(portal),
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
      
      void loadSchedulerTimestamp();
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

  // ---------- Tauri Event Listeners (Refactored to rely on backend auto-persistence) ----------
  useEffect(() => {
    const isTauri = typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS?.transformCallback;
    if (!isTauri) return;

    const unlistenPortal = listen('sentinel://hunter/portal-detected', async () => {
      // Backend automatically persisted this. Just trigger a reload.
      void loadPortals();
    });

    const unlistenOpp = listen('sentinel://hunter/opportunity-found', async () => {
      // Backend automatically persisted this. Just trigger a reload.
      void loadOpportunities();
      void loadPortals();
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
  }, [opportunities, portals]);

  // ---------- Scheduler UI Updates ----------
  useEffect(() => {
    async function updateSchedulerStatus() {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;
      const lastRunStr = await loadSchedulerTimestamp();
      let lastRunText = 'Never';
      if (lastRunStr) {
        const diffMin = Math.floor((Date.now() - parseInt(lastRunStr, 10)) / 60000);
        if (diffMin < 60) lastRunText = `${diffMin}m ago`;
        else lastRunText = `${Math.floor(diffMin / 60)}h ago`;
      }
      if (inWindow) setSchedulerInfo(`Active Window • Last Auto-Run: ${lastRunText}`);
      else setSchedulerInfo(`Idle (Window: 09:00 AM - 11:59 AM) • Last: ${lastRunText}`);
    }
    void updateSchedulerStatus();
    const interval = setInterval(updateSchedulerStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // ---------- Automated Hourly Hunt ----------
  useEffect(() => {
    const checkAndTriggerAutoHunt = async () => {
      const now = new Date();
      const hour = now.getHours();
      const inWindow = hour >= 9 && hour < 12;
      if (!inWindow || hunting || portals.length === 0) return;
      const lastRunStr = lastAutoHuntTimestamp || await loadSchedulerTimestamp();
      const oneHourMs = 3600000;
      const shouldTrigger = !lastRunStr || Date.now() - parseInt(lastRunStr, 10) >= oneHourMs;
      if (shouldTrigger) {
        console.log('Automated scheduler: Triggering hourly hunts for all active websites...');
        await persistSchedulerTimestamp(Date.now().toString());
        const activePortals = portals.filter(p => p.status === 'Active');
        if (activePortals.length > 0) {
          setHuntLogs([`[${new Date().toLocaleTimeString()}] [AUTOMATED] Triggering scheduled hourly hunt...`]);
          void triggerQueueHunt(activePortals.map(p => p.id));
        }
      }
    };
    void checkAndTriggerAutoHunt();
    const interval = setInterval(checkAndTriggerAutoHunt, 30000);
    return () => clearInterval(interval);
  }, [portals, hunting, lastAutoHuntTimestamp]);

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
