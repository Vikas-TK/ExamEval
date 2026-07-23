import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BookOpen, CheckCircle2, Code, Download, FileText, Layers, Plus, Sparkles, UploadCloud } from 'lucide-react';
import { Card, FileUploader, PageHeader } from '../components/ui';

const SAMPLE_BLUEPRINT_JSON = JSON.stringify(
  {
    exam_name: "End Semester Examination",
    subject: "Cloud Computing & Distributed Systems",
    subject_code: "IT8401",
    regulation: "R2021",
    semester: "SEM-06",
    department: "Computer Science and Engineering",
    duration_minutes: 180,
    maximum_marks: 100.0,
    status: "Approved",
    blueprint_type: "json_upload",
    sections: [
      {
        section_name: "Part A (10 x 2 = 20 Marks)",
        total_marks: 20.0,
        instructions: "Answer all questions.",
        questions: [
          {
            question_number: "Q1",
            marks: 2.0,
            course_outcome: "CO1",
            blooms_taxonomy: "Remember",
            difficulty_level: "Easy",
            question_type: "Short Answer",
            expected_depth: "Brief definition with 2 key points",
            keywords: ["Cloud Computing", "Virtualization"],
            answer_key: "Cloud computing provides on-demand availability of computer system resources without direct active management."
          },
          {
            question_number: "Q2",
            marks: 2.0,
            course_outcome: "CO1",
            blooms_taxonomy: "Understand",
            difficulty_level: "Medium",
            question_type: "Short Answer",
            expected_depth: "Comparison",
            keywords: ["IaaS", "PaaS", "SaaS"],
            answer_key: "IaaS offers infrastructure, PaaS provides platform/frameworks, and SaaS delivers complete software applications."
          }
        ]
      }
    ]
  },
  null,
  2
);

