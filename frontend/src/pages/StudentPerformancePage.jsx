import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Award, GraduationCap, Search, ShieldCheck, UserCheck } from 'lucide-react';
import { Card, LoadingState, PageHeader, StatusBadge } from '../components/ui';

export default function StudentPerformancePage({ apiKey }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [query, setQuery] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const params = query ? { search: query } : {};
      const response = await axios.get('/api/analytics/student-performance', { params, headers });
      setData(response.data);
    } catch (err) {
      toast.error('Could not load student performance data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(loadData, 250);
    return () => clearTimeout(timer);
  }, [query, apiKey]);

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Analytics / Performance"
        title="Student Performance"
        description="Zero-trust anonymized performance log with grade distributions and OCR confidence scores."
      />

      <div className="metric-grid">
        <div className="metric-card">
          <span className="metric-label">Evaluated Students</span>
          <strong className="metric-value">{data?.total_students ?? '—'}</strong>
          <small className="metric-change">Anonymized SHA-256 hashes</small>
        </div>
        <div className="metric-card green-tone">
          <span className="metric-label">Distinction (A+ / A)</span>
          <strong className="metric-value">
            {(data?.grade_distribution?.['A+'] || 0) + (data?.grade_distribution?.['A'] || 0)}
          </strong>
          <small className="metric-change">High confidence scores</small>
        </div>
        <div className="metric-card yellow-tone">
          <span className="metric-label">First Class (B)</span>
          <strong className="metric-value">{data?.grade_distribution?.['B'] || 0}</strong>
          <small className="metric-change">Satisfactory performance</small>
        </div>
        <div className="metric-card red-tone">
          <span className="metric-label">Re-appear (RA)</span>
          <strong className="metric-value">{data?.grade_distribution?.['RA'] || 0}</strong>
          <small className="metric-change">Action required</small>
        </div>
      </div>

      <Card title="Anonymized Student Performance Records">
        <div className="master-toolbar">
          <label className="master-search">
            <Search size={16} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by student hash or subject ID..."
              aria-label="Search student records"
            />
          </label>
          <span className="record-count">{data?.students?.length || 0} records</span>
        </div>

        {loading ? (
          <LoadingState label="Loading student performance data..." />
        ) : (
          <div className="table-wrap">
            <table className="master-table">
              <thead>
                <tr>
                  <th>Student Hash</th>
                  <th>Subject</th>
                  <th>Regulation</th>
                  <th>Semester</th>
                  <th>Status</th>
                  <th>OCR Confidence</th>
                  <th>Grade</th>
                </tr>
              </thead>
              <tbody>
                {(data?.students || []).map((s, idx) => (
                  <tr key={s.evaluation_id || idx}>
                    <td>
                      <strong className="mono text-xs">{s.student_hash}</strong>
                    </td>
                    <td>
                      <strong>{s.subject_id}</strong>
                    </td>
                    <td>{s.regulation}</td>
                    <td>{s.semester}</td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>
                      <strong>{s.ocr_confidence_pct}%</strong>
                    </td>
                    <td>
                      <span className="font-bold text-emerald-700">{s.predicted_grade}</span>
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
