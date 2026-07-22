import React, { useRef, useState } from 'react';
import { CheckCircle2, ChevronRight, FileText, Loader2, UploadCloud, X } from 'lucide-react';

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = '', title, description, action }) {
  return (
    <section className={`card ${className}`}>
      {(title || description || action) && (
        <div className="card-header">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {description && <p className="card-description">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatusBadge({ status = 'Processing' }) {
  const value = String(status).replaceAll('_', ' ');
  const normalized = value.toLowerCase();
  const tone = normalized.includes('complete') || normalized.includes('approve') || normalized === 'ready' ? 'success' : normalized.includes('review') || normalized.includes('pending') || normalized.includes('process') ? 'warning' : normalized.includes('fail') || normalized.includes('reject') ? 'error' : 'neutral';
  return <span className={`status-badge ${tone}`}><span className="status-dot" />{value}</span>;
}

export function ProgressBar({ value = 0, label, tone = 'green' }) {
  return <div className="progress-wrap">{label && <div className="progress-label"><span>{label}</span><strong>{value}%</strong></div>}<div className="progress-track"><span className={`progress-value ${tone}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div></div>;
}

export function FileUploader({ file, onFile, accept = '.pdf,.png,.jpg,.jpeg', label = 'Drop a file here, or browse', hint = 'PDF, PNG, or JPG up to 25MB' }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const chooseFile = (nextFile) => { if (nextFile) onFile(nextFile); };
  return (
    <div className={`file-uploader ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]); }} onClick={() => inputRef.current?.click()} role="button" tabIndex={0} onKeyDown={(event) => event.key === 'Enter' && inputRef.current?.click()} aria-label="Upload file">
      <input ref={inputRef} type="file" accept={accept} onChange={(event) => chooseFile(event.target.files?.[0])} hidden />
      <span className="upload-icon"><UploadCloud size={21} /></span>
      {file ? <><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} MB · Click to replace</span></> : <><strong>{label}</strong><span>{hint}</span></>}
    </div>
  );
}

export function EmptyState({ icon: Icon = FileText, title, description, action }) {
  return <div className="empty-state"><span className="empty-icon"><Icon size={24} /></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function MetricCard({ label, value, change, icon: Icon, tone = 'green' }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={19} /></div><div className="metric-copy"><p>{label}</p><strong>{value}</strong>{change && <span className="metric-change">{change}</span>}</div><ChevronRight className="metric-arrow" size={17} /></div>;
}

export function LoadingState({ label = 'Loading data' }) { return <div className="loading-state"><Loader2 className="spin" size={22} /><span>{label}</span></div>; }

export function ToastAction({ onClose }) { return <button className="icon-button" onClick={onClose} aria-label="Close notification"><X size={16} /></button>; }

export function SuccessMessage({ children }) { return <div className="success-message"><CheckCircle2 size={17} />{children}</div>; }
