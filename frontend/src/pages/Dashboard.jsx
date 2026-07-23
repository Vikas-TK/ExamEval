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

      {/* MINIMALIST TEXT WELCOME HERO */}
      <div
        style={{
          borderRadius: '1rem',
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          boxShadow: '0 10px 25px -5px rgba(15, 23, 42, 0.15)',
          border: '1px solid #334155',
          padding: '3rem 2.5rem',
          color: '#ffffff',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid #10b981',
            color: '#34d399',
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
            fontSize: '2.5rem',
            fontWeight: 800,
            margin: '0 0 1rem 0',
            letterSpacing: '-0.025em',
            color: '#f8fafc',
            lineHeight: 1.2,
          }}
        >
          Welcome to Automated Answer Script Evaluation
        </h1>

        <p
          style={{
            fontSize: '1.125rem',
            color: '#94a3b8',
            maxWidth: '720px',
            margin: '0 0 2.5rem 0',
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
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              textDecoration: 'none',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <UploadCloud size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem' }}>Evaluate Papers</strong>
              <small style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Upload student answer scripts</small>
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
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              textDecoration: 'none',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <BookOpen size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem' }}>Question Papers</strong>
              <small style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Build & edit blueprints</small>
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
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              textDecoration: 'none',
            }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '0.5rem', background: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <CheckCircle2 size={20} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem' }}>Manual Review</strong>
              <small style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Review review queues</small>
            </div>
            <ArrowRight size={16} style={{ color: '#94a3b8' }} />
          </Link>
        </div>
      </div>
    </div>
  );
}
