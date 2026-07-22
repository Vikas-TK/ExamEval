import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Header from './components/Header';
import Footer from './components/Footer';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import AnswerSheetPage from './pages/AnswerSheetPage';
import QuestionPaperPage from './pages/QuestionPaperPage';
import AcademicMasterPage from './pages/AcademicMasterPage';
import ManualReviewPage from './pages/ManualReviewPage';
import BlueprintPage from './pages/BlueprintPage';

export default function App() {
  const [apiKey, setApiKey] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Router>
      <div className="app-shell">
        <Toaster position="top-right" toastOptions={{ className: 'app-toast' }} />
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="app-main"><Header onMenu={() => setSidebarOpen(true)} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/answer-sheets" element={<AnswerSheetPage apiKey={apiKey} />} />
            <Route path="/question-papers" element={<QuestionPaperPage apiKey={apiKey} />} />
            <Route path="/manual-review" element={<ManualReviewPage apiKey={apiKey} />} />
            <Route path="/blueprints" element={<BlueprintPage apiKey={apiKey} />} />
            <Route path="/academic-master" element={<AcademicMasterPage apiKey={apiKey} />} />
            <Route path="/ocr-results" element={<AnswerSheetPage apiKey={apiKey} />} />
            <Route path="/reports" element={<PlaceholderPage title="Reports" description="Reporting dashboards are coming soon." />} />
            <Route path="/settings" element={<PlaceholderPage title="Settings" description="Workspace settings will be available here." />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <Footer /></div>
      </div>
    </Router>
  );
}

function PlaceholderPage({ title, description }) {
  return <div className="page-container"><div className="placeholder-page"><h1>{title}</h1><p>{description}</p></div></div>;
}