export default function QuestionPaperPage({ apiKey }) {
  const [activeMode, setActiveMode] = useState('ai_ocr'); // 'ai_ocr' | 'json_upload' | 'manual_builder'
  const [paper, setPaper] = useState(null);
  const [answerKey, setAnswerKey] = useState(null);
  const [masters, setMasters] = useState([]);
  const [jsonText, setJsonText] = useState('');
  
  const [metadata, setMetadata] = useState({
    exam_name: 'End Semester Examination',
    subject: 'Cloud Computing & Distributed Systems',
    subject_code: 'IT8401',
    regulation: 'R2021',
    semester: 'SEM-06',
    department: 'Computer Science',
    duration_minutes: 180,
    maximum_marks: 100,
  });

  // Manual Builder State
  const [manualSections, setManualSections] = useState([
    {
      section_name: 'Part A',
      total_marks: 20,
      instructions: 'Answer all questions.',
      questions: [
        {
          question_number: 'Q1',
          marks: 2,
          course_outcome: 'CO1',
          blooms_taxonomy: 'Remember',
          difficulty_level: 'Easy',
          question_type: 'Short Answer',
          expected_depth: 'Brief definition',
          keywords: 'Cloud, Elasticity',
          answer_key: 'Cloud computing delivers on-demand computing services over the internet.'
        }
      ]
    }
  ]);

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
      .catch(() => {});
  }, [apiKey]);

  const updateMetadata = (key, value) => setMetadata({ ...metadata, [key]: value });

  // --- Mode 1: AI OCR Submit ---
  const handleAiOcrSubmit = async (event) => {
    event.preventDefault();
    if (!paper) return toast.error('Please select or drop a question paper file.');
    setLoading(true);
    const data = new FormData();
    data.append('question_paper', paper);
    data.append('metadata', JSON.stringify(metadata));
    if (answerKey) data.append('answer_key', answerKey);

    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const res = await axios.post('/api/blueprints', data, { headers });
      toast.success('Question paper processed with AI GOT-OCR!');
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

  // --- Mode 2: JSON Upload / Paste Submit ---
  const handleJsonSubmit = async (event) => {
    event.preventDefault();
    if (!jsonText.trim()) return toast.error('Please paste or upload blueprint JSON content.');
    setLoading(true);
    try {
      const parsed = JSON.parse(jsonText);
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const res = await axios.post('/api/manual-review/blueprint/upload-json', parsed, { headers });
      toast.success('Blueprint JSON validated and saved successfully!');
      if (res.data?.blueprint_id) {
        const detailRes = await axios.get(`/api/blueprints/${res.data.blueprint_id}`, { headers });
        setBlueprintData(detailRes.data);
      }
    } catch (error) {
      console.error(error);
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail.errors) {
        toast.error(`JSON Validation Failed: ${detail.errors.join('; ')}`);
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Invalid Blueprint JSON format.');
      }
    } finally {
      setLoading(false);
    }
  };

  // --- Mode 3: Manual Builder Submit ---
  const handleManualBuilderSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      const payload = {
        ...metadata,
        status: 'Approved',
        blueprint_type: 'manual_builder',
        sections: manualSections.map((sec) => ({
          ...sec,
          questions: sec.questions.map((q) => ({
            ...q,
            keywords: typeof q.keywords === 'string' ? q.keywords.split(',').map((k) => k.trim()) : q.keywords,
          }))
        }))
      };
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const res = await axios.post('/api/manual-review/blueprint/manual-create', payload, { headers });
      toast.success('Manual Blueprint created successfully!');
      if (res.data?.blueprint_id) {
        const detailRes = await axios.get(`/api/blueprints/${res.data.blueprint_id}`, { headers });
        setBlueprintData(detailRes.data);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save manual blueprint.');
    } finally {
      setLoading(false);
    }
  };

  const addManualSection = () => {
    setManualSections([
      ...manualSections,
      {
        section_name: `Part ${String.fromCharCode(65 + manualSections.length)}`,
        total_marks: 50,
        instructions: 'Answer required questions.',
        questions: [
          {
            question_number: `Q${manualSections.length * 10 + 1}`,
            marks: 10,
            course_outcome: 'CO2',
            blooms_taxonomy: 'Apply',
            difficulty_level: 'Medium',
            question_type: 'Theory',
            expected_depth: 'Detailed explanation',
            keywords: 'Architecture, Design',
            answer_key: 'Detailed model answer.'
          }
        ]
      }
    ]);
  };

  const addManualQuestion = (secIdx) => {
    const updated = [...manualSections];
    const qCount = updated[secIdx].questions.length + 1;
    updated[secIdx].questions.push({
      question_number: `Q${qCount}`,
      marks: 2,
      course_outcome: 'CO1',
      blooms_taxonomy: 'Remember',
      difficulty_level: 'Easy',
      question_type: 'Short Answer',
      expected_depth: 'Brief definition',
      keywords: '',
      answer_key: ''
    });
    setManualSections(updated);
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
        title="Question Paper & Blueprint Management"
        description="Select your preferred mode: AI-driven OCR extraction, Direct Blueprint JSON Upload, or Visual Manual Builder."
      />

      {/* Mode Selection Tabs */}
      <div style={{ display: 'flex', gap: '1rem', borderBottom: '2px solid #e2e8f0', paddingBottom: '0.75rem', marginBottom: '1.5rem' }}>
        <button
          type="button"
          className={`primary-button ${activeMode === 'ai_ocr' ? '' : 'secondary-button'}`}
          onClick={() => setActiveMode('ai_ocr')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Sparkles size={16} /> Mode 1: AI OCR Extraction
        </button>
        <button
          type="button"
          className={`primary-button ${activeMode === 'json_upload' ? '' : 'secondary-button'}`}
          onClick={() => setActiveMode('json_upload')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Code size={16} /> Mode 2: Upload / Paste Blueprint JSON
        </button>
        <button
          type="button"
          className={`primary-button ${activeMode === 'manual_builder' ? '' : 'secondary-button'}`}
          onClick={() => setActiveMode('manual_builder')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Layers size={16} /> Mode 3: Visual Blueprint Builder
        </button>
      </div>

      <div className="form-layout" style={{ display: 'grid', gridTemplateColumns: blueprintData ? '1fr 1.2fr' : '1fr', gap: '1.5rem' }}>
        
        {/* MODE 1: AI OCR EXTRACTION */}
        {activeMode === 'ai_ocr' && (
          <form onSubmit={handleAiOcrSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <Card title="Question paper" description="Upload the source document (PDF, Image, JSON, TXT) for GOT-OCR extraction.">
              <FileUploader
                file={paper}
                onFile={setPaper}
                accept=".pdf,.png,.jpg,.jpeg,.txt,.json"
                label="Drop question paper here, or browse"
                hint="PDF, image, TXT, or JSON up to 25MB"
              />
              <div className="file-note" style={{ marginTop: '1rem' }}>
                <BookOpen size={16} />
                <span>We’ll extract sections, questions, marks, and question types automatically.</span>
              </div>
            </Card>

            <Card title="Exam metadata" description="Select a subject from the Academic Master.">
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
                      onChange={(e) => updateMetadata(key, e.target.value)}
                    />
                  </label>
                ))}
              </div>
            </Card>

            <button className="primary-button full-width" type="submit" disabled={loading}>
              {loading ? 'Processing GOT-OCR Blueprint...' : 'Generate Blueprint using AI'}
            </button>
          </form>
        )}

        {/* MODE 2: DIRECT JSON UPLOAD / PASTE */}
        {activeMode === 'json_upload' && (
          <form onSubmit={handleJsonSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <Card title="Upload or Paste Predefined Blueprint JSON" description="Upload a JSON file or paste structured blueprint JSON with automatic schema validation.">
              <div style={{ marginBottom: '1rem' }}>
                <FileUploader
                  file={null}
                  onFile={(file) => {
                    const reader = new FileReader();
                    reader.onload = (e) => setJsonText(e.target.result);
                    reader.readAsText(file);
                  }}
                  accept=".json"
                  label="Drop Blueprint JSON file here, or browse"
                  hint="JSON files up to 10MB"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Or Paste Blueprint JSON:</span>
                <button
                  type="button"
                  className="secondary-button"
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                  onClick={() => setJsonText(SAMPLE_BLUEPRINT_JSON)}
                >
                  Load Sample Blueprint JSON
                </button>
              </div>

              <textarea
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                placeholder="Paste Blueprint JSON content here..."
                rows={14}
                style={{
                  width: '100%',
                  fontFamily: 'Consolas, monospace',
                  fontSize: '0.85rem',
                  padding: '0.75rem',
                  borderRadius: '0.375rem',
                  border: '1px solid #cbd5e1',
                  background: '#0f172a',
                  color: '#f8fafc',
                }}
              />
            </Card>

            <button className="primary-button full-width" type="submit" disabled={loading}>
              {loading ? 'Validating & Saving JSON...' : 'Upload & Validate Blueprint JSON'}
            </button>
          </form>
        )}

        {/* MODE 3: VISUAL MANUAL BLUEPRINT BUILDER */}
        {activeMode === 'manual_builder' && (
          <form onSubmit={handleManualBuilderSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <Card title="Exam General Metadata" description="Define subject & examination specifications.">
              <div className="form-grid">
                <label className="field full-field">
                  <span>Subject Name</span>
                  <input
                    value={metadata.subject}
                    onChange={(e) => updateMetadata('subject', e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>Subject Code</span>
                  <input
                    value={metadata.subject_code}
                    onChange={(e) => updateMetadata('subject_code', e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>Semester</span>
                  <input
                    value={metadata.semester}
                    onChange={(e) => updateMetadata('semester', e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>Maximum Marks</span>
                  <input
                    type="number"
                    value={metadata.maximum_marks}
                    onChange={(e) => updateMetadata('maximum_marks', parseFloat(e.target.value))}
                    required
                  />
                </label>
                <label className="field">
                  <span>Duration (Minutes)</span>
                  <input
                    type="number"
                    value={metadata.duration_minutes}
                    onChange={(e) => updateMetadata('duration_minutes', parseInt(e.target.value, 10))}
                    required
                  />
                </label>
              </div>
            </Card>

            {/* Dynamic Sections */}
            {manualSections.map((sec, secIdx) => (
              <Card key={secIdx} title={`Section ${secIdx + 1}: ${sec.section_name}`} description="Configure section questions, marks, and Taxonomy levels.">
                <div className="form-grid" style={{ marginBottom: '1rem' }}>
                  <label className="field">
                    <span>Section Name</span>
                    <input
                      value={sec.section_name}
                      onChange={(e) => {
                        const updated = [...manualSections];
                        updated[secIdx].section_name = e.target.value;
                        setManualSections(updated);
                      }}
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Total Marks</span>
                    <input
                      type="number"
                      value={sec.total_marks}
                      onChange={(e) => {
                        const updated = [...manualSections];
                        updated[secIdx].total_marks = parseFloat(e.target.value);
                        setManualSections(updated);
                      }}
                      required
                    />
                  </label>
                </div>

                {/* Questions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {sec.questions.map((q, qIdx) => (
                    <div key={qIdx} style={{ border: '1px solid #e2e8f0', borderRadius: '0.5rem', padding: '1rem', background: '#f8fafc' }}>
                      <div className="form-grid">
                        <label className="field">
                          <span>Q. No</span>
                          <input
                            value={q.question_number}
                            onChange={(e) => {
                              const updated = [...manualSections];
                              updated[secIdx].questions[qIdx].question_number = e.target.value;
                              setManualSections(updated);
                            }}
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Marks</span>
                          <input
                            type="number"
                            value={q.marks}
                            onChange={(e) => {
                              const updated = [...manualSections];
                              updated[secIdx].questions[qIdx].marks = parseFloat(e.target.value);
                              setManualSections(updated);
                            }}
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Bloom's Level</span>
                          <select
                            value={q.blooms_taxonomy}
                            onChange={(e) => {
                              const updated = [...manualSections];
                              updated[secIdx].questions[qIdx].blooms_taxonomy = e.target.value;
                              setManualSections(updated);
                            }}
                          >
                            <option value="Remember">Remember</option>
                            <option value="Understand">Understand</option>
                            <option value="Apply">Apply</option>
                            <option value="Analyze">Analyze</option>
                            <option value="Evaluate">Evaluate</option>
                            <option value="Create">Create</option>
                          </select>
                        </label>
                        <label className="field">
                          <span>Question Type</span>
                          <select
                            value={q.question_type}
                            onChange={(e) => {
                              const updated = [...manualSections];
                              updated[secIdx].questions[qIdx].question_type = e.target.value;
                              setManualSections(updated);
                            }}
                          >
                            <option value="Theory">Theory</option>
                            <option value="Numerical">Numerical</option>
                            <option value="Programming">Programming</option>
                            <option value="Diagram">Diagram</option>
                            <option value="MCQ">MCQ</option>
                            <option value="Short Answer">Short Answer</option>
                            <option value="Long Answer">Long Answer</option>
                          </select>
                        </label>
                      </div>
                      <label className="field full-field" style={{ marginTop: '0.5rem' }}>
                        <span>Faculty Model Answer Key</span>
                        <textarea
                          rows={2}
                          value={q.answer_key}
                          onChange={(e) => {
                            const updated = [...manualSections];
                            updated[secIdx].questions[qIdx].answer_key = e.target.value;
                            setManualSections(updated);
                          }}
                          placeholder="Enter model answer expected for evaluation..."
                        />
                      </label>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => addManualQuestion(secIdx)}
                  style={{ marginTop: '1rem', width: '100%' }}
                >
                  <Plus size={15} /> Add Question to {sec.section_name}
                </button>
              </Card>
            ))}

            <div style={{ display: 'flex', gap: '1rem' }}>
              <button type="button" className="secondary-button" onClick={addManualSection} style={{ flex: 1 }}>
                <Plus size={16} /> Add New Section
              </button>
              <button className="primary-button" type="submit" disabled={loading} style={{ flex: 2 }}>
                {loading ? 'Creating Blueprint...' : 'Save Approved Manual Blueprint'}
              </button>
            </div>
          </form>
        )}

        {/* BLUEPRINT DISPLAY PREVIEW */}
        {blueprintData && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <Card title="Generated Blueprint Preview" description="Live view of the approved exam blueprint.">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{blueprintData.metadata?.subject}</h3>
                  <small style={{ color: '#64748b' }}>
                    {blueprintData.metadata?.subject_code} · {blueprintData.metadata?.regulation} · {blueprintData.metadata?.semester}
                  </small>
                </div>
                <span className="badge badge-success" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                  {blueprintData.status || 'Approved'}
                </span>
              </div>

              {(blueprintData.sections || []).map((sec, idx) => (
                <div key={idx} style={{ marginBottom: '1.25rem', border: '1px solid #e2e8f0', borderRadius: '0.5rem', padding: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', color: '#1e293b' }}>{sec.section_name}</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {(sec.questions || []).map((q, qIdx) => (
                      <div key={qIdx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: '#f8fafc', borderRadius: '0.375rem' }}>
                        <div>
                          <strong>{q.question_number}.</strong> {q.question_text || `Question ${q.question_number}`}
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          {getQuestionBadge(q.question_type)}
                          <span style={{ fontWeight: 600, color: '#2563eb' }}>{q.marks} Marks</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </Card>
          </div>
        )}

      </div>
    </div>
  );
}
