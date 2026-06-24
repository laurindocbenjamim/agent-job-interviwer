import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { InterviewPage } from './modules/interviews/InterviewPage';
import { AdminPage } from './modules/admin/AdminPage';
import { AdminMonitoringPage } from './modules/admin/AdminMonitoringPage';
import { AdminLayout } from './shared/components/AdminLayout';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route path="voice" element={<AdminPage />} />
          <Route path="monitoring/:candidateId" element={<AdminMonitoringPage />} />
          <Route index element={<Navigate to="/admin/voice" replace />} />
        </Route>
        <Route path="/interview/:candidateId" element={<InterviewPage />} />
        <Route path="*" element={<Navigate to="/interview/default_candidate" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
