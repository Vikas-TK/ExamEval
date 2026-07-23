import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Download, FileText, Filter, History, Search } from 'lucide-react';
import { Card, LoadingState, PageHeader, StatusBadge } from '../components/ui';

export default function HistoryPage({ apiKey }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const params = {
        search: query || undefined,
        status: statusFilter || undefined,
        page_size: 50,
      };
      const response = await axios.get('/api/analytics/history', { params, headers });
      setItems(response.data.items || []);
      setTotal(response.data.total || 0);
    } catch (err) {
      toast.error('Could not load evaluation history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(loadData, 250);
    return () => clearTimeout(timer);
  }, [query, statusFilter, apiKey]);

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Workspace / Logs"
        title="Evaluation History"
        description="Comprehensive audit log of all answer sheet evaluation submissions, quality gates, and processing outcomes."
      />

      <Card title="Audit History Log">
        <div className="master-toolbar">
          <label className="master-search">
            <Search size={16} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by subject code or ID..."
              aria-label="Search evaluation history"
            />
          </label>
          <div className="filter-row">
            <span className="filter-label">
              <Filter size={14} /> Filter status
            </span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All Statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="PROCESSING">Processing</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
          <span className="record-count">{total} total logs</span>
        </div>

        {loading ? (
          <LoadingState label="Loading evaluation history..." />
        ) : (
          <div className="table-wrap">
            <table className="master-table">
              <thead>
                <tr>
                  <th>Evaluation ID</th>
                  <th>Subject</th>
                  <th>Student Hash</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Quality Gate</th>
                  <th>Date & Time</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.evaluation_id}>
                    <td>
                      <strong className="mono text-xs">{item.evaluation_id}</strong>
                    </td>
                    <td>
                      <strong>{item.subject_id}</strong>
                    </td>
                    <td>
                      <small className="mono">{item.student_hash || 'Anonymized'}</small>
                    </td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td>
                      <strong>{item.confidence_pct}%</strong>
                    </td>
                    <td>
                      <span className={`badge ${item.quality_passed ? 'badge-active' : 'badge-inactive'}`}>
                        {item.quality_passed ? 'Passed' : 'Review Required'}
                      </span>
                    </td>
                    <td>
                      <small>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
