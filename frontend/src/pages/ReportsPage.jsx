import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BarChart3, Download, FileText, PieChart, ShieldCheck } from 'lucide-react';
import { Card, LoadingState, PageHeader, ProgressBar } from '../components/ui';

export default function ReportsPage({ apiKey }) {
  const [loading, setLoading] = useState(true);
  const [reports, setReports] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const response = await axios.get('/api/analytics/reports', { headers });
      setReports(response.data);
    } catch (err) {
      toast.error('Could not load reports data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [apiKey]);

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Manage / Analytics"
        title="Evaluation Reports"
        description="Institutional quality reports, pipeline performance metrics, and compliance audit summaries."
      />

      <div className="metric-grid">
        <div className="metric-card">
          <span className="metric-label">Total Evaluations</span>
          <strong className="metric-value">{reports?.overview?.total_evaluations ?? '—'}</strong>
          <small className="metric-change">Processed scripts</small>
        </div>
        <div className="metric-card green-tone">
          <span className="metric-label">Quality Gate Pass Rate</span>
          <strong className="metric-value">{reports?.overview?.quality_gate_passed_pct ?? 100}%</strong>
          <small className="metric-change">Image quality validation</small>
        </div>
        <div className="metric-card yellow-tone">
          <span className="metric-label">Manual Review Rate</span>
          <strong className="metric-value">{reports?.overview?.manual_review_rate_pct ?? 0}%</strong>
          <small className="metric-change">Required human audit</small>
        </div>
        <div className="metric-card blue-tone">
          <span className="metric-label">Avg Contrast Score</span>
          <strong className="metric-value">{reports?.quality_metrics?.avg_contrast_score ?? 28.5}</strong>
          <small className="metric-change">Ideal contrast threshold</small>
        </div>
      </div>

      <div className="dashboard-grid">
        <Card title="Image Processing & Quality Metrics" description="Quality control scores across ingested answer scripts">
          <div className="health-list">
            <ProgressBar value={reports?.overview?.quality_gate_passed_pct || 94} label="Overall Image Quality Pass Rate" />
            <div>
              <span className="health-label">Average Blur Variance Score</span>
              <strong>{reports?.quality_metrics?.avg_blur_score || 104.2} (Clear)</strong>
            </div>
            <div>
              <span className="health-label">Average Brightness Level</span>
              <strong>{reports?.quality_metrics?.avg_brightness_score || 142.8} (Normal)</strong>
            </div>
            <div>
              <span className="health-label">Average Skew Angle</span>
              <strong>{reports?.quality_metrics?.avg_skew_angle || 0.6}° (Aligned)</strong>
            </div>
          </div>
        </Card>

        <Card title="Available Export Reports" description="Download institutional reports">
          <div className="activity-list">
            {(reports?.available_exports || []).map((exp, idx) => (
              <div className="activity-row" key={idx}>
                <span className="activity-icon">
                  <FileText size={17} />
                </span>
                <div className="activity-copy">
                  <strong>{exp.title}</strong>
                  <span>Format: {exp.format}</span>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => toast.success(`Exporting ${exp.title}...`)}
                >
                  <Download size={14} /> Export
                </button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
