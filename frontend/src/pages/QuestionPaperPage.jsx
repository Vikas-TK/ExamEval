import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BookOpen, CheckCircle2, Code, Download, FileText, Layers, Plus, Sparkles, UploadCloud } from 'lucide-react';
import { Card, FileUploader, PageHeader } from '../components/ui';

// Fixed structure for the college's internal-assessment question papers (50 marks total).
const INTERNAL_NORMAL_TEMPLATE = {
  exam_type: 'INTERNAL_NORMAL',
  total_marks: 50,
  parts: [
    { part_name: 'Part A', choice_type: 'ALL_COMPULSORY', total_questions: 12, questions_to_answer: 12, marks_per_question: 0.5, has_subparts: false, has_internal_or_choice: false },
    { part_name: 'Part B', choice_type: 'ALL_COMPULSORY', total_questions: 3, questions_to_answer: 3, marks_per_question: 2.0, has_subparts: false, has_internal_or_choice: false },
    { part_name: 'Part C', choice_type: 'SELECT_ANY_N', total_questions: 3, questions_to_answer: 2, marks_per_question: 14.0, has_subparts: true, has_internal_or_choice: true },
    { part_name: 'Part D', choice_type: 'SELECT_ANY_N', total_questions: 2, questions_to_answer: 1, marks_per_question: 10.0, has_subparts: true, has_internal_or_choice: true },
  ],
};

const makeSubparts = (marks) => ([
  { label: 'a', marks: marks / 2, question_text: '', answer_key: '' },
  { label: 'b', marks: marks / 2, question_text: '', answer_key: '' },
]);

const makeManualQuestion = (questionNumber, marks, hasSubparts) => ({
  question_number: questionNumber,
  marks,
  course_outcome: 'CO1',
  blooms_taxonomy: 'Remember',
  difficulty_level: 'Easy',
  question_type: 'Short Answer',
  expected_depth: 'Brief definition',
  keywords: '',
  answer_key: '',
  ...(hasSubparts ? { subparts: makeSubparts(marks) } : {}),
});

const buildSectionFromPart = (part, partIdx) => ({
  section_name: part.part_name,
  choice_type: part.choice_type,
  total_questions: part.total_questions,
  questions_to_answer: part.questions_to_answer,
  marks_per_question: part.marks_per_question,
  has_subparts: part.has_subparts,
  has_internal_or_choice: part.has_internal_or_choice,
  total_marks: part.questions_to_answer * part.marks_per_question,
  instructions: part.choice_type === 'SELECT_ANY_N'
    ? `Answer any ${part.questions_to_answer} of ${part.total_questions} questions.`
    : 'Answer all questions.',
  questions: Array.from({ length: part.total_questions }, (_, i) =>
    makeManualQuestion(`Q${partIdx * 100 + i + 1}`, part.marks_per_question, part.has_subparts)
  ),
});

