import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BarChart3, HelpCircle, Layers, Filter, Search, Sparkles } from 'lucide-react';
import { Card, LoadingState, PageHeader, StatusBadge } from '../components/ui';

export default function QuestionAnalysisPage({ apiKey }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [filterSubject, setFilterSubject] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const params = filterSubject ? { subject_code: filterSubject } : {};
      const response = await axios.get('/api/analytics/question-analysis', { params, headers });
      setData(response.data);
    } catch (err) {
      toast.error('Could not load question analysis metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterSubject, apiKey]);

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Analytics / Item Analysis"
        title="Question Analysis"
        description="Deep-dive into question difficulty taxonomy, mark distributions, and evaluation confidence across blueprints."
      />

      <div className="metric-grid">
        <div className="metric-card">
          <span className="metric-label">Questions Analyzed</span>
          <strong className="metric-value">{data?.total_questions_analyzed ?? '—'}</strong>
          <small className="metric-change">Across active blueprints</small>
        </div>
        <div className="metric-card yellow-tone">
          <span className="metric-label">Short Answer Items</span>
          <strong className="metric-value">{data?.taxonomy_breakdown?.SHORT_ANSWER ?? 0}</strong>
          <small className="metric-change">2 to 5 marks taxonomy</small>
        </div>
        <div className="metric-card green-tone">
          <span className="metric-label">Descriptive Questions</span>
          <strong className="metric-value">{data?.taxonomy_breakdown?.DESCRIPTIVE ?? 0}</strong>
          <small className="metric-change">10+ marks taxonomy</small>
        </div>
        <div className="metric-card blue-tone">
          <span className="metric-label">Diagram & Formula Items</span>
          <strong className="metric-value">
            {(data?.taxonomy_breakdown?.DIAGRAM ?? 0) + (data?.taxonomy_breakdown?.MCQ ?? 0)}
          </strong>
          <small className="metric-change">Specialized visual items</small>
        </div>
      </div>

      <Card title="Question Breakdown" description="Evaluated items ordered by blueprint sections">
        {loading ? (
          <LoadingState label="Analyzing blueprint questions..." />
        ) : (
          <div className="table-wrap">
            <table className="master-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Q. No</th>
                  <th>Question Text</th>
                  <th>Type</th>
                  <th>Max Marks</th>
                  <th>Difficulty</th>
                  <th>Average Score</th>
                </tr>
              </thead>
              <tbody>
                {(data?.questions || []).map((q, idx) => (
                  <tr key={idx}>
                    <td>
                      <strong>{q.subject_code}</strong>
                      <small>{q.subject}</small>
                    </td>
                    <td>
                      <strong className="mono">Q{q.question_number}</strong>
                    </td>
                    <td>{q.question_text}</td>
                    <td>
                      <span className="badge badge-active">{q.question_type}</span>
                    </td>
                    <td>{q.maximum_marks}</td>
                    <td>
                      <StatusBadge status={q.difficulty_level === 'Hard' ? 'NEEDS_REVIEW' : 'COMPLETED'} />
                    </td>
                    <td>
                      <strong>{q.avg_score_pct}%</strong>
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
