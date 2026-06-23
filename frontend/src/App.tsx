import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { InterviewPage } from './modules/interviews/InterviewPage';
import { AdminPage } from './modules/admin/AdminPage';
import { AdminMonitoringPage } from './modules/admin/AdminMonitoringPage';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/admin/voice" element={<AdminPage />} />
        <Route path="/admin/monitoring/:candidateId" element={<AdminMonitoringPage />} />
        <Route path="/interview/:candidateId" element={<InterviewPage />} />
        <Route path="*" element={<Navigate to="/interview/default_candidate" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
