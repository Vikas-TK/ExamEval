import React from 'react';
import { Link } from 'react-router-dom';

export default function Footer() {
  return <footer className="app-footer"><div><strong>EvalFlow</strong><span>© 2025 College of Engineering</span><span className="footer-version">v1.0.0</span></div><nav aria-label="Footer navigation"><Link to="/settings">Documentation</Link><Link to="/settings">Support</Link><Link to="/settings">Privacy</Link></nav></footer>;
}
