import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { AlertTriangle, CheckCircle, Search, Loader } from 'lucide-react';

interface Gap {
  area: string;
  description: string;
  severity?: 'blocking' | 'advisory';
  suggestion?: string;
}

export function GapReport() {
  const [rfpText, setRfpText] = useState('');
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const unlistenProgress = listen('sentinel://gap-engine/progress', (event: any) => {
      setStatus(event.payload.message);
    });

    const unlistenReport = listen('sentinel://gap-engine/gap-report-generated', (event: any) => {
      setGaps(event.payload.gaps);
      setLoading(false);
      setStatus('Analysis complete.');
    });

    return () => {
      unlistenProgress.then(u => u());
      unlistenReport.then(u => u());
    };
  }, []);

  async function handleAnalyze() {
    if (!rfpText.trim()) return;
    setLoading(true);
    setGaps([]);
    setStatus('Initializing Gap Engine...');
    try {
      // In a real scenario, we'd fetch rfpText from DB by ID, but for now we take text
      await invoke('run_gap_analysis', {
        rfpText,
        mode: 'local', // Should come from settings
        model: 'phi3',
        url: 'http://127.0.0.1:11434'
      });
    } catch (error) {
      console.error('Gap analysis failed:', error);
      setLoading(false);
      setStatus('Error occurred during analysis.');
    }
  }

  return (
    <div className="card glass gap-report" style={{ marginTop: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
        <AlertTriangle size={20} style={{ color: 'var(--accent-color)' }} />
        <h3 style={{ margin: 0 }}>Compliance & Gap Analysis</h3>
      </div>

      <div className="input-group" style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.85rem', color: '#8b90a0' }}>
          RFP Content or Requirements Text
        </label>
        <textarea
          value={rfpText}
          onChange={(e) => setRfpText(e.target.value)}
          placeholder="Paste RFP text here to analyze for compliance gaps..."
          style={{
            width: '100%',
            minHeight: '100px',
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: 'rgba(0,0,0,0.2)',
            border: '1px solid rgba(255,255,255,0.05)',
            color: '#fff',
            resize: 'vertical'
          }}
          disabled={loading}
        />
      </div>

      <button
        className="btn btn-primary"
        onClick={() => {
          void handleAnalyze();
        }}
        disabled={loading || !rfpText.trim()}
        style={{ width: '100%', display: 'flex', justifyContent: 'center', gap: '8px' }}
      >
        {loading ? <Loader size={16} className="spin" /> : <Search size={16} />}
        {loading ? status : 'Analyze RFP for Gaps'}
      </button>

      {gaps.length > 0 && (
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {gaps.map((gap, idx) => (
            <div
              key={idx}
              style={{
                padding: '12px',
                borderRadius: '8px',
                backgroundColor: 'rgba(255,255,255,0.02)',
                border: '1px solid ' + (gap.severity === 'blocking' ? 'rgba(255,59,48,0.2)' : 'rgba(255,149,0,0.2)'),
                textAlign: 'left'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: gap.severity === 'blocking' ? '#ff3b30' : '#ff9500'
                }}>
                  {gap.area} - {gap.severity || 'advisory'}
                </span>
              </div>
              <p style={{ margin: '0 0 8px 0', fontSize: '0.9rem', color: '#fff' }}>{gap.description}</p>
              {gap.suggestion && (
                <div style={{ fontSize: '0.8rem', color: '#8b90a0', fontStyle: 'italic' }}>
                  Suggestion: {gap.suggestion}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {gaps.length === 0 && !loading && (
        <div style={{ marginTop: '15px', textAlign: 'center', color: '#8b90a0', fontSize: '0.85rem' }}>
          <CheckCircle size={32} style={{ color: 'rgba(52,199,89,0.2)', marginBottom: '10px', display: 'block', margin: '0 auto' }} />
          No gaps analyzed yet.
        </div>
      )}
    </div>
  );
}
