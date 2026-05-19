import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { AlertTriangle, CheckCircle, Search } from 'lucide-react';

interface Gap {
  area: string;
  description: string;
}

export function GapReport() {
  const [rfpId, setRfpId] = useState('');
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleAnalyze() {
    if (!rfpId.trim()) return;
    setLoading(true);
    try {
      // Call mock command
      const result = await invoke('analyze_gaps', { rfpId });
      setGaps(result as Gap[]);
    } catch (error) {
      console.error('Gap analysis failed:', error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card glass gap-report">
      <h3>Compliance & Gap Analysis</h3>
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
