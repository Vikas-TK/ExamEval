import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  BarChart2, Download, RefreshCw, Users, Award, ChevronDown, ChevronUp,
  FileSpreadsheet, TrendingUp, TrendingDown
} from 'lucide-react';

function pctColor(pct) {
  if (pct >= 75) return '#10b981';
  if (pct >= 50) return '#f59e0b';
  return '#ef4444';
}

function CellMark({ score, max }) {
  if (score == null) return <span style={{ color: '#374151' }}>—</span>;
  const pct = max > 0 ? (score / max) * 100 : 0;
  return (
    <span style={{
      fontWeight: 600, fontSize: 13,
      color: pct >= 75 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171',
    }}>{score}</span>
  );
}

export default function MarksMatrixPage({ apiKey }) {
  const [blueprints, setBlueprints] = useState([]);
  const [blueprintId, setBlueprintId] = useState('');
  const [matrix, setMatrix] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState('register_number');
  const [sortDir, setSortDir] = useState(1);

  const headers = apiKey ? { 'x-api-key': apiKey } : {};

  useEffect(() => {
    axios.get('/api/blueprints', { headers, params: { page_size: 100 } })
      .then(r => setBlueprints(r.data.items || r.data || [])).catch(() => {});
  }, []);

  const loadMatrix = useCallback(() => {
    if (!blueprintId) return;
    setLoading(true);
    axios.get(`/api/evaluate/matrix/${blueprintId}`, { headers })
      .then(r => setMatrix(r.data))
      .catch(err => toast.error(err.response?.data?.detail || 'Failed to load matrix'))
      .finally(() => setLoading(false));
  }, [blueprintId]);

  useEffect(() => { loadMatrix(); }, [loadMatrix]);

  const downloadCSV = async () => {
    if (!blueprintId) return;
    try {
      const res = await axios.get(`/api/evaluate/matrix/${blueprintId}/download`, {
        headers, responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `marks_matrix_${blueprintId.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('CSV downloaded');
    } catch { toast.error('Download failed'); }
  };

  const sortedRows = matrix ? [...matrix.rows].sort((a, b) => {
    let av = sortKey === 'grand_total' ? a.grand_total
      : sortKey === 'percentage' ? a.percentage
      : a.register_number;
    let bv = sortKey === 'grand_total' ? b.grand_total
      : sortKey === 'percentage' ? b.percentage
      : b.register_number;
    if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
    return (av - bv) * sortDir;
  }) : [];

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => -d);
    else { setSortKey(key); setSortDir(-1); } // default descending for numbers
  };

  // Stats
  const avgPct = matrix?.rows.length
    ? (matrix.rows.reduce((s, r) => s + r.percentage, 0) / matrix.rows.length).toFixed(1) : 0;
  const topStudent = matrix?.rows.length
    ? matrix.rows.reduce((a, b) => a.percentage > b.percentage ? a : b, matrix.rows[0]) : null;
  const passCount = matrix?.rows.filter(r => r.percentage >= 40).length || 0;

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(79,70,229,0.25)',
          }}>
            <FileSpreadsheet size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
              Faculty Marks Matrix
            </h1>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: '#475569', fontWeight: 500 }}>
              Marks per question, section and total for all students — Downloadable
            </p>
          </div>
        </div>
        {matrix && (
          <button onClick={downloadCSV} style={{
            padding: '11px 20px', borderRadius: 10, border: 'none',
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)', color: '#ffffff', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700,
            boxShadow: '0 4px 12px rgba(79,70,229,0.25)',
          }}>
            <Download size={15} /> Download CSV Matrix
          </button>
        )}
      </div>

      {/* Blueprint selector */}
      <div style={{
        background: '#ffffff', border: '1px solid #e2e8f0',
        borderRadius: 16, padding: 22, marginBottom: 28,
        display: 'flex', gap: 16, alignItems: 'flex-end',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, fontWeight: 700, color: '#4338ca', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Select Exam Blueprint
          </label>
          <select value={blueprintId} onChange={e => setBlueprintId(e.target.value)} style={{
            width: '100%', padding: '12px 14px', background: '#ffffff',
            border: '1px solid #cbd5e1', borderRadius: 10,
            color: '#0f172a', fontSize: 13, fontWeight: 600, outline: 'none',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)', cursor: 'pointer',
          }}>
            <option value="" style={{ color: '#94a3b8' }}>— Select Exam Blueprint —</option>
            {blueprints.map(bp => {
              const meta = bp.metadata || {};
              const subj = bp.subject || meta.subject || meta.subject_code || 'Subject';
              const code = bp.subject_code || meta.subject_code || '';
              const exam = bp.exam_name || meta.exam_name || 'Exam';
              const sem = bp.semester || meta.semester || '';
              const label = `${subj}${code ? ` (${code})` : ''} — ${exam}${sem ? ` [${sem}]` : ''}`;
              return (
                <option key={bp.blueprint_id} value={bp.blueprint_id}>
                  {label}
                </option>
              );
            })}
          </select>
        </div>
        <button onClick={loadMatrix} disabled={!blueprintId || loading} style={{
          padding: '12px 20px', borderRadius: 10, border: '1px solid #cbd5e1', cursor: 'pointer',
          background: '#f8fafc', color: '#4338ca', fontWeight: 700,
          display: 'flex', alignItems: 'center', gap: 7, fontSize: 13,
          opacity: !blueprintId ? 0.5 : 1, boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
        }}>
          <RefreshCw size={14} style={loading ? { animation: 'spin 1s linear infinite' } : {}} />
          Refresh Matrix
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
          <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: 10 }} />
          <div>Building marks matrix…</div>
        </div>
      )}

      {matrix && !loading && (
        <>
          {/* Stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 24 }}>
            {[
              { icon: Users, label: 'Total Students', value: matrix.total_students, color: '#4f46e5' },
              { icon: BarChart2, label: 'Class Average', value: `${avgPct}%`, color: '#d97706' },
              { icon: Award, label: 'Passed (≥40%)', value: passCount, color: '#059669' },
              { icon: TrendingUp, label: 'Top Score', value: topStudent ? `${topStudent.grand_total}/${topStudent.maximum_total}` : '—', color: '#047857' },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} style={{
                background: '#ffffff', border: '1px solid #e2e8f0',
                borderRadius: 14, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 14,
                boxShadow: '0 2px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon size={18} color={color} />
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#0f172a' }}>{value}</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>{label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Exam info */}
          <div style={{ marginBottom: 16, fontSize: 14, color: '#475569', fontWeight: 600 }}>
            <strong style={{ color: '#0f172a' }}>{matrix.exam_name}</strong> ·{' '}
            {matrix.subject} ({matrix.subject_code})
          </div>

          {/* Marks table */}
          <div style={{
            background: '#ffffff', border: '1px solid #cbd5e1',
            borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  {/* Section header row */}
                  <tr style={{ background: '#f1f5f9' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', color: '#334155', fontWeight: 700, borderBottom: '1px solid #cbd5e1', minWidth: 140, position: 'sticky', left: 0, background: '#f1f5f9' }}>
                      Student Reg No / ID
                    </th>
                    {matrix.section_headers.map(sh => {
                      const count = matrix.question_headers.filter(q => q.section_name === sh.section_name).length;
                      return (
                        <th key={sh.section_name} colSpan={count + 1}
                          style={{ padding: '10px 12px', textAlign: 'center', color: '#6b21a8', fontWeight: 700, borderBottom: '1px solid #cbd5e1', borderLeft: '1px solid #cbd5e1', background: '#f3e8ff' }}>
                          {sh.section_name} ({sh.section_max}m)
                        </th>
                      );
                    })}
                    <th colSpan={3} style={{ padding: '10px 12px', textAlign: 'center', color: '#047857', fontWeight: 700, borderBottom: '1px solid #cbd5e1', borderLeft: '1px solid #cbd5e1', background: '#d1fae5' }}>
                      Overall Total
                    </th>
                  </tr>
                  {/* Question number row */}
                  <tr style={{ background: '#f8fafc' }}>
                    <th onClick={() => handleSort('register_number')} style={{
                      padding: '10px 16px', textAlign: 'left', color: '#475569', cursor: 'pointer', borderBottom: '2px solid #cbd5e1', position: 'sticky', left: 0, background: '#f8fafc', fontWeight: 700,
                    }}>
                      Register No.
                    </th>
                    {matrix.section_headers.map(sh =>
                      matrix.question_headers
                        .filter(q => q.section_name === sh.section_name)
                        .map(q => (
                          <th key={q.question_number} style={{
                            padding: '10px 12px', textAlign: 'center', color: '#334155', fontWeight: 700,
                            borderBottom: '2px solid #cbd5e1',
                            borderLeft: '1px solid #e2e8f0', minWidth: 65,
                          }}>
                            Q{q.question_number}<br />
                            <span style={{ color: '#64748b', fontWeight: 500, fontSize: 11 }}>({q.maximum_marks}m)</span>
                          </th>
                        ))
                        .concat([
                          <th key={`${sh.section_name}-total`} style={{
                            padding: '10px 12px', textAlign: 'center', color: '#6b21a8', fontWeight: 700,
                            borderBottom: '2px solid #cbd5e1',
                            borderLeft: '1px solid #cbd5e1', background: '#faf5ff',
                          }}>Sub Total</th>
                        ])
                    )}
                    <th onClick={() => handleSort('grand_total')} style={{ padding: '10px 12px', textAlign: 'center', color: '#047857', fontWeight: 700, cursor: 'pointer', borderBottom: '2px solid #cbd5e1', borderLeft: '1px solid #cbd5e1', background: '#ecfdf5' }}>
                      Total Score
                    </th>
                    <th style={{ padding: '10px 12px', textAlign: 'center', color: '#64748b', fontWeight: 700, borderBottom: '2px solid #cbd5e1', background: '#ecfdf5' }}>
                      Max
                    </th>
                    <th onClick={() => handleSort('percentage')} style={{ padding: '10px 12px', textAlign: 'center', color: '#047857', fontWeight: 700, cursor: 'pointer', borderBottom: '2px solid #cbd5e1', background: '#ecfdf5' }}>
                      Percentage
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, ri) => (
                    <tr key={row.evaluation_id} style={{
                      background: ri % 2 === 0 ? '#ffffff' : '#f8fafc',
                      transition: 'background 0.15s',
                    }}
                      onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
                      onMouseLeave={e => e.currentTarget.style.background = ri % 2 === 0 ? '#ffffff' : '#f8fafc'}
                    >
                      <td style={{
                        padding: '12px 16px', color: '#0f172a', fontWeight: 700,
                        borderBottom: '1px solid #e2e8f0',
                        position: 'sticky', left: 0, background: ri % 2 === 0 ? '#ffffff' : '#f8fafc',
                        fontFamily: 'monospace', fontSize: 12,
                      }}>
                        {row.register_number}
                      </td>
                      {matrix.section_headers.map(sh =>
                        matrix.question_headers
                          .filter(q => q.section_name === sh.section_name)
                          .map(q => (
                            <td key={q.question_number} style={{
                              padding: '12px 12px', textAlign: 'center',
                              borderBottom: '1px solid #e2e8f0',
                              borderLeft: '1px solid #f1f5f9',
                            }}>
                              <CellMark score={row.question_scores[q.question_number]} max={q.maximum_marks} />
                            </td>
                          ))
                          .concat([
                            <td key={`${sh.section_name}-st`} style={{
                              padding: '12px 12px', textAlign: 'center', fontWeight: 800, color: '#7e22ce',
                              borderBottom: '1px solid #e2e8f0',
                              borderLeft: '1px solid #e9d5ff',
                              background: '#faf5ff',
                            }}>
                              {(row.section_totals[sh.section_name] ?? 0).toFixed(1)}
                            </td>
                          ])
                      )}
                      <td style={{
                        padding: '12px 12px', textAlign: 'center', fontWeight: 800,
                        color: pctColor(row.percentage), fontSize: 15,
                        borderBottom: '1px solid #e2e8f0',
                        borderLeft: '1px solid #a7f3d0',
                        background: '#ecfdf5',
                      }}>
                        {row.grand_total.toFixed(1)}
                      </td>
                      <td style={{ padding: '12px 12px', textAlign: 'center', color: '#64748b', fontWeight: 600, borderBottom: '1px solid #e2e8f0', background: '#ecfdf5' }}>
                        {row.maximum_total}
                      </td>
                      <td style={{
                        padding: '12px 12px', textAlign: 'center', fontWeight: 800,
                        color: pctColor(row.percentage), fontSize: 14,
                        borderBottom: '1px solid #e2e8f0', background: '#ecfdf5',
                      }}>
                        {row.percentage}%
                      </td>
                    </tr>
                  ))}
                  {sortedRows.length === 0 && (
                    <tr>
                      <td colSpan={100} style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
                        No evaluation results found for this blueprint yet.<br />
                        <span style={{ fontSize: 13, color: '#94a3b8' }}>Run Phase 4 evaluation for each student first on the AI Evaluation page.</span>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ fontSize: 12, color: '#64748b', marginTop: 12, textAlign: 'right', fontWeight: 500 }}>
            🟢 ≥75% &nbsp;|&nbsp; 🟡 50–74% &nbsp;|&nbsp; 🔴 &lt;50% &nbsp;·&nbsp; Click table header columns to sort
          </div>
        </>
      )}

      {!matrix && !loading && blueprintId && (
        <div style={{ textAlign: 'center', padding: 56, background: '#ffffff', borderRadius: 16, border: '1px dashed #cbd5e1', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <FileSpreadsheet size={40} color="#4f46e5" style={{ marginBottom: 12 }} />
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0f172a' }}>No evaluation results yet for this blueprint</div>
          <div style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>Run Phase 4 evaluation for students first on the AI Evaluation page.</div>
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        select option { background: #ffffff; color: #0f172a; }
      `}</style>
    </div>
  );
}
