import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { InterviewPage } from './modules/interviews/InterviewPage';
import { AdminVoicePage } from './modules/admin/AdminVoicePage';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/admin/voice" element={<AdminVoicePage />} />
        <Route path="/interview/:candidateId" element={<InterviewPage />} />
        <Route path="*" element={<Navigate to="/interview/default_candidate" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
