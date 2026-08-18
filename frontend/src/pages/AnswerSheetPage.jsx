import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { ArrowRight, FileText, LockKeyhole, ShieldCheck, UploadCloud, X } from 'lucide-react';
import { Card, PageHeader, ProgressBar, StatusBadge } from '../components/ui';

export default function AnswerSheetPage({ apiKey }) {
  const [form, setForm] = useState({ regulation: '', semester: '', subject_id: '' });
  const [masters, setMasters] = useState([]);

  // Each entry: { id (local key), file, registerNumber }
  const [pending, setPending] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const nextLocalId = useRef(0);
  const fileInputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  // Each entry: { localId, filename, evaluation_id, status: 'submitting'|'processing'|'error', data? }
  const [queue, setQueue] = useState([]);
  const [selectedEvalId, setSelectedEvalId] = useState(null);

  const headers = () => (apiKey ? { 'x-api-key': apiKey } : {});

  useEffect(() => {
    axios
      .get('/api/academic-master', { params: { status: 'ACTIVE', page_size: 100 }, headers: headers() })
      .then((response) => {
        const records = response.data.items || [];
        setMasters(records);
        if (records[0]) {
          setForm((current) => ({
            ...current,
            regulation: records[0].regulation,
            semester: records[0].semester,
            subject_id: records[0].subject_code,
          }));
        }
      })
      .catch(() => toast.error('Academic master data could not be loaded.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  const addFiles = (fileList) => {
    const chosen = Array.from(fileList || []);
    if (chosen.length === 0) return;
    setPending((prev) => [
      ...prev,
      ...chosen.map((file) => ({ id: nextLocalId.current++, file, registerNumber: '' })),
    ]);
  };

  const removePending = (id) => setPending((prev) => prev.filter((p) => p.id !== id));
  const updateRegisterNumber = (id, value) =>
    setPending((prev) => prev.map((p) => (p.id === id ? { ...p, registerNumber: value } : p)));

  const submitOne = async (entry) => {
    const data = new FormData();
    data.append('regulation', form.regulation);
    data.append('semester', form.semester);
    data.append('subject_id', form.subject_id);
    data.append('register_number', entry.registerNumber);
    data.append('file', entry.file);
    const response = await axios.post('/api/evaluations', data, { headers: headers() });
    return response.data.evaluation_id;
  };

  const submit = async (event) => {
    event.preventDefault();
    if (pending.length === 0) {
      toast.error('Please select at least one answer sheet to upload.');
      return;
    }
    const missing = pending.filter((p) => !p.registerNumber.trim());
    if (missing.length > 0) {
      toast.error(`Enter a register number for every file (${missing.length} missing).`);
      return;
    }

    setSubmitting(true);
    const batch = [...pending];
    setPending([]);

    // Submitted one at a time on purpose: OCR/scoring all share a single
    // GPU/Ollama instance, so firing many uploads at once wouldn't process
    // them any faster — it would just queue heavy work behind a burst of
    // requests. Sequential submission keeps each request light (just the
    // upload) and lets the backend's own background task pace the rest.
    for (const entry of batch) {
      setQueue((prev) => [
        ...prev,
        { localId: entry.id, filename: entry.file.name, evaluation_id: null, status: 'submitting' },
      ]);
      try {
        const evaluationId = await submitOne(entry);
        setQueue((prev) =>
          prev.map((q) =>
            q.localId === entry.id ? { ...q, evaluation_id: evaluationId, status: 'processing' } : q
          )
        );
      } catch (error) {
        const message = error.response?.data?.detail || 'Answer sheet upload failed.';
        setQueue((prev) =>
          prev.map((q) => (q.localId === entry.id ? { ...q, status: 'error' } : q))
        );
        toast.error(`${entry.file.name}: ${message}`);
      }
    }
    setSubmitting(false);
    toast.success(`${batch.length} file${batch.length > 1 ? 's' : ''} queued for processing.`);
  };

  // Poll every evaluation currently in-flight, all in one shared interval
  // rather than one interval per file.
  useEffect(() => {
    const inFlight = queue.filter((q) => q.status === 'processing' && q.evaluation_id);
    if (inFlight.length === 0) return undefined;
    const timer = setInterval(async () => {
      await Promise.all(
        inFlight.map(async (q) => {
          try {
            const response = await axios.get(`/api/evaluations/${q.evaluation_id}`, { headers: headers() });
            setQueue((prev) =>
              prev.map((item) => (item.localId === q.localId ? { ...item, data: response.data } : item))
            );
            if (['COMPLETED', 'NEEDS_REVIEW', 'FAILED'].includes(response.data.status)) {
              toast.success(`${q.filename}: OCR processing ${response.data.status.toLowerCase().replace('_', ' ')}.`);
            }
          } catch {
            /* Keep polling while the API is processing. */
          }
        })
      );
    }, 2500);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue, apiKey]);

  const selected = queue.find((q) => q.evaluation_id === selectedEvalId);
  const result = selected?.data;

  const queueStatus = (q) => {
    if (q.data?.status) return q.data.status;
    if (q.status === 'error') return 'FAILED';
    if (q.status === 'submitting') return 'Uploading';
    return 'PROCESSING';
  };

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Answer sheets / Ingestion"
        title="Upload answer sheets"
        description="Securely submit handwritten scripts for anonymized OCR processing and quality validation. Select multiple files to batch-submit — each still gets its own register number."
      />
      <div className="form-layout answer-layout">
        <Card
          title="New answer sheets"
          description="Files are encrypted and student identifiers are anonymized before processing."
        >
          <form onSubmit={submit}>
            <div
              className={`file-uploader ${dragging ? 'dragging' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => event.key === 'Enter' && fileInputRef.current?.click()}
              aria-label="Upload files"
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(event) => { addFiles(event.target.files); event.target.value = ''; }}
                hidden
              />
              <span className="upload-icon"><UploadCloud size={21} /></span>
              {pending.length > 0 ? (
                <>
                  <strong>{pending.length} file{pending.length > 1 ? 's' : ''} selected</strong>
                  <span>Click to add more</span>
                </>
              ) : (
                <>
                  <strong>Drop answer sheets here, or browse</strong>
                  <span>PDF, PNG, or JPG up to 25MB each</span>
                </>
              )}
            </div>

            {pending.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12, maxHeight: 220, overflowY: 'auto' }}>
                {pending.map((entry) => (
                  <div
                    key={entry.id}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, border: '1px solid var(--border)', borderRadius: 7, padding: 8 }}
                  >
                    <FileText size={14} style={{ color: 'var(--muted)', flexShrink: 0 }} />
                    <span
                      style={{ flex: 1, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={entry.file.name}
                    >
                      {entry.file.name}
                    </span>
                    <input
                      className="mono"
                      placeholder="Register number"
                      value={entry.registerNumber}
                      onChange={(e) => updateRegisterNumber(entry.id, e.target.value)}
                      style={{ width: 150, border: '1px solid #d1d5db', borderRadius: 6, padding: '6px 8px', fontSize: 11 }}
                    />
                    <button
                      type="button"
                      onClick={() => removePending(entry.id)}
                      aria-label={`Remove ${entry.file.name}`}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', flexShrink: 0 }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="form-grid compact-grid">
              <label className="field">
                <span>Subject</span>
                <select
                  value={form.subject_id}
                  onChange={(e) => {
                    const selectedMaster = masters.find((item) => item.subject_code === e.target.value);
                    setForm({
                      ...form,
                      subject_id: e.target.value,
                      regulation: selectedMaster?.regulation || form.regulation,
                      semester: selectedMaster?.semester || form.semester,
                    });
                  }}
                  required
                >
                  <option value="">Select a subject</option>
                  {masters.map((item) => (
                    <option key={item.id} value={item.subject_code}>
                      {item.subject_code} · {item.subject_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field"><span>Regulation</span><input value={form.regulation} readOnly /></label>
              <label className="field"><span>Semester</span><input value={form.semester} readOnly /></label>
            </div>

            <div className="security-note">
              <LockKeyhole size={17} />
              <span>
                <strong>Anonymous by design</strong>
                <small>Raw student identity is never exposed to evaluators. Each file above gets its own register number, isolated to a single identity record.</small>
              </span>
            </div>

            <button className="primary-button full-button" disabled={submitting || pending.length === 0}>
              {submitting ? 'Anonymizing & processing…' : (
                <>{pending.length > 1 ? `Submit ${pending.length} for OCR` : 'Submit for OCR'} <ArrowRight size={17} /></>
              )}
            </button>
          </form>

          {queue.length > 0 && (
            <div style={{ marginTop: 20, borderTop: '1px solid #f3f4f6', paddingTop: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#374151', marginBottom: 8 }}>Submission queue</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflowY: 'auto' }}>
                {queue.map((q) => (
                  <button
                    type="button"
                    key={q.localId}
                    onClick={() => q.evaluation_id && setSelectedEvalId(q.evaluation_id)}
                    disabled={!q.evaluation_id}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                      border: `1px solid ${selectedEvalId === q.evaluation_id ? 'var(--green)' : 'var(--border)'}`,
                      background: selectedEvalId === q.evaluation_id ? '#ecfdf5' : '#fff',
                      borderRadius: 7, padding: '8px 10px', fontSize: 11,
                      cursor: q.evaluation_id ? 'pointer' : 'default', textAlign: 'left',
                    }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.filename}</span>
                    <StatusBadge status={queueStatus(q)} />
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card title="Processing status" description="Select a file in the submission queue to view its results.">
          {result ? (
            <div className="result-panel">
              <div className="result-heading">
                <span className="result-icon"><FileText size={18} /></span>
                <div>
                  <strong>{result.register_number || selected?.filename || 'Unknown'}</strong>
                  <small>{result.subject_id}</small>
                </div>
                <StatusBadge status={result.status || 'PROCESSING'} />
              </div>
              <ProgressBar
                value={['COMPLETED', 'NEEDS_REVIEW', 'FAILED'].includes(result.status) ? 100 : 42}
                label="Pipeline progress"
              />
              <div className="result-stats">
                <div>
                  <span>OCR confidence</span>
                  <strong>
                    {result.overall_confidence !== null && result.overall_confidence !== undefined
                      ? `${(result.overall_confidence * 100).toFixed(1)}%`
                      : 'Calculating…'}
                  </strong>
                </div>
                <div>
                  <span>Quality gate</span>
                  <strong>
                    {result.quality_report
                      ? (result.quality_report.passed ? 'Passed' : 'Failed')
                      : (['COMPLETED', 'NEEDS_REVIEW', 'FAILED'].includes(result.status) ? 'Evaluated' : 'Pending')}
                  </strong>
                </div>
              </div>
              {result.error_message && (
                <div style={{ marginTop: '12px', fontSize: '12px', color: '#b45309', background: '#fef3c7', padding: '8px 12px', borderRadius: '6px' }}>
                  <strong>Note:</strong> {result.error_message}
                </div>
              )}
            </div>
          ) : (
            <div className="status-empty">
              <span className="empty-icon"><ShieldCheck size={23} /></span>
              <h3>Ready to process</h3>
              <p>
                {queue.length > 0
                  ? 'Click a file in the submission queue to see OCR confidence, quality checks, and transcript results.'
                  : 'Upload one or more answer sheets to see OCR confidence, quality checks, and transcript results.'}
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
