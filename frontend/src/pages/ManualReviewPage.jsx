import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Eye, CheckCircle2, XCircle, RefreshCw, AlertTriangle, FileText } from 'lucide-react';

export default function ManualReviewPage({ apiKey }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notesMap, setNotesMap] = useState({});

  const fetchItems = async () => {
    setLoading(true);
    try {
      const headers = {};
      if (apiKey) headers['x-api-key'] = apiKey;
      const res = await axios.get('/evaluations/manual-review', { headers });
      setItems(res.data.items || []);
    } catch (err) {
      console.error(err);
      toast.error('Failed to fetch manual review items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [apiKey]);

  const handleAction = async (evaluationId, action) => {
    try {
      const headers = {};
      if (apiKey) headers['x-api-key'] = apiKey;
      const notes = notesMap[evaluationId] || '';
      await axios.post(`/evaluations/${evaluationId}/review`, { action, notes }, { headers });
      toast.success(`Evaluation ${action}d successfully`);
      fetchItems();
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || `Failed to ${action} evaluation`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Eye className="w-7 h-7 text-amber-500" />
            Faculty / Admin Manual Review Queue
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Step 9: Answer scripts flagged due to OCR confidence &lt; 80% or OpenCV quality gate warnings.
          </p>
        </div>
        <button
          onClick={fetchItems}
          className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Queue
        </button>
      </div>

      {loading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center card-shadow">
          <RefreshCw className="w-8 h-8 text-emerald-600 animate-spin mx-auto mb-2" />
          <p className="text-sm font-semibold text-gray-600">Loading manual review queue...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center card-shadow">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <p className="font-bold text-gray-800 text-base">Review Queue Clear!</p>
          <p className="text-xs text-gray-400 mt-1">All processed answer sheets met high confidence and quality thresholds.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {items.map((item) => (
            <div key={item.evaluation_id} className="bg-white border border-amber-200 rounded-xl p-6 card-shadow space-y-4">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 border-b border-gray-100 pb-3">
                <div>
                  <span className="text-xs font-bold uppercase text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-mono">
                    Evaluation ID: {item.evaluation_id}
                  </span>
                  <div className="text-xs text-gray-500 mt-1 flex gap-4">
                    <span>Subject: <strong>{item.subject_id}</strong></span>
                    <span>Student Hash: <strong className="font-mono text-gray-700">{item.student_hash?.substring(0, 16)}...</strong></span>
                    <span>Confidence: <strong className="text-amber-700">{item.overall_confidence ? `${(item.overall_confidence * 100).toFixed(1)}%` : 'N/A'}</strong></span>
                  </div>
                </div>
                <span className="bg-amber-100 text-amber-900 text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> {item.status}
                </span>
              </div>

              {item.error_message && (
                <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg text-xs">
                  <strong>Reason Flagged:</strong> {item.error_message}
                </div>
              )}

              {/* Transcript Preview */}
              {item.ocr_data?.pages?.length > 0 && (
                <div className="bg-gray-900 text-gray-200 p-3 rounded-lg text-xs font-mono max-h-40 overflow-y-auto">
                  {item.ocr_data.pages.map((p) => (
                    <div key={p.page_number} className="mb-2">
                      <span className="text-amber-400 font-bold">Page {p.page_number}:</span> {p.transcript || '[No text extracted]'}
                    </div>
                  ))}
                </div>
              )}

              {/* Review Actions */}
              <div className="flex flex-col md:flex-row items-center gap-3 pt-2">
                <input
                  type="text"
                  placeholder="Review notes / comments (optional)"
                  value={notesMap[item.evaluation_id] || ''}
                  onChange={(e) => setNotesMap({ ...notesMap, [item.evaluation_id]: e.target.value })}
                  className="flex-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
                <div className="flex items-center gap-2 w-full md:w-auto">
                  <button
                    onClick={() => handleAction(item.evaluation_id, 'approve')}
                    className="flex-1 md:flex-initial px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                  </button>
                  <button
                    onClick={() => handleAction(item.evaluation_id, 'reprocess')}
                    className="flex-1 md:flex-initial px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Reprocess
                  </button>
                  <button
                    onClick={() => handleAction(item.evaluation_id, 'reject')}
                    className="flex-1 md:flex-initial px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition"
                  >
                    <XCircle className="w-3.5 h-3.5" /> Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
