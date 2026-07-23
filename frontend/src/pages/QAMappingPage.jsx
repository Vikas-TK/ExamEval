import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  Brain, CheckCircle2, AlertTriangle, XCircle, RefreshCw,
  ChevronDown, ChevronUp, Layers, BookOpen, FileText,
  Zap, Eye, EyeOff, BarChart2, Hash, Award, Clock
} from 'lucide-react';

const API = '/api';

const STATUS_BADGE = {
  MAPPED: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: CheckCircle2 },
  SKIPPED: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: AlertTriangle },
  UNMAPPED: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: XCircle },
};

const VALIDATION_BADGE = {
  VALID: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: 'VALID' },
  WARNING: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: 'WARNING' },
  INVALID: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', label: 'INVALID' },
};

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div style={{
      background: '#ffffff', border: '1px solid #e2e8f0',
      borderRadius: 14, padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 14,
      boxShadow: '0 2px 4px rgba(0,0,0,0.04)',
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 10, background: `${color}18`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 24, fontWeight: 800, color: '#0f172a' }}>{value ?? '—'}</div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#64748b', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

function QACard({ record, index }) {
  const [expanded, setExpanded] = useState(false);
  const st = STATUS_BADGE[record.mapping_status] || STATUS_BADGE.MAPPED;
  const vt = VALIDATION_BADGE[record.validation_status] || VALIDATION_BADGE.VALID;
  const StatusIcon = st.icon;

  return (
    <div style={{
      background: '#ffffff', border: '1px solid #e2e8f0',
      borderRadius: 14, overflow: 'hidden', transition: 'border-color 0.2s',
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
    }}>
      {/* Header row */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 14,
          cursor: 'pointer', userSelect: 'none', background: expanded ? '#f8fafc' : '#ffffff',
        }}
      >
        {/* Sequence badge */}
        <div style={{
          width: 34, height: 34, borderRadius: 8, background: '#e0e7ff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, color: '#4338ca', flexShrink: 0,
        }}>{index + 1}</div>

        {/* Question number + text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 800, color: '#0f172a', fontSize: 15 }}>
              Q{record.question_number}
            </span>
            {record.section_name && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 9px', borderRadius: 20,
                background: '#f3e8ff', color: '#7e22ce',
              }}>{record.section_name}</span>
            )}
            {record.maximum_marks != null && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 9px', borderRadius: 20,
                background: '#d1fae5', color: '#047857',
              }}>{record.maximum_marks} marks</span>
            )}
          </div>
          <div style={{
            fontSize: 13, color: '#475569', marginTop: 4, fontWeight: 500,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {record.question_text || 'No question text available'}
          </div>
        </div>

        {/* Status badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '4px 11px', borderRadius: 20,
            background: st.bg, color: st.color, display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <StatusIcon size={12} /> {record.mapping_status}
          </span>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '4px 11px', borderRadius: 20,
            background: vt.bg, color: vt.color,
          }}>{vt.label}</span>
          {expanded ? <ChevronUp size={16} color="#64748b" /> : <ChevronDown size={16} color="#64748b" />}
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div style={{
          borderTop: '1px solid #e2e8f0', background: '#f8fafc',
          padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          {/* Question text */}
          {record.question_text && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Question Description
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0f172a', lineHeight: 1.6 }}>
                {record.question_text}
              </div>
            </div>
          )}

          {/* Student answer */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Student Handwritten Answer (Extracted via OCR)
            </div>
            {record.student_answer ? (
              <div style={{
                background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 10,
                padding: '14px 16px', fontSize: 13, color: '#0f172a', lineHeight: 1.7,
                whiteSpace: 'pre-wrap', fontFamily: 'inherit', maxHeight: 300, overflowY: 'auto',
                boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.03)',
              }}>{record.student_answer}</div>
            ) : (
              <div style={{ fontSize: 13, color: '#64748b', fontStyle: 'italic', background: '#ffffff', padding: '12px 14px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                No answer detected — question was {record.mapping_status === 'SKIPPED' ? 'skipped' : 'unmapped'}.
              </div>
            )}
          </div>

          {/* Metadata row */}
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, color: '#475569', fontWeight: 500 }}>
            <span>Answer length: <strong style={{ color: '#0f172a' }}>{record.answer_length ?? 0} chars</strong></span>
            {record.anchor_text && (
              <span>Anchor: <strong style={{ color: '#0f172a' }}>"{record.anchor_text}"</strong></span>
            )}
            {record.anchor_confidence != null && (
              <span>Confidence: <strong style={{ color: '#0f172a' }}>{(record.anchor_confidence * 100).toFixed(0)}%</strong></span>
            )}
            <span>Type: <strong style={{ color: '#0f172a' }}>{record.question_type || '—'}</strong></span>
          </div>

          {/* Visual elements */}
          {record.visual_elements && record.visual_elements.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Visual Elements / Diagrams ({record.visual_elements.length})
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {record.visual_elements.map((ve, i) => (
                  <span key={i} style={{
                    fontSize: 11, fontWeight: 600, padding: '4px 11px', borderRadius: 20,
                    background: '#f3e8ff', color: '#7e22ce', border: '1px solid #e9d5ff',
                  }}>{ve.type || ve.element_type || 'element'}</span>
                ))}
              </div>
            </div>
          )}

          {/* Validation warnings */}
          {record.validation_warnings && record.validation_warnings.length > 0 && (
            <div style={{
              background: '#fffbeb', border: '1px solid #fde68a',
              borderRadius: 8, padding: '10px 14px',
            }}>
              {record.validation_warnings.map((w, i) => (
                <div key={i} style={{ fontSize: 12, fontWeight: 600, color: '#b45309', display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                  <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1 }} /> {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function QAMappingPage({ apiKey }) {
  const [evaluations, setEvaluations] = useState([]);
  const [blueprints, setBlueprints] = useState([]);
  const [evalId, setEvalId] = useState('');
  const [blueprintId, setBlueprintId] = useState('');
  const [processing, setProcessing] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [records, setRecords] = useState([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [showRawReport, setShowRawReport] = useState(false);

  const headers = apiKey ? { 'x-api-key': apiKey } : {};

  // Load evaluations and blueprints for the dropdowns
  const loadData = useCallback(() => {
    axios.get('/api/evaluations', { headers, params: { page_size: 100 } })
      .then(r => setEvaluations(r.data.items || r.data || []))
      .catch(() => {});
    axios.get('/api/blueprints', { headers, params: { page_size: 100 } })
      .then(r => setBlueprints(r.data.items || r.data || []))
      .catch(() => {});
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Fetch existing mapping records for the selected evaluation
  const fetchRecords = useCallback((eid) => {
    if (!eid) return;
    setLoadingRecords(true);
    axios.get(`${API}/mapping/${eid}`, { headers })
      .then(r => setRecords(r.data || []))
      .catch(() => setRecords([]))
      .finally(() => setLoadingRecords(false));
  }, []);

  const handleProcess = async () => {
    if (!evalId || !blueprintId) {
      toast.error('Select both an evaluation and a blueprint.');
      return;
    }
    setProcessing(true);
    setLastResult(null);
    setRecords([]);
    try {
      const { data } = await axios.post(`${API}/mapping/process`, {
        evaluation_id: evalId,
        blueprint_id: blueprintId,
      }, { headers });
      setLastResult(data);
      toast.success(`Phase 3 complete — ${data.mapped_questions} questions mapped.`);
      fetchRecords(evalId);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      toast.error(`Mapping failed: ${msg}`);
    } finally {
      setProcessing(false);
    }
  };

  const filteredRecords = filterStatus === 'ALL'
    ? records
    : records.filter(r => r.mapping_status === filterStatus);

  const vStatus = lastResult?.validation_status || (records.length > 0 ? records[0]?.validation_status : null);

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(79,70,229,0.25)',
          }}>
            <Brain size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
              Phase 3 — Q&amp;A Mapping Engine
            </h1>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: '#475569', fontWeight: 500 }}>
              Map student OCR answers to blueprint questions for AI evaluation
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
          <Zap size={18} color="#4f46e5" /> Run Mapping Pipeline
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 22 }}>
          {/* Evaluation selector */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#4338ca', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Student Evaluation Script
            </label>
            <select
              value={evalId}
              onChange={e => { setEvalId(e.target.value); setRecords([]); setLastResult(null); fetchRecords(e.target.value); }}
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
            {evalId && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#4f46e5', fontWeight: 600, fontFamily: 'monospace' }}>
                Full UUID: {evalId}
              </div>
            )}
          </div>

          {/* Blueprint selector */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#4338ca', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
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
            {blueprintId && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#4f46e5', fontWeight: 600, fontFamily: 'monospace' }}>
                Full UUID: {blueprintId}
              </div>
            )}
          </div>
        </div>

        <button
          onClick={handleProcess}
          disabled={processing || !evalId || !blueprintId}
          style={{
            padding: '12px 28px', borderRadius: 10, border: 'none', cursor: processing ? 'wait' : 'pointer',
            background: processing ? '#94a3b8' : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            color: '#fff', fontWeight: 700, fontSize: 14,
            display: 'flex', alignItems: 'center', gap: 8,
            opacity: (!evalId || !blueprintId) ? 0.5 : 1,
            boxShadow: '0 4px 12px rgba(79,70,229,0.25)',
            transition: 'all 0.2s',
          }}
        >
          {processing
            ? <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> Processing…</>
            : <><Brain size={16} /> Run Phase 3 Mapping</>}
        </button>
      </div>

      {/* Result summary */}
      {lastResult && (
        <div style={{
          background: '#ffffff', border: '1px solid #e2e8f0',
          borderRadius: 16, padding: 24, marginBottom: 28,
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
              <BarChart2 size={18} color="#059669" /> Pipeline Result
            </h2>
            <button
              onClick={() => setShowRawReport(s => !s)}
              style={{
                background: '#f1f5f9', border: '1px solid #cbd5e1',
                color: '#334155', borderRadius: 8, padding: '7px 14px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {showRawReport ? <EyeOff size={14} /> : <Eye size={14} />}
              {showRawReport ? 'Hide' : 'Raw Report'}
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 20 }}>
            <StatCard icon={BookOpen} label="Questions Processed" value={lastResult.questions_processed} color="#4f46e5" />
            <StatCard icon={CheckCircle2} label="Mapped" value={lastResult.mapped_questions} color="#059669" />
            <StatCard icon={AlertTriangle} label="Skipped" value={lastResult.skipped_questions} color="#d97706" />
            <StatCard icon={XCircle} label="Unmapped" value={lastResult.unmapped_questions} color="#dc2626" />
          </div>

          <div style={{
            padding: '12px 16px', borderRadius: 10,
            background: (lastResult.validation_status === 'VALID') ? '#ecfdf5' :
              (lastResult.validation_status === 'WARNING') ? '#fffbeb' : '#fef2f2',
            border: `1px solid ${lastResult.validation_status === 'VALID' ? '#a7f3d0' :
              lastResult.validation_status === 'WARNING' ? '#fde68a' : '#fecaca'}`,
            fontSize: 13, fontWeight: 700,
            color: lastResult.validation_status === 'VALID' ? '#047857' :
              lastResult.validation_status === 'WARNING' ? '#b45309' : '#b91c1c',
          }}>
            Validation: {lastResult.validation_status} — {lastResult.output}
          </div>

          {showRawReport && lastResult.validation_report && (
            <div style={{ marginTop: 16 }}>
              {lastResult.validation_report.errors?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#dc2626', textTransform: 'uppercase', marginBottom: 4 }}>Errors</div>
                  {lastResult.validation_report.errors.map((e, i) => (
                    <div key={i} style={{ fontSize: 12, fontWeight: 500, color: '#991b1b', padding: '2px 0' }}>• {e}</div>
                  ))}
                </div>
              )}
              {lastResult.validation_report.warnings?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#d97706', textTransform: 'uppercase', marginBottom: 4 }}>Warnings</div>
                  {lastResult.validation_report.warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: 12, fontWeight: 500, color: '#92400e', padding: '2px 0' }}>• {w}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Q&A Records */}
      {(records.length > 0 || loadingRecords) && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers size={18} color="#4f46e5" /> Question–Answer Records
              <span style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>({filteredRecords.length})</span>
            </h2>
            <div style={{ display: 'flex', gap: 8 }}>
              {['ALL', 'MAPPED', 'SKIPPED', 'UNMAPPED'].map(s => (
                <button
                  key={s}
                  onClick={() => setFilterStatus(s)}
                  style={{
                    padding: '6px 14px', borderRadius: 20, border: '1px solid',
                    borderColor: filterStatus === s ? '#4f46e5' : '#cbd5e1',
                    background: filterStatus === s ? '#e0e7ff' : '#ffffff',
                    color: filterStatus === s ? '#4338ca' : '#475569',
                    fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  }}
                >{s}</button>
              ))}
            </div>
          </div>

          {loadingRecords ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
              <RefreshCw size={20} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
              <div>Loading Q&A records…</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {filteredRecords.map((rec, i) => (
                <QACard key={rec.mapping_id} record={rec} index={i} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state — eval selected but no records */}
      {evalId && !loadingRecords && records.length === 0 && !lastResult && (
        <div style={{
          textAlign: 'center', padding: '48px 24px',
          background: '#ffffff', borderRadius: 16,
          border: '1px dashed #cbd5e1', boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}>
          <Brain size={40} color="#4f46e5" style={{ marginBottom: 12 }} />
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>No Q&A mapping found for this evaluation</div>
          <div style={{ fontSize: 13, color: '#64748b' }}>Select a blueprint and click "Run Phase 3 Mapping" to generate one.</div>
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        select option { background: #ffffff; color: #0f172a; }
      `}</style>
    </div>
  );
}