const SAMPLE_BLUEPRINT_JSON = JSON.stringify(
  {
    exam_name: "Internal Assessment I",
    subject: "Cloud Computing & Distributed Systems",
    subject_code: "IT8401",
    regulation: "R2021",
    semester: "SEM-06",
    department: "Computer Science and Engineering",
    duration_minutes: 90,
    maximum_marks: 50.0,
    exam_type: "INTERNAL_NORMAL",
    status: "Approved",
    blueprint_type: "json_upload",
    sections: [
      {
        section_name: "Part A",
        choice_type: "ALL_COMPULSORY",
        total_questions: 12,
        questions_to_answer: 12,
        marks_per_question: 0.5,
        has_subparts: false,
        has_internal_or_choice: false,
        total_marks: 6.0,
        instructions: "Answer all questions.",
        questions: [
          {
            question_number: "Q1",
            marks: 0.5,
            course_outcome: "CO1",
            blooms_taxonomy: "Remember",
            difficulty_level: "Easy",
            question_type: "MCQ",
            expected_depth: "One-line answer",
            keywords: ["Cloud Computing"],
            answer_key: "Cloud computing provides on-demand availability of computer system resources."
          },
          {
            question_number: "Q2",
            marks: 0.5,
            course_outcome: "CO1",
            blooms_taxonomy: "Remember",
            difficulty_level: "Easy",
            question_type: "MCQ",
            expected_depth: "One-line answer",
            keywords: ["Virtualization"],
            answer_key: "Virtualization creates a virtual version of a resource such as a server or OS."
          }
        ]
      },
      {
        section_name: "Part B",
        choice_type: "ALL_COMPULSORY",
        total_questions: 3,
        questions_to_answer: 3,
        marks_per_question: 2.0,
        has_subparts: false,
        has_internal_or_choice: false,
        total_marks: 6.0,
        instructions: "Answer all questions.",
        questions: [
          {
            question_number: "Q13",
            marks: 2.0,
            course_outcome: "CO2",
            blooms_taxonomy: "Understand",
            difficulty_level: "Medium",
            question_type: "Short Answer",
            expected_depth: "Short explanation",
            keywords: ["IaaS", "PaaS", "SaaS"],
            answer_key: "IaaS offers infrastructure, PaaS provides platform/frameworks, and SaaS delivers complete software applications."
          }
        ]
      },
      {
        section_name: "Part C",
        choice_type: "SELECT_ANY_N",
        total_questions: 3,
        questions_to_answer: 2,
        marks_per_question: 14.0,
        has_subparts: true,
        has_internal_or_choice: true,
        total_marks: 28.0,
        instructions: "Answer any 2 of 3 questions.",
        questions: [
          {
            question_number: "Q16",
            marks: 14.0,
            course_outcome: "CO3",
            blooms_taxonomy: "Apply",
            difficulty_level: "Hard",
            question_type: "Theory",
            expected_depth: "Detailed explanation with diagrams",
            keywords: ["Distributed Systems"],
            answer_key: "",
            subparts: [
              { label: "a", marks: 8.0, question_text: "Explain the architecture in detail.", answer_key: "" },
              { label: "b", marks: 6.0, question_text: "Discuss its advantages and limitations.", answer_key: "" }
            ]
          }
        ]
      },
      {
        section_name: "Part D",
        choice_type: "SELECT_ANY_N",
        total_questions: 2,
        questions_to_answer: 1,
        marks_per_question: 10.0,
        has_subparts: true,
        has_internal_or_choice: true,
        total_marks: 10.0,
        instructions: "Answer any 1 of 2 questions.",
        questions: [
          {
            question_number: "Q19",
            marks: 10.0,
            course_outcome: "CO4",
            blooms_taxonomy: "Analyze",
            difficulty_level: "Hard",
            question_type: "Theory",
            expected_depth: "Case-study level analysis",
            keywords: ["Case Study"],
            answer_key: "",
            subparts: [
              { label: "a", marks: 5.0, question_text: "Analyze the given case study scenario.", answer_key: "" },
              { label: "b", marks: 5.0, question_text: "Propose an improved design.", answer_key: "" }
            ]
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
    exam_name: 'Internal Assessment I',
    subject: 'Cloud Computing & Distributed Systems',
    subject_code: 'IT8401',
    regulation: 'R2021',
    semester: 'SEM-06',
    department: 'Computer Science',
    duration_minutes: 90,
    maximum_marks: INTERNAL_NORMAL_TEMPLATE.total_marks,
    exam_type: INTERNAL_NORMAL_TEMPLATE.exam_type,
  });

  // Manual Builder State - defaults to the fixed INTERNAL_NORMAL Part A-D template
  const [manualSections, setManualSections] = useState(
    INTERNAL_NORMAL_TEMPLATE.parts.map(buildSectionFromPart)
  );

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
    const marksPerQuestion = 5;
    setManualSections([
      ...manualSections,
      {
        section_name: `Part ${String.fromCharCode(65 + manualSections.length)}`,
        choice_type: 'ALL_COMPULSORY',
        total_questions: 1,
        questions_to_answer: 1,
        marks_per_question: marksPerQuestion,
        has_subparts: false,
        has_internal_or_choice: false,
        total_marks: marksPerQuestion,
        instructions: 'Answer required questions.',
        questions: [makeManualQuestion(`Q${manualSections.length * 10 + 1}`, marksPerQuestion, false)]
      }
    ]);
  };

  const addManualQuestion = (secIdx) => {
    const updated = [...manualSections];
    const section = updated[secIdx];
    const qCount = section.questions.length + 1;
    const marks = section.marks_per_question ?? 2;
    section.questions.push(makeManualQuestion(`Q${qCount}`, marks, !!section.has_subparts));
    setManualSections(updated);
  };

  const updateSectionField = (secIdx, field, value) => {
    const updated = [...manualSections];
    updated[secIdx] = { ...updated[secIdx], [field]: value };
    setManualSections(updated);
  };

  const updateSubpart = (secIdx, qIdx, spIdx, field, value) => {
    const updated = [...manualSections];
    updated[secIdx].questions[qIdx].subparts[spIdx][field] = value;
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
                    <span>Marks per Question</span>
                    <input
                      type="number"
                      step="0.5"
                      value={sec.marks_per_question ?? ''}
                      onChange={(e) => {
                        const marksPerQuestion = parseFloat(e.target.value);
                        const updated = [...manualSections];
                        const target = updated[secIdx];
                        target.marks_per_question = marksPerQuestion;
                        target.total_marks = (target.questions_to_answer ?? target.questions.length) * marksPerQuestion;
                        setManualSections(updated);
                      }}
                    />
                  </label>
                  <label className="field">
                    <span>Choice Type</span>
                    <select
                      value={sec.choice_type || 'ALL_COMPULSORY'}
                      onChange={(e) => updateSectionField(secIdx, 'choice_type', e.target.value)}
                    >
                      <option value="ALL_COMPULSORY">All Compulsory</option>
                      <option value="SELECT_ANY_N">Select Any N</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Total Questions</span>
                    <input
                      type="number"
                      value={sec.total_questions ?? sec.questions.length}
                      onChange={(e) => updateSectionField(secIdx, 'total_questions', parseInt(e.target.value, 10))}
                    />
                  </label>
                  {sec.choice_type === 'SELECT_ANY_N' && (
                    <label className="field">
                      <span>Questions to Answer</span>
                      <input
                        type="number"
                        value={sec.questions_to_answer ?? ''}
                        onChange={(e) => {
                          const questionsToAnswer = parseInt(e.target.value, 10);
                          const updated = [...manualSections];
                          const target = updated[secIdx];
                          target.questions_to_answer = questionsToAnswer;
                          target.total_marks = questionsToAnswer * (target.marks_per_question ?? 0);
                          setManualSections(updated);
                        }}
                      />
                    </label>
                  )}
                  <label className="field">
                    <span>Total Marks (auto)</span>
                    <input type="number" value={sec.total_marks} readOnly />
                  </label>
                  <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={!!sec.has_subparts}
                      onChange={(e) => updateSectionField(secIdx, 'has_subparts', e.target.checked)}
                    />
                    <span>Has Sub-parts (a/b)</span>
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

                      {sec.has_subparts && Array.isArray(q.subparts) && (
                        <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px dashed #cbd5e1' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Sub-parts</span>
                            {Math.abs(q.subparts.reduce((sum, sp) => sum + (parseFloat(sp.marks) || 0), 0) - q.marks) > 0.01 && (
                              <span style={{ color: '#dc2626', fontSize: '0.75rem' }}>
                                Sub-part marks must sum to {q.marks}
                              </span>
                            )}
                          </div>
                          {q.subparts.map((sp, spIdx) => (
                            <div key={spIdx} className="form-grid" style={{ marginBottom: '0.5rem' }}>
                              <label className="field">
                                <span>Label</span>
                                <input
                                  value={sp.label}
                                  onChange={(e) => updateSubpart(secIdx, qIdx, spIdx, 'label', e.target.value)}
                                />
                              </label>
                              <label className="field">
                                <span>Marks</span>
                                <input
                                  type="number"
                                  step="0.5"
                                  value={sp.marks}
                                  onChange={(e) => updateSubpart(secIdx, qIdx, spIdx, 'marks', parseFloat(e.target.value))}
                                />
                              </label>
                              <label className="field full-field">
                                <span>Sub-part Question Text</span>
                                <input
                                  value={sp.question_text}
                                  onChange={(e) => updateSubpart(secIdx, qIdx, spIdx, 'question_text', e.target.value)}
                                />
                              </label>
                            </div>
                          ))}
                        </div>
                      )}
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
