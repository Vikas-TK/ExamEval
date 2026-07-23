import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { UploadCloud, CheckCircle2, AlertTriangle, RefreshCw, FileText, Download, ShieldCheck } from 'lucide-react';

export default function IngestionPage({ apiKey }) {
  const [formData, setFormData] = useState({
    regulation: 'R2021',
    semester: 'SEM-04',
    subject_id: 'CS8451',
    register_number: '312221104001',
  });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const [currentEvalId, setCurrentEvalId] = useState(null);
  const [evalData, setEvalData] = useState(null);
  const [polling, setPolling] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      toast.error('Please select an answer sheet file to upload.');
      return;
    }

    setLoading(true);
    const data = new FormData();
    data.append('regulation', formData.regulation);
    data.append('semester', formData.semester);
    data.append('subject_id', formData.subject_id);
    data.append('register_number', formData.register_number);
    data.append('file', file);

    const headers = {};
    if (apiKey) headers['x-api-key'] = apiKey;

    try {
      const res = await axios.post('/api/evaluations', data, { headers });
      toast.success('Upload accepted! Identity anonymized & pipeline started.');
      setCurrentEvalId(res.data.evaluation_id);
      setPolling(true);
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || 'Ingestion upload failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let interval = null;
    if (polling && currentEvalId) {
      const poll = async () => {
        try {
          const headers = {};
          if (apiKey) headers['x-api-key'] = apiKey;
          const res = await axios.get(`/api/evaluations/${currentEvalId}`, { headers });
          setEvalData(res.data);
          if (['COMPLETED', 'NEEDS_REVIEW', 'FAILED'].includes(res.data.status)) {
            setPolling(false);
            toast.success(`Pipeline reached state: ${res.data.status}`);
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      };
      poll();
      interval = setInterval(poll, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [polling, currentEvalId, apiKey]);

  const handleDownloadTranscript = async () => {
    if (!currentEvalId) return;
    try {
      const headers = {};
      if (apiKey) headers['x-api-key'] = apiKey;
      const res = await axios.get(`/api/evaluations/${currentEvalId}/transcript`, { headers });
      if (res.data?.url) {
        window.open(res.data.url, '_blank');
      }
    } catch (err) {
      toast.error('Download failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const renderBadge = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="bg-emerald-100 text-emerald-800 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> COMPLETED</span>;
      case 'NEEDS_REVIEW':
        return <span className="bg-amber-100 text-amber-800 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> NEEDS REVIEW</span>;
      case 'FAILED':
        return <span className="bg-red-100 text-red-800 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> FAILED</span>;
      default:
        return <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5 animate-spin" /> PROCESSING</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* Upload Form */}
      <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl p-6 card-shadow space-y-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <UploadCloud className="w-6 h-6 text-emerald-600" />
            Student Script Ingestion
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Phase 1: Zero-trust student identity HMAC hashing, image quality gate, and Qwen2.5-VL OCR.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Regulation</label>
            <input
              type="text"
              required
              value={formData.regulation}
              onChange={(e) => setFormData({ ...formData, regulation: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Semester</label>
              <input
                type="text"
                required
                value={formData.semester}
                onChange={(e) => setFormData({ ...formData, semester: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Subject Code</label>
              <input
                type="text"
                required
                value={formData.subject_id}
                onChange={(e) => setFormData({ ...formData, subject_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Register Number (Anonymized to HMAC SHA-256)</label>
            <input
              type="text"
              required
              value={formData.register_number}
              onChange={(e) => setFormData({ ...formData, register_number: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Answer Sheet (PDF / PNG / JPG)</label>
            <div className="border-2 border-dashed border-gray-300 hover:border-emerald-500 rounded-xl p-6 text-center cursor-pointer transition bg-gray-50 hover:bg-emerald-50/30">
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="cursor-pointer block">
                <FileText className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                <span className="text-sm font-medium text-gray-700 block">
                  {file ? file.name : 'Click to select or drag & drop answer sheet'}
                </span>
                <span className="text-xs text-gray-400 mt-1 block">Supported: PDF, PNG, JPG (Max 25MB)</span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-amber-500 hover:from-emerald-700 hover:to-amber-600 text-white font-semibold shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
            {loading ? 'Anonymizing & Processing...' : 'Submit Answer Sheet'}
          </button>
        </form>
      </div>

      {/* Evaluation Results & Quality Gate */}
      <div className="lg:col-span-7 space-y-6">
        {evalData ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6 card-shadow space-y-6">
            <div className="flex justify-between items-start border-b border-gray-100 pb-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Evaluation Record</span>
                <h3 className="text-lg font-bold text-gray-900 font-mono mt-0.5">{evalData.evaluation_id}</h3>
                <div className="flex items-center gap-4 text-xs text-gray-500 mt-1">
                  <span>Subject: <strong>{evalData.subject_id}</strong></span>
                  {evalData.overall_confidence !== null && (
                    <span>OCR Confidence: <strong className="text-emerald-600">{(evalData.overall_confidence * 100).toFixed(1)}%</strong></span>
                  )}
                </div>
              </div>
              <div>{renderBadge(evalData.status)}</div>
            </div>

            {/* Quality Report Metrics */}
            {evalData.quality_report && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase text-gray-500 tracking-wider">OpenCV Quality Validation Gate</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-center">
                    <span className="text-xs text-gray-400 block">Blur Score</span>
                    <span className={`text-base font-bold ${evalData.quality_report.blur_score < 100 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {evalData.quality_report.blur_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-center">
                    <span className="text-xs text-gray-400 block">Contrast</span>
                    <span className="text-base font-bold text-gray-800">{evalData.quality_report.contrast_score.toFixed(1)}</span>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-center">
                    <span className="text-xs text-gray-400 block">Skew Angle</span>
                    <span className="text-base font-bold text-gray-800">{evalData.quality_report.skew_angle.toFixed(1)}&deg;</span>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-center">
                    <span className="text-xs text-gray-400 block">Noise Score</span>
                    <span className="text-base font-bold text-gray-800">{evalData.quality_report.noise_score.toFixed(1)}</span>
                  </div>
                </div>

                {!evalData.quality_report.passed && evalData.quality_report.failure_reasons?.length > 0 && (
                  <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-xs space-y-1">
                    <span className="font-semibold block flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-600" /> Quality Gate Rejections:
                    </span>
                    <ul className="list-disc list-inside space-y-0.5 text-red-700">
                      {evalData.quality_report.failure_reasons.map((reason, i) => (
                        <li key={i}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* OCR Data & Transcript */}
            {evalData.ocr_data?.pages?.length > 0 && (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-bold uppercase text-gray-500 tracking-wider">Extracted OCR Transcript</h4>
                  <button
                    onClick={handleDownloadTranscript}
                    className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold flex items-center gap-1"
                  >
                    <Download className="w-3.5 h-3.5" /> Download Transcript
                  </button>
                </div>
                <div className="bg-gray-900 text-gray-100 p-4 rounded-xl font-mono text-xs overflow-x-auto max-h-80 space-y-4">
                  {evalData.ocr_data.pages.map((p) => (
                    <div key={p.page_number} className="border-b border-gray-800 pb-3 last:border-none">
                      <div className="text-emerald-400 font-semibold mb-1">
                        --- Page {p.page_number} (Confidence: {(p.confidence * 100).toFixed(0)}%) ---
                      </div>
                      <pre className="whitespace-pre-wrap text-gray-200 leading-relaxed font-mono">{p.transcript || '[No text transcribed]'}</pre>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400 card-shadow">
            <UploadCloud className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="font-semibold text-gray-600 text-sm">No Active Evaluation</p>
            <p className="text-xs text-gray-400 mt-1">Submit an answer sheet on the left to initiate ingestion and view live execution results.</p>
          </div>
        )}
      </div>
    </div>
  );
}
