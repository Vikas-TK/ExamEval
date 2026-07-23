import React from 'react';
import { ArrowRight, BookOpen, CheckCircle2, Sparkles, UploadCloud } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/ui';

export default function Dashboard() {
  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Academic Evaluation Workspace"
        title="Welcome to EvalFlow"
        description="AI-Based Automated Answer Script Evaluation & Blueprint Platform."
      />

      {/* CLEAN WHITE BACKGROUND WELCOME CARD WITH DARK TEXT */}
      <div
        style={{
          borderRadius: '0.75rem',
          background: '#ffffff',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
          border: '1px solid #e2e8f0',
          padding: '2.5rem',
          color: '#0f172a',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            color: '#047857',
            padding: '0.35rem 0.85rem',
            borderRadius: '9999px',
            fontSize: '0.85rem',
            fontWeight: 600,
            marginBottom: '1.25rem',
          }}
        >
          <Sparkles size={15} /> GOT-OCR 2.0 & Multi-Agent Evaluation Engine
        </div>

        <h1
          style={{
            fontSize: '2.25rem',
            fontWeight: 800,
            margin: '0 0 0.85rem 0',
            letterSpacing: '-0.025em',
            color: '#0f172a',
            lineHeight: 1.2,
          }}
        >
          Welcome to Automated Answer Script Evaluation
        </h1>

        <p
          style={{
            fontSize: '1.1rem',
            color: '#475569',
            maxWidth: '740px',
            margin: '0 0 2.25rem 0',
            lineHeight: 1.6,
          }}
        >
          Streamline your institutional examination workflows. Ingest handwritten student scripts, automatically generate structured question paper blueprints, run multi-agent evaluation, and view consolidated evaluation metrics.
        </p>

        {/* Quick Action Navigation Buttons */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
          <Link
            to="/answer-sheets"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1.25rem',
              borderRadius: '0.75rem',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              color: '#0f172a',
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <UploadCloud size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem', color: '#0f172a' }}>Evaluate Papers</strong>
              <small style={{ color: '#64748b', fontSize: '0.8rem' }}>Upload student answer scripts</small>
            </div>
            <ArrowRight size={16} style={{ color: '#94a3b8' }} />
          </Link>

          <Link
            to="/question-papers"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1.25rem',
              borderRadius: '0.75rem',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              color: '#0f172a',
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <BookOpen size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem', color: '#0f172a' }}>Question Papers</strong>
              <small style={{ color: '#64748b', fontSize: '0.8rem' }}>Build & edit blueprints</small>
            </div>
            <ArrowRight size={16} style={{ color: '#94a3b8' }} />
          </Link>

          <Link
            to="/manual-review"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1.25rem',
              borderRadius: '0.75rem',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              color: '#0f172a',
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <CheckCircle2 size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem', color: '#0f172a' }}>Manual Review</strong>
              <small style={{ color: '#64748b', fontSize: '0.8rem' }}>Review review queues</small>
            </div>
            <ArrowRight size={16} style={{ color: '#94a3b8' }} />
          </Link>
        </div>
      </div>
    </div>
  );
}
