import React from 'react';
import { Bell, Menu, Search, ShieldCheck } from 'lucide-react';

export default function Header({ onMenu }) {
  return <header className="topbar"><button className="mobile-menu icon-button" onClick={onMenu} aria-label="Open navigation"><Menu size={21} /></button><div className="topbar-context"><span className="context-icon"><ShieldCheck size={15} /></span><span>Evaluation workspace</span><span className="context-separator">/</span><strong>Overview</strong></div><div className="topbar-actions"><label className="search-box"><Search size={16} /><input placeholder="Search workspace" aria-label="Search workspace" /><kbd>⌘ K</kbd></label><button className="topbar-icon icon-button" aria-label="Notifications"><Bell size={18} /><span className="notification-dot" /></button><span className="topbar-avatar">AS</span></div></header>;
}
