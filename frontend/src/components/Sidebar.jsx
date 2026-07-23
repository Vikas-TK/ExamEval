import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  BarChart3,
  BookOpen,
  Brain,
  ClipboardCheck,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  GraduationCap,
  HelpCircle,
  History,
  LayoutDashboard,
  Settings,
  Sparkles,
  UploadCloud,
  UserCheck,
  X,
} from 'lucide-react';

const primaryLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/answer-sheets', label: 'Evaluate papers', icon: FileText },
  { to: '/question-papers', label: 'Question papers', icon: BookOpen },
  { to: '/manual-review', label: 'Manual review', icon: ClipboardCheck, badge: '4' },
  { to: '/blueprints', label: 'Blueprints', icon: FileCheck2 },
  { to: '/qa-mapping', label: 'Q&A Mapping', icon: Brain },
  { to: '/evaluate', label: 'AI Evaluation', icon: Sparkles },
  { to: '/results-matrix', label: 'Marks Matrix', icon: FileSpreadsheet },
  { to: '/academic-master', label: 'Academic master', icon: GraduationCap },
];

const secondaryLinks = [
  { to: '/question-analysis', label: 'Question analysis', icon: HelpCircle },
  { to: '/student-performance', label: 'Student performance', icon: UserCheck },
  { to: '/history', label: 'Evaluation history', icon: History },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar({ open, onClose }) {
  const location = useLocation();

  return (
    <>
      {open && <button className="sidebar-backdrop" onClick={onClose} aria-label="Close navigation" />}
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <span className="brand-mark">
            <FileCheck2 size={18} />
          </span>
          <span>
            Eval<span className="brand-accent">Flow</span>
          </span>
          <button className="mobile-close icon-button" onClick={onClose} aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>
        <div className="workspace-switcher">
          <span className="workspace-avatar">CE</span>
          <span>
            <strong>College of Engineering</strong>
            <small>Institution workspace</small>
          </span>
          <span className="switcher-dot" />
        </div>
        <nav className="sidebar-nav" aria-label="Primary navigation">
          <p className="nav-label">Workspace</p>
          {primaryLinks.map(({ to, label, icon: Icon, badge }) => (
            <Link
              key={to}
              to={to}
              onClick={onClose}
              className={`nav-link ${
                location.pathname === to ||
                (to === '/answer-sheets' && (location.pathname === '/ocr-results' || location.pathname === '/evaluate-papers'))
                  ? 'active'
                  : ''
              }`}
            >
              <Icon size={17} />
              <span>{label}</span>
              {badge && <span className="nav-badge">{badge}</span>}
            </Link>
          ))}
          <p className="nav-label nav-label-spaced">Analytics & Manage</p>
          {secondaryLinks.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={onClose}
              className={`nav-link ${location.pathname === to ? 'active' : ''}`}
            >
              <Icon size={17} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-help">
          <div className="help-icon">
            <UploadCloud size={16} />
          </div>
          <div>
            <strong>Need a hand?</strong>
            <p>View processing guide</p>
          </div>
        </div>
        <div className="sidebar-user">
          <span className="user-avatar">AS</span>
          <div>
            <strong>Alex Sharma</strong>
            <small>Administrator</small>
          </div>
          <button className="user-menu" aria-label="Open user menu">
            •••
          </button>
        </div>
      </aside>
    </>
  );
}
