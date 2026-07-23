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
import QuestionAnalysisPage from './pages/QuestionAnalysisPage';
import StudentPerformancePage from './pages/StudentPerformancePage';
import HistoryPage from './pages/HistoryPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import QAMappingPage from './pages/QAMappingPage';
import EvaluationRunPage from './pages/EvaluationRunPage';
import MarksMatrixPage from './pages/MarksMatrixPage';

export default function App() {
  const [apiKey, setApiKey] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Router>
      <div className="app-shell">
        <Toaster position="top-right" toastOptions={{ className: 'app-toast' }} />
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="app-main">
          <Header onMenu={() => setSidebarOpen(true)} />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/answer-sheets" element={<AnswerSheetPage apiKey={apiKey} />} />
              <Route path="/evaluate-papers" element={<AnswerSheetPage apiKey={apiKey} />} />
              <Route path="/question-papers" element={<QuestionPaperPage apiKey={apiKey} />} />
              <Route path="/manual-review" element={<ManualReviewPage apiKey={apiKey} />} />
              <Route path="/blueprints" element={<BlueprintPage apiKey={apiKey} />} />
              <Route path="/academic-master" element={<AcademicMasterPage apiKey={apiKey} />} />
              <Route path="/ocr-results" element={<AnswerSheetPage apiKey={apiKey} />} />
              <Route path="/question-analysis" element={<QuestionAnalysisPage apiKey={apiKey} />} />
              <Route path="/student-performance" element={<StudentPerformancePage apiKey={apiKey} />} />
              <Route path="/history" element={<HistoryPage apiKey={apiKey} />} />
              <Route path="/reports" element={<ReportsPage apiKey={apiKey} />} />
              <Route path="/settings" element={<SettingsPage apiKey={apiKey} />} />
              <Route path="/qa-mapping" element={<QAMappingPage apiKey={apiKey} />} />
              <Route path="/evaluate" element={<EvaluationRunPage apiKey={apiKey} />} />
              <Route path="/results-matrix" element={<MarksMatrixPage apiKey={apiKey} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </div>
    </Router>
  );
}
