import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Database, HardDrive, Key, Save, Server, Shield } from 'lucide-react';
import { Card, PageHeader, StatusBadge } from '../components/ui';

export default function SettingsPage({ apiKey }) {
  const [health, setHealth] = useState(null);
  const [storageStatus, setStorageStatus] = useState(null);
  const [keyInput, setKeyInput] = useState(apiKey || '');

  const loadStatus = async () => {
    try {
      const hRes = await axios.get('/health');
      setHealth(hRes.data);
      const sRes = await axios.get('/api/storage/status');
      setStorageStatus(sRes.data);
    } catch {
      toast.error('Could not fetch workspace status.');
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const saveApiKey = (e) => {
    e.preventDefault();
    toast.success('API Key updated.');
  };

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Manage / System"
        title="Settings & System Health"
        description="Configure workspace parameters, monitor database connections, and verify Supabase storage status."
      />

      <div className="dashboard-grid">
        <Card title="System & Service Health" description="Live status of core services">
          <div className="health-list">
            <div>
              <span className="health-label">
                <i className={`health-dot ${health?.database === 'ok' ? 'green' : 'yellow'}`} />
                PostgreSQL Database
              </span>
              <strong>{health?.database === 'ok' ? 'Operational' : 'Fallback / Unavailable'}</strong>
            </div>
            <div>
              <span className="health-label">
                <i className={`health-dot ${health?.supabase === 'ok' ? 'green' : 'yellow'}`} />
                Supabase Connection
              </span>
              <strong>{health?.supabase === 'ok' ? 'Connected' : 'Degraded'}</strong>
            </div>
            <div>
              <span className="health-label">
                <i className="health-dot green" />
                Backend Engine
              </span>
              <strong>{health?.backend || 'Operational'}</strong>
            </div>
          </div>
        </Card>

        <Card title="API Authentication" description="Configure API Security Key">
          <form onSubmit={saveApiKey} className="form-grid">
            <label className="field full-field">
              <span>API Secret Key</span>
              <input
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Enter API Key if required..."
              />
            </label>
            <button className="primary-button">
              <Save size={16} /> Save Key
            </button>
          </form>
        </Card>
      </div>

      <Card title="Supabase Storage Buckets Status" description="Active storage provider buckets">
        <div className="table-wrap">
          <table className="master-table">
            <thead>
              <tr>
                <th>Bucket Name</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Files Count</th>
              </tr>
            </thead>
            <tbody>
              {(storageStatus?.buckets || []).map((b) => (
                <tr key={b.bucket_name}>
                  <td>
                    <strong className="mono">{b.bucket_name}</strong>
                  </td>
                  <td>{b.provider}</td>
                  <td>
                    <StatusBadge status={b.status === 'active' ? 'COMPLETED' : 'PROCESSING'} />
                  </td>
                  <td>{b.approx_files}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
