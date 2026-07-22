import React, { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { FileSpreadsheet, Upload, CheckCircle2, Download, Layers, BookOpen } from 'lucide-react';

export default function BlueprintPage({ apiKey }) {
  const [ocrJsonInput, setOcrJsonInput] = useState(
    JSON.stringify(
      {
        pages: [
          {
            transcript:
              "Exam Name: End Semester Examination\nSubject: Database Management Systems\nSubject Code: CS8451\nRegulation: R2021\nSemester: IV\nDepartment: Computer Science and Engineering\nDuration: 180 minutes\nMaximum Marks: 100\n\nPart A: Short Answer Questions (Answer all questions)\n1. Define First Normal Form (1NF). (2 marks)\n2. What is a Foreign Key constraint? (2 marks)\n\nPart B: Descriptive Questions\n3. Explain relational database normalization up to BCNF with examples. (16 marks)",
          },
        ],
      },
      null,
      2
    )
  );

  const [metadata, setMetadata] = useState({
    exam_name: 'End Semester Examination',
    subject: 'Database Management Systems',
    subject_code: 'CS8451',
    regulation: 'R2021',
    semester: 'SEM-04',
    department: 'CSE',
    duration_minutes: 180,
    maximum_marks: 100,
  });

  const [answerKeyFile, setAnswerKeyFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [blueprintData, setBlueprintData] = useState(null);

  const handleJsonFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      setOcrJsonInput(evt.target.result);
      toast.success('Loaded OCR JSON file content.');
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ocrJsonInput.trim()) {
      toast.error('Please enter or upload valid OCR JSON.');
      return;
    }

    setLoading(true);
    const data = new FormData();
    data.append('ocr_json', ocrJsonInput);
    if (metadata.subject && metadata.subject_code) {
      data.append('metadata', JSON.stringify(metadata));
    }
    if (answerKeyFile) {
      data.append('answer_key', answerKeyFile);
    }

    const headers = {};
    if (apiKey) headers['x-api-key'] = apiKey;

    try {
      const createRes = await axios.post('/blueprints', data, { headers });
      toast.success('Blueprint layout generated successfully!');
      
      // Fetch full details
      const detailRes = await axios.get(`/blueprints/${createRes.data.blueprint_id}`, { headers });
      setBlueprintData(detailRes.data);
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || 'Blueprint generation failed');
    } finally {
      setLoading(false);
    }
  };

  const getQuestionBadge = (type) => {
    switch (type) {
      case 'MCQ':
        return <span className="bg-purple-100 text-purple-800 text-xs font-semibold px-2 py-0.5 rounded">MCQ</span>;
      case 'SHORT_ANSWER':
        return <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-0.5 rounded">Short Answer</span>;
      case 'DESCRIPTIVE':
        return <span className="bg-emerald-100 text-emerald-800 text-xs font-semibold px-2 py-0.5 rounded">Descriptive</span>;
      case 'DIAGRAM':
        return <span className="bg-amber-100 text-amber-800 text-xs font-semibold px-2 py-0.5 rounded">Diagram</span>;
      default:
        return <span className="bg-gray-100 text-gray-800 text-xs font-semibold px-2 py-0.5 rounded">{type}</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* Blueprint Generation Form */}
      <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl p-6 card-shadow space-y-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <FileSpreadsheet className="w-6 h-6 text-emerald-600" />
            Exam Blueprint Generator
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Phase 2: Extract question paper metadata, sections, marks, question taxonomy & faculty answer key mapping.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">Question Paper OCR JSON</label>
              <label htmlFor="json-upload" className="text-xs text-emerald-600 hover:underline cursor-pointer font-medium flex items-center gap-1">
                <Upload className="w-3.5 h-3.5" /> Upload File
              </label>
              <input type="file" accept=".json,.txt" id="json-upload" onChange={handleJsonFileUpload} className="hidden" />
            </div>
            <textarea
              rows={6}
              value={ocrJsonInput}
              onChange={(e) => setOcrJsonInput(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              placeholder="Paste OCR JSON here..."
            />
          </div>

          <div className="border-t border-gray-100 pt-3 space-y-3">
            <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider">Optional Exam Metadata</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Exam Name</label>
                <input
                  type="text"
                  value={metadata.exam_name}
                  onChange={(e) => setMetadata({ ...metadata, exam_name: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Subject</label>
                <input
                  type="text"
                  value={metadata.subject}
                  onChange={(e) => setMetadata({ ...metadata, subject: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Subject Code</label>
                <input
                  type="text"
                  value={metadata.subject_code}
                  onChange={(e) => setMetadata({ ...metadata, subject_code: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Regulation</label>
                <input
                  type="text"
                  value={metadata.regulation}
                  onChange={(e) => setMetadata({ ...metadata, regulation: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Faculty Answer Key (TXT / DOCX / PDF)</label>
            <input
              type="file"
              accept=".txt,.docx,.pdf"
              onChange={(e) => setAnswerKeyFile(e.target.files[0] || null)}
              className="w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-amber-500 hover:from-emerald-700 hover:to-amber-600 text-white font-semibold shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? 'Analyzing & Building...' : 'Generate Blueprint Model'}
          </button>
        </form>
      </div>

      {/* Blueprint Display Dashboard */}
      <div className="lg:col-span-7 space-y-6">
        {blueprintData ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6 card-shadow space-y-6">
            <div className="flex justify-between items-start border-b border-gray-100 pb-4">
              <div>
                <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-mono">
                  Blueprint ID: {blueprintData.blueprint_id}
                </span>
                <h3 className="text-lg font-bold text-gray-900 mt-2">{blueprintData.metadata.exam_name}</h3>
                <p className="text-xs text-gray-500">{blueprintData.metadata.subject} ({blueprintData.metadata.subject_code}) &bull; {blueprintData.metadata.regulation} &bull; Semester {blueprintData.metadata.semester}</p>
              </div>
              <div className="text-right">
                <span className="text-xs text-gray-400 block">Total Marks / Duration</span>
                <span className="text-sm font-bold text-gray-900">{blueprintData.metadata.maximum_marks} Marks / {blueprintData.metadata.duration_minutes} mins</span>
              </div>
            </div>

            {/* Sections & Questions Table */}
            <div className="space-y-6">
              {blueprintData.sections?.map((section, idx) => (
                <div key={section.section_id || idx} className="border border-gray-200 rounded-xl p-4 space-y-3 bg-gray-50/50">
                  <div className="flex justify-between items-center border-b border-gray-200 pb-2">
                    <h4 className="text-sm font-bold text-gray-800 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-emerald-600" />
                      {section.name}
                    </h4>
                    {section.instructions && <span className="text-xs text-gray-500 italic">{section.instructions}</span>}
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-gray-100 text-gray-600 font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="p-2 w-16">Q.No</th>
                          <th className="p-2">Question Text</th>
                          <th className="p-2 w-28">Type</th>
                          <th className="p-2 w-16">Marks</th>
                          <th className="p-2">Answer Key Mapping</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 bg-white">
                        {section.questions?.map((q) => (
                          <tr key={q.question_id || q.question_number}>
                            <td className="p-2 font-bold font-mono">Q{q.question_number}</td>
                            <td className="p-2 text-gray-800">{q.question_text}</td>
                            <td className="p-2">{getQuestionBadge(q.question_type)}</td>
                            <td className="p-2 font-semibold text-gray-900">{q.maximum_marks}</td>
                            <td className="p-2 text-gray-600 italic">
                              {q.faculty_answer || <span className="text-gray-300">Unmapped</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>

            {/* Downloads */}
            <div className="flex gap-4 border-t border-gray-100 pt-4">
              {blueprintData.blueprint_url && (
                <a
                  href={blueprintData.blueprint_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" /> Download Blueprint JSON
                </a>
              )}
              {blueprintData.faculty_answer_key_s3_url && (
                <a
                  href={blueprintData.faculty_answer_key_s3_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" /> Download Answer Key Artifact
                </a>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400 card-shadow">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="font-semibold text-gray-600 text-sm">No Exam Blueprint Generated</p>
            <p className="text-xs text-gray-400 mt-1">Submit the question paper OCR JSON on the left to extract sections and questions.</p>
          </div>
        )}
      </div>
    </div>
  );
}
