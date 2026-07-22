import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BarChart3, BookOpen, ClipboardCheck, FileCheck2, FileText, GraduationCap, LayoutDashboard, Settings, UploadCloud, X } from 'lucide-react';

const primaryLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/answer-sheets', label: 'Answer sheets', icon: FileText },
  { to: '/question-papers', label: 'Question papers', icon: BookOpen },
  { to: '/manual-review', label: 'Manual review', icon: ClipboardCheck, badge: '4' },
  { to: '/blueprints', label: 'Blueprints', icon: FileCheck2 },
  { to: '/academic-master', label: 'Academic master', icon: GraduationCap },
];

export default function Sidebar({ open, onClose }) {
  const location = useLocation();
  return <>
    {open && <button className="sidebar-backdrop" onClick={onClose} aria-label="Close navigation" />}
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-brand"><span className="brand-mark"><FileCheck2 size={18} /></span><span>Eval<span className="brand-accent">Flow</span></span><button className="mobile-close icon-button" onClick={onClose} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-switcher"><span className="workspace-avatar">CE</span><span><strong>College of Engineering</strong><small>Institution workspace</small></span><span className="switcher-dot" /></div>
      <nav className="sidebar-nav" aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        {primaryLinks.map(({ to, label, icon: Icon, badge }) => <Link key={to} to={to} onClick={onClose} className={`nav-link ${location.pathname === to || (to === '/answer-sheets' && location.pathname === '/ocr-results') ? 'active' : ''}`}><Icon size={17} /><span>{label}</span>{badge && <span className="nav-badge">{badge}</span>}</Link>)}
        <p className="nav-label nav-label-spaced">Manage</p>
        <Link to="/reports" onClick={onClose} className={`nav-link ${location.pathname === '/reports' ? 'active' : ''}`}><BarChart3 size={17} /><span>Reports</span><span className="coming-soon">Soon</span></Link>
        <Link to="/settings" onClick={onClose} className={`nav-link ${location.pathname === '/settings' ? 'active' : ''}`}><Settings size={17} /><span>Settings</span></Link>
      </nav>
      <div className="sidebar-help"><div className="help-icon"><UploadCloud size={16} /></div><div><strong>Need a hand?</strong><p>View the processing guide</p></div></div>
      <div className="sidebar-user"><span className="user-avatar">AS</span><div><strong>Alex Sharma</strong><small>Administrator</small></div><button className="user-menu" aria-label="Open user menu">•••</button></div>
    </aside>
  </>;
}
