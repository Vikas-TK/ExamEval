import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  Brain, CheckCircle2, AlertTriangle, XCircle, RefreshCw,
  ChevronDown, ChevronUp, Sparkles, Star, BarChart2,
  Download, Eye, EyeOff, Hash, Award, BookOpen, Zap
} from 'lucide-react';

const API = '/api';

const STATUS_COLORS = {
  SCORED: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', icon: CheckCircle2 },
  SKIPPED: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', icon: AlertTriangle },
  ERROR: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: XCircle },
  PENDING: { color: '#6366f1', bg: 'rgba(99,102,241,0.1)', icon: RefreshCw },
};

function ScoreBar({ scored, maximum }) {
  const pct = maximum > 0 ? Math.min((scored / maximum) * 100, 100) : 0;
  const color = pct >= 70 ? '#059669' : pct >= 40 ? '#d97706' : '#dc2626';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        flex: 1, height: 7, borderRadius: 4,
        background: '#e2e8f0', overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 4,
          background: color, transition: 'width 0.5s ease',
        }} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 700, color, minWidth: 55, textAlign: 'right' }}>
        {scored}/{maximum}
      </span>
    </div>
  );
}

function AnswerCard({ record, index }) {
  const [expanded, setExpanded] = useState(false);
  const st = STATUS_COLORS[record.evaluation_status] || STATUS_COLORS.PENDING;
  const Icon = st.icon;
  const pct = record.maximum_marks > 0
    ? Math.round((record.scored_marks / record.maximum_marks) * 100) : 0;

  return (
    <div style={{
      background: '#ffffff', border: '1px solid #e2e8f0',
      borderRadius: 14, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
    }}>
      <div onClick={() => setExpanded(e => !e)} style={{
        padding: '16px 20px', cursor: 'pointer', userSelect: 'none',
        display: 'flex', alignItems: 'center', gap: 14, background: expanded ? '#f8fafc' : '#ffffff',
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, background: '#e0e7ff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, color: '#4338ca', flexShrink: 0,
        }}>{index + 1}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 800, color: '#0f172a', fontSize: 15 }}>
              Q{record.question_number}
            </span>
            {record.section_name && (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 9px', borderRadius: 20, background: '#f3e8ff', color: '#7e22ce' }}>
                {record.section_name}
              </span>
            )}
            <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: st.bg, color: st.color, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Icon size={12} /> {record.evaluation_status}
            </span>
          </div>
          <div style={{ marginTop: 6 }}>
            <ScoreBar scored={record.scored_marks ?? 0} maximum={record.maximum_marks} />
          </div>
        </div>

        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: pct >= 70 ? '#059669' : pct >= 40 ? '#d97706' : '#dc2626' }}>
            {record.scored_marks ?? '—'}
          </div>
          <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>/ {record.maximum_marks}m</div>
        </div>
        {expanded ? <ChevronUp size={16} color="#64748b" /> : <ChevronDown size={16} color="#64748b" />}
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid #e2e8f0', background: '#f8fafc', padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {record.question_text && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Question Description</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0f172a', lineHeight: 1.6 }}>{record.question_text}</div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Student Answer (Extracted)</div>
            <div style={{
              background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 10, padding: '14px 16px',
              fontSize: 13, color: '#0f172a', lineHeight: 1.7, whiteSpace: 'pre-wrap',
              maxHeight: 280, overflowY: 'auto', boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.03)',
            }}>
              {record.student_answer || <em style={{ color: '#94a3b8' }}>No answer written</em>}
            </div>
          </div>
          {record.answer_key && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Reference Answer Key</div>
              <div style={{ background: '#e0e7ff', border: '1px solid #c7d2fe', borderRadius: 8, padding: '12px 14px', fontSize: 13, color: '#3730a3', lineHeight: 1.6, fontWeight: 500 }}>
                {record.answer_key}
              </div>
            </div>
          )}
          {record.ai_feedback && (
            <div style={{
              background: '#ecfdf5', border: '1px solid #a7f3d0',
              borderRadius: 10, padding: '14px 16px',
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#047857', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={13} /> AI Evaluation Feedback &amp; Justification
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: '#065f46', lineHeight: 1.6 }}>{record.ai_feedback}</div>
              {record.ai_confidence != null && (
                <div style={{ fontSize: 11, fontWeight: 600, color: '#059669', marginTop: 6 }}>
                  Scoring Confidence: {(record.ai_confidence * 100).toFixed(0)}%
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function EvaluationRunPage({ apiKey }) {
  const [evaluations, setEvaluations] = useState([]);
  const [blueprints, setBlueprints] = useState([]);
  const [evalId, setEvalId] = useState('');
  const [blueprintId, setBlueprintId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);

  const headers = apiKey ? { 'x-api-key': apiKey } : {};

  useEffect(() => {
    axios.get('/api/evaluations', { headers, params: { page_size: 100 } })
      .then(r => setEvaluations(r.data.items || r.data || [])).catch(() => {});
    axios.get('/api/blueprints', { headers, params: { page_size: 100 } })
      .then(r => setBlueprints(r.data.items || r.data || [])).catch(() => {});
  }, []);

  const fetchRecords = useCallback((eid) => {
    if (!eid) return;
    setLoading(true);
    axios.get(`/api/evaluate/${eid}`, { headers })
      .then(r => setRecords(r.data || []))
      .catch(() => setRecords([]))
      .finally(() => setLoading(false));
  }, []);

  const handleRun = async () => {
    if (!evalId || !blueprintId) { toast.error('Select evaluation and blueprint'); return; }
    setRunning(true); setResult(null); setRecords([]);
    try {
      const { data } = await axios.post('/api/evaluate/run', {
        evaluation_id: evalId, blueprint_id: blueprintId,
      }, { headers });
      setResult(data);
      toast.success(`Evaluation complete — ${data.total_scored_marks}/${data.total_maximum_marks} marks`);
      fetchRecords(evalId);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally { setRunning(false); }
  };

  const downloadTranscript = async (fmt) => {
    if (!evalId) return;
    try {
      const res = await axios.get(`/api/evaluate/transcript/${evalId}/${fmt}`, {
        headers, responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcript_${evalId.slice(0,8)}.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error('Transcript download failed'); }
  };

  const totalQ = records.length;
  const scoredQ = records.filter(r => r.evaluation_status === 'SCORED').length;
  const totalScored = records.reduce((s, r) => s + (r.scored_marks || 0), 0);
  const totalMax = records.reduce((s, r) => s + (r.maximum_marks || 0), 0);
  const pct = totalMax > 0 ? ((totalScored / totalMax) * 100).toFixed(1) : 0;

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1050, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(5,150,105,0.25)',
          }}>
            <Sparkles size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
              Phase 4 — AI Answer Evaluation Engine
            </h1>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: '#475569', fontWeight: 500 }}>
              Score student answers using Qwen2.5-7B — faculty view only
            </p>
          </div>
        </div>
      </div>

      {/* Trigger card */}
      <div style={{
        background: '#ffffff', border: '1px solid #e2e8f0',
        borderRadius: 16, padding: 24, marginBottom: 28,
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}>
        <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Zap size={18} color="#059669" /> Run AI Evaluation
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 22 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#047857', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Student Evaluation Script
            </label>
            <select
              value={evalId}
              onChange={e => { setEvalId(e.target.value); setRecords([]); setResult(null); fetchRecords(e.target.value); }}
              style={{
                width: '100%', padding: '12px 14px', background: '#ffffff',
                border: '1px solid #cbd5e1', borderRadius: 10,
                color: '#0f172a', fontSize: 13, fontWeight: 600, outline: 'none',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)', cursor: 'pointer',
              }}
            >
              <option value="" style={{ color: '#94a3b8' }}>— Select Student Evaluation Script —</option>
              {evaluations.map(ev => {
                const sub = ev.subject_id || 'Script';
                const idShort = ev.evaluation_id ? ev.evaluation_id.slice(0, 8) : 'Evaluation';
                const st = ev.status || ev.evaluation_status || 'UNKNOWN';
                return (
                  <option key={ev.evaluation_id} value={ev.evaluation_id}>
                    {sub} · ID: {idShort}… ({st})
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#047857', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Exam Blueprint (Question Paper)
            </label>
            <select
              value={blueprintId}
              onChange={e => setBlueprintId(e.target.value)}
              style={{
                width: '100%', padding: '12px 14px', background: '#ffffff',
                border: '1px solid #cbd5e1', borderRadius: 10,
                color: '#0f172a', fontSize: 13, fontWeight: 600, outline: 'none',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)', cursor: 'pointer',
              }}
            >
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
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={handleRun} disabled={running || !evalId || !blueprintId} style={{
            padding: '12px 28px', borderRadius: 10, border: 'none', cursor: running ? 'wait' : 'pointer',
            background: running ? '#94a3b8' : 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
            color: '#fff', fontWeight: 700, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8,
            opacity: (!evalId || !blueprintId) ? 0.5 : 1,
            boxShadow: '0 4px 12px rgba(5,150,105,0.25)',
          }}>
            {running ? <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> Evaluating…</>
              : <><Sparkles size={16} /> Run AI Evaluation</>}
          </button>
          {evalId && (
            <>
              <button onClick={() => downloadTranscript('txt')} style={{
                padding: '12px 20px', borderRadius: 10, border: '1px solid #cbd5e1',
                background: '#ffffff', color: '#334155', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600,
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}>
                <Download size={14} color="#059669" /> Download TXT Transcript
              </button>
              <button onClick={() => downloadTranscript('pdf')} style={{
                padding: '12px 20px', borderRadius: 10, border: '1px solid #cbd5e1',
                background: '#ffffff', color: '#334155', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600,
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}>
                <Download size={14} color="#059669" /> Download PDF Transcript
              </button>
            </>
          )}
        </div>
      </div>

      {/* Result summary */}
      {result && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 28,
        }}>
          {[
            { label: 'Total Score', value: `${result.total_scored_marks}`, sub: `/ ${result.total_maximum_marks} max marks`, color: '#059669' },
            { label: 'Overall Percentage', value: `${result.percentage}%`, sub: result.percentage >= 40 ? 'Passed' : 'Needs attention', color: result.percentage >= 40 ? '#059669' : '#dc2626' },
            { label: 'Questions Scored', value: result.questions_evaluated, sub: 'answered by student', color: '#4f46e5' },
          ].map(({ label, value, sub, color }) => (
            <div key={label} style={{
              background: '#ffffff', border: '1px solid #e2e8f0',
              borderRadius: 16, padding: '18px 22px', boxShadow: '0 2px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ fontSize: 26, fontWeight: 800, color }}>{value}</div>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#64748b', marginTop: 2 }}>{sub}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Per-question results */}
      {(records.length > 0 || loading) && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
              <BookOpen size={18} color="#4f46e5" /> Scored Answers &amp; Theory Evaluation
              {records.length > 0 && (
                <span style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>
                  ({scoredQ}/{totalQ} scored · {totalScored.toFixed(1)}/{totalMax} total marks)
                </span>
              )}
            </h2>
          </div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
              <RefreshCw size={20} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
              <div>Loading scored answers…</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {records.map((rec, i) => <AnswerCard key={rec.eval_result_id} record={rec} index={i} />)}
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        select option { background: #ffffff; color: #0f172a; }
      `}</style>
    </div>
  );
}
