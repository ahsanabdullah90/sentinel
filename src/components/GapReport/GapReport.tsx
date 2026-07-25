import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { AlertTriangle, CheckCircle, Search } from 'lucide-react';
import { useAppContext } from '../../context/AppContext';

interface Gap {
  area: string;
  description: string;
}

export function GapReport() {
  const { settings } = useAppContext();
  const [rfpId, setRfpId] = useState('');
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    if (!rfpId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      // Call mock command
      const result = await invoke('analyze_gaps', {
        rfpId,
        ollamaUrl: settings.ollamaUrl,
        ollamaModel: settings.ollamaModel,
      });
      setGaps(result as Gap[]);
    } catch (err: any) {
      console.error('Gap analysis failed:', err);
      setError(err?.message || String(err) || 'Gap analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card glass gap-report">
      <h3>Compliance & Gap Analysis</h3>
      {error && (
        <div style={{ color: '#ff453a', backgroundColor: 'rgba(255, 69, 58, 0.1)', padding: '10px', borderRadius: '8px', marginBottom: '15px', fontSize: '0.9rem', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}
      <div className="input-group" style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
        <input
          value={rfpId}
          onChange={(e) => {
            setRfpId(e.target.value);
          }}
          placeholder="Enter RFP ID (e.g. RFP-2026-001)"
          style={{ flex: 1 }}
          disabled={loading}
        />
        <button
          className="btn btn-primary"
          onClick={() => {
            void handleAnalyze();
          }}
          disabled={loading}
        >
          <Search size={16} /> {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      <div className="gap-list" style={{ maxHeight: '200px', overflowY: 'auto' }}>
        {gaps.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#8b90a0', padding: '20px' }}>
            <CheckCircle
              size={24}
              style={{ color: 'var(--success-color)', marginBottom: '10px' }}
            />
            <p>No gaps analyzed yet or system compliant.</p>
          </div>
        ) : (
          gaps.map((gap, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                gap: '10px',
                backgroundColor: 'rgba(255,255,255,0.05)',
                padding: '10px',
                borderRadius: '8px',
                marginBottom: '10px',
              }}
            >
              <AlertTriangle size={18} style={{ color: '#ff9500' }} />
              <div>
                <strong style={{ color: '#fff' }}>{gap.area}</strong>
                <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem', color: '#8b90a0' }}>
                  {gap.description}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
