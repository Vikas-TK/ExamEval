import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BookOpen, CheckCircle2, Download, Layers, Sparkles } from 'lucide-react';
import { Card, FileUploader, PageHeader } from '../components/ui';

export default function QuestionPaperPage({ apiKey }) {
  const [paper, setPaper] = useState(null);
  const [answerKey, setAnswerKey] = useState(null);
  const [masters, setMasters] = useState([]);
  const [metadata, setMetadata] = useState({
    exam_name: 'End Semester Examination',
    subject: '',
    subject_code: '',
    regulation: '',
    semester: '',
    department: '',
    duration_minutes: 180,
    maximum_marks: 100,
  });
  const [loading, setLoading] = useState(false);
  const [blueprintData, setBlueprintData] = useState(null);

  useEffect(() => {
    axios
      .get('/api/academic-master', {
        params: { status: 'ACTIVE', page_size: 100 },
        headers: apiKey ? { 'x-api-key': apiKey } : {},
      })
      .then((response) => {
        const records = response.data.items || [];
        setMasters(records);
        if (records[0]) {
          setMetadata((current) => ({
            ...current,
            subject: records[0].subject_name,
            subject_code: records[0].subject_code,
            regulation: records[0].regulation,
            semester: records[0].semester,
            department: records[0].department,
          }));
        }
      })
      .catch(() => toast.error('Academic master data could not be loaded.'));
  }, [apiKey]);

  const update = (key, value) => setMetadata({ ...metadata, [key]: value });

  const submit = async (event) => {
    event.preventDefault();
    if (!paper) return toast.error('Please upload a question paper first.');
    setLoading(true);
    const data = new FormData();
    data.append('question_paper', paper);
    data.append('metadata', JSON.stringify(metadata));
    if (answerKey) data.append('answer_key', answerKey);

    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const res = await axios.post('/api/blueprints', data, { headers });
      toast.success('Question paper processed and blueprint generated!');
      if (res.data?.blueprint_id) {
        const detailRes = await axios.get(`/api/blueprints/${res.data.blueprint_id}`, { headers });
        setBlueprintData(detailRes.data);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Question paper upload failed.');
    } finally {
      setLoading(false);
    }
  };

  const getQuestionBadge = (type) => {
    const t = String(type || '').toUpperCase();
    if (t.includes('MCQ')) return <span className="badge badge-mcq">MCQ</span>;
    if (t.includes('SHORT')) return <span className="badge badge-short">Short Answer</span>;
    if (t.includes('DESCRIPTIVE')) return <span className="badge badge-descriptive">Descriptive</span>;
    if (t.includes('DIAGRAM')) return <span className="badge badge-diagram">Diagram</span>;
    return <span className="badge badge-other">{type}</span>;
  };

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Blueprints / Question Papers"
        title="Upload & View Question Paper"
        description="Upload a question paper and optional answer key to generate and view the structured exam blueprint."
      />

      <div className="form-layout" style={{ display: 'grid', gridTemplateColumns: blueprintData ? '1fr 1.2fr' : '1fr', gap: '1.5rem' }}>
        {/* Upload Form */}
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <Card title="Question paper" description="Upload the source document (PDF, Image, JSON, TXT) for OCR extraction.">
            <FileUploader
              file={paper}
              onFile={setPaper}
              accept=".pdf,.png,.jpg,.jpeg,.txt,.json"
              label="Drop question paper here, or browse"
              hint="PDF, image, TXT, or JSON up to 25MB"
            />
            <div className="file-note">
              <BookOpen size={16} />
              <span>We’ll extract sections, questions, marks, and question types automatically.</span>
            </div>
          </Card>

          <Card title="Exam metadata" description="Select a subject from the centralized Academic Master.">
            <div className="form-grid">
              <label className="field full-field">
                <span>Subject</span>
                <select
                  value={metadata.subject_code}
                  onChange={(e) => {
                    const selected = masters.find((item) => item.subject_code === e.target.value);
                    if (selected) {
                      setMetadata({
                        ...metadata,
                        subject: selected.subject_name,
                        subject_code: selected.subject_code,
                        regulation: selected.regulation,
                        semester: selected.semester,
                        department: selected.department,
                      });
                    }
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
              {[
                ['exam_name', 'Exam name'],
                ['subject_code', 'Subject code'],
                ['regulation', 'Regulation'],
                ['semester', 'Semester'],
                ['department', 'Department'],
                ['duration_minutes', 'Duration (minutes)'],
                ['maximum_marks', 'Maximum marks'],
              ].map(([key, label]) => (
                <label className="field" key={key}>
                  <span>{label}</span>
                  <input
                    value={metadata[key]}
                    readOnly={['subject_code', 'regulation', 'semester', 'department'].includes(key)}
                    onChange={(e) => update(key, e.target.value)}
                    required
                  />
                </label>
              ))}
            </div>
          </Card>

          <Card title="Faculty answer key" description="Optional mapping used to support answer evaluation.">
            <FileUploader
              file={answerKey}
              onFile={setAnswerKey}
              accept=".pdf,.docx,.txt"
              label="Drop answer key here, or browse"
              hint="PDF, DOCX, or TXT · Optional"
            />
            <div className="form-submit">
              <span>
                <Sparkles size={16} /> AI extraction is ready to run
              </span>
              <button className="primary-button" disabled={loading}>
                {loading ? 'Generating…' : <><CheckCircle2 size={17} /> Generate blueprint</>}
              </button>
            </div>
          </Card>
        </form>

        {/* Phase 2 Output Display Dashboard */}
        {blueprintData && (
          <Card title="Extracted Exam Blueprint Output" description={`Blueprint ID: ${blueprintData.blueprint_id}`}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.75rem', background: '#f9fafb', padding: '1rem', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                <div>
                  <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Exam Name</small>
                  <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{blueprintData.metadata.exam_name}</p>
                </div>
                <div>
                  <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Subject (Code)</small>
                  <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{blueprintData.metadata.subject} ({blueprintData.metadata.subject_code})</p>
                </div>
                <div>
                  <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Max Marks / Duration</small>
                  <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{blueprintData.metadata.maximum_marks} Marks / {blueprintData.metadata.duration_minutes} min</p>
                </div>
              </div>

              {/* Sections and Questions */}
              {blueprintData.sections?.map((section, idx) => (
                <div key={section.section_id || idx} style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '1rem', background: '#ffffff' }}>
                  <div style={{ fontWeight: 600, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', borderBottom: '1px solid #f3f4f6', paddingBottom: '0.5rem' }}>
                    <Layers size={18} color="#10b981" />
                    <span>{section.name}</span>
                    {section.instructions && <small style={{ color: '#6b7280', fontWeight: 400, marginLeft: 'auto' }}>{section.instructions}</small>}
                  </div>

                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ background: '#f9fafb', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                        <th style={{ padding: '0.5rem' }}>Q.No</th>
                        <th style={{ padding: '0.5rem' }}>Question Text</th>
                        <th style={{ padding: '0.5rem' }}>Type</th>
                        <th style={{ padding: '0.5rem' }}>Marks</th>
                        <th style={{ padding: '0.5rem' }}>Answer Key Mapping</th>
                      </tr>
                    </thead>
                    <tbody>
                      {section.questions?.map((q) => (
                        <tr key={q.question_id || q.question_number} style={{ borderBottom: '1px solid #f3f4f6' }}>
                          <td style={{ padding: '0.5rem', fontWeight: 600 }}>{String(q.question_number || '').toUpperCase().startsWith('Q') ? q.question_number : 'Q' + q.question_number}</td>
                          <td style={{ padding: '0.5rem' }}>{q.question_text}</td>
                          <td style={{ padding: '0.5rem' }}>{getQuestionBadge(q.question_type)}</td>
                          <td style={{ padding: '0.5rem', fontWeight: 600 }}>{q.maximum_marks}</td>
                          <td style={{ padding: '0.5rem', color: q.faculty_answer ? '#0d0d0d' : '#9ca3af', fontStyle: q.faculty_answer ? 'normal' : 'italic' }}>
                            {q.faculty_answer || 'Unmapped'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}

              {/* Artifact Downloads */}
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                {blueprintData.blueprint_url && (
                  <a href={blueprintData.blueprint_url} target="_blank" rel="noreferrer" className="secondary-button" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', textDecoration: 'none' }}>
                    <Download size={14} /> Download Blueprint JSON
                  </a>
                )}
                {blueprintData.faculty_answer_key_s3_url && (
                  <a href={blueprintData.faculty_answer_key_s3_url} target="_blank" rel="noreferrer" className="secondary-button" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', textDecoration: 'none' }}>
                    <Download size={14} /> Download Answer Key Artifact
                  </a>
                )}
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
