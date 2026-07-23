import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { BookOpen, Code, Download, FileSpreadsheet, Layers, LayoutList, Trash2 } from 'lucide-react';
import { Card, PageHeader } from '../components/ui';

export default function BlueprintPage({ apiKey }) {
  const [blueprints, setBlueprints] = useState([]);
  const [selectedBlueprint, setSelectedBlueprint] = useState(null);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState('visual'); // 'visual' | 'json'

  const fetchBlueprints = async () => {
    setLoading(true);
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      const res = await axios.get('/api/blueprints', { headers });
      const items = res.data || [];
      setBlueprints(items);
      if (items.length > 0 && !selectedBlueprint) {
        setSelectedBlueprint(items[0]);
      }
    } catch (err) {
      console.error(err);
      toast.error('Failed to load blueprints list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBlueprints();
  }, [apiKey]);

  const deleteBlueprint = async (blueprintId, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this blueprint model?')) return;
    try {
      const headers = apiKey ? { 'x-api-key': apiKey } : {};
      await axios.delete(`/api/blueprints/${blueprintId}`, { headers });
      toast.success('Blueprint deleted successfully.');
      if (selectedBlueprint?.blueprint_id === blueprintId) {
        setSelectedBlueprint(null);
      }
      fetchBlueprints();
    } catch (err) {
      console.error(err);
      toast.error('Failed to delete blueprint.');
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
        eyebrow="Blueprints / Repository"
        title="Exam Blueprints & Layout Models"
        description="Inspect generated exam blueprints, structured question taxonomies, and raw JSON models."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '1.5rem' }}>
        {/* Left Column: List of Blueprints */}
        <Card title="Stored Blueprints" description={`${blueprints.length} total blueprint models`}>
          {loading ? (
            <p style={{ color: '#6b7280', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>Loading blueprints...</p>
          ) : blueprints.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem 0', color: '#9ca3af' }}>
              <BookOpen size={24} style={{ margin: '0 auto 0.5rem' }} />
              <p style={{ fontSize: '0.85rem' }}>No blueprints generated yet.</p>
              <small style={{ fontSize: '0.75rem' }}>Upload a Question Paper under Question Papers to generate one.</small>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {blueprints.map((bp) => {
                const isSelected = selectedBlueprint?.blueprint_id === bp.blueprint_id;
                return (
                  <div
                    key={bp.blueprint_id}
                    onClick={() => setSelectedBlueprint(bp)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.75rem',
                      borderRadius: '8px',
                      border: isSelected ? '2px solid #10b981' : '1px solid #e5e7eb',
                      background: isSelected ? '#ecfdf5' : '#ffffff',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#111827' }}>
                        {bp.metadata?.subject_code || 'GENERAL'} · {bp.metadata?.subject || 'Question Paper'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.2rem' }}>
                        {bp.metadata?.exam_name || 'Exam'} ({bp.metadata?.maximum_marks || 100} Marks)
                      </div>
                    </div>
                    <button
                      onClick={(e) => deleteBlueprint(bp.blueprint_id, e)}
                      title="Delete Blueprint"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#ef4444',
                        padding: '0.3rem',
                        cursor: 'pointer',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Right Column: Blueprint Details & JSON Viewer */}
        {selectedBlueprint ? (
          <Card
            title={`${selectedBlueprint.metadata?.subject || 'Blueprint'} (${selectedBlueprint.metadata?.subject_code || ''})`}
            description={`ID: ${selectedBlueprint.blueprint_id}`}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Header Action Controls */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e5e7eb', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', background: '#f3f4f6', padding: '0.25rem', borderRadius: '8px' }}>
                  <button
                    onClick={() => setViewMode('visual')}
                    style={{
                      padding: '0.4rem 0.8rem',
                      borderRadius: '6px',
                      border: 'none',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: viewMode === 'visual' ? '#ffffff' : 'transparent',
                      color: viewMode === 'visual' ? '#10b981' : '#4b5563',
                      boxShadow: viewMode === 'visual' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <LayoutList size={14} /> Blueprint Layout
                  </button>
                  <button
                    onClick={() => setViewMode('json')}
                    style={{
                      padding: '0.4rem 0.8rem',
                      borderRadius: '6px',
                      border: 'none',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: viewMode === 'json' ? '#ffffff' : 'transparent',
                      color: viewMode === 'json' ? '#10b981' : '#4b5563',
                      boxShadow: viewMode === 'json' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <Code size={14} /> Raw JSON Model
                  </button>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={(e) => deleteBlueprint(selectedBlueprint.blueprint_id, e)}
                    style={{
                      padding: '0.4rem 0.8rem',
                      borderRadius: '6px',
                      border: '1px solid #fca5a5',
                      background: '#fef2f2',
                      color: '#dc2626',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                    }}
                  >
                    <Trash2 size={14} /> Delete Blueprint
                  </button>
                  {selectedBlueprint.blueprint_url && (
                    <a
                      href={selectedBlueprint.blueprint_url}
                      target="_blank"
                      rel="noreferrer"
                      className="secondary-button"
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', textDecoration: 'none' }}
                    >
                      <Download size={14} /> Blueprint JSON
                    </a>
                  )}
                  {selectedBlueprint.faculty_answer_key_s3_url && (
                    <a
                      href={selectedBlueprint.faculty_answer_key_s3_url}
                      target="_blank"
                      rel="noreferrer"
                      className="secondary-button"
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', textDecoration: 'none' }}
                    >
                      <Download size={14} /> Answer Key File
                    </a>
                  )}
                </div>
              </div>

              {/* VIEW MODE 1: VISUAL BLUEPRINT */}
              {viewMode === 'visual' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem', background: '#f9fafb', padding: '1rem', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                    <div>
                      <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Exam Name</small>
                      <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{selectedBlueprint.metadata?.exam_name}</p>
                    </div>
                    <div>
                      <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Regulation / Sem</small>
                      <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{selectedBlueprint.metadata?.regulation} / Sem {selectedBlueprint.metadata?.semester}</p>
                    </div>
                    <div>
                      <small style={{ color: '#6b7280', fontSize: '0.75rem', textTransform: 'uppercase' }}>Max Marks / Duration</small>
                      <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{selectedBlueprint.metadata?.maximum_marks} Marks / {selectedBlueprint.metadata?.duration_minutes} min</p>
                    </div>
                  </div>

                  {selectedBlueprint.sections?.map((section, idx) => (
                    <div key={section.section_id || idx} style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '1rem', background: '#ffffff' }}>
                      <div style={{ fontWeight: 600, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', borderBottom: '1px solid #f3f4f6', paddingBottom: '0.5rem' }}>
                        <Layers size={18} color="#10b981" />
                        <span>{section.name}</span>
                        {section.instructions && <small style={{ color: '#6b7280', fontWeight: 400, marginLeft: 'auto' }}>{section.instructions}</small>}
                      </div>

                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead>
                          <tr style={{ background: '#f9fafb', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                            <th style={{ padding: '0.5rem', width: '60px' }}>Q.No</th>
                            <th style={{ padding: '0.5rem' }}>Question Description</th>
                            <th style={{ padding: '0.5rem', width: '120px' }}>Type</th>
                            <th style={{ padding: '0.5rem', width: '60px' }}>Marks</th>
                            <th style={{ padding: '0.5rem' }}>Faculty Answer Key Mapping</th>
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
                </div>
              ) : (
                /* VIEW MODE 2: RAW JSON MODEL */
                <div style={{ background: '#0f172a', color: '#f8fafc', padding: '1.25rem', borderRadius: '8px', overflowX: 'auto', fontFamily: 'monospace', fontSize: '0.8rem', lineHeight: '1.5' }}>
                  <pre style={{ margin: 0 }}>{JSON.stringify(selectedBlueprint, null, 2)}</pre>
                </div>
              )}
            </div>
          </Card>
        ) : (
          <Card title="Blueprint Viewer" description="Select a blueprint from the list to view.">
            <div style={{ textAlign: 'center', padding: '4rem 0', color: '#9ca3af' }}>
              <FileSpreadsheet size={32} style={{ margin: '0 auto 0.5rem' }} />
              <p style={{ fontSize: '0.9rem' }}>Select a blueprint model from the list to inspect.</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
