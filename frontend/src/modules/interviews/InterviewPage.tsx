import React from 'react';
import { useParams } from 'react-router-dom';
import { useWebRTC } from './hooks/useWebRTC';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Video, VideoOff, AlertCircle, Mic, CheckCircle } from 'lucide-react';
import './InterviewPage.css';

const mockData = [
  { time: '0:00', stress: 10, engagement: 90 },
  { time: '5:00', stress: 20, engagement: 85 },
  { time: '10:00', stress: 40, engagement: 60 },
  { time: '15:00', stress: 15, engagement: 95 },
];

const TOPICS = [
  "Experience with FastAPI and Async Python.",
  "System design concepts (Caching with Redis, Databases with MongoDB).",
  "Handling real-time streaming data pipelines."
];

export const InterviewPage: React.FC = () => {
  const { candidateId } = useParams<{ candidateId: string }>();
  const { localVideoRef, isStarted, status, startInterview, stopInterview } = useWebRTC(candidateId || 'default');

  return (
    <div className="interview-container">
      <div className="interview-layout">
        
        <header className="interview-header">
          <h1 className="title-gradient">Interview Console</h1>
          <div className="status-badges">
            <span className={`status-badge ${status}`}>
              {status.toUpperCase()}
            </span>
          </div>
        </header>

        <div className="interview-grid">
          <div className="video-section">
            <div className="video-wrapper">
              <video
                ref={localVideoRef}
                autoPlay
                playsInline
                muted
                className={`video-element ${!isStarted ? 'hidden' : ''}`}
              />
              {!isStarted && (
                <div className="video-placeholder">
                  <VideoOff size={48} />
                  <p>Camera is currently off</p>
                </div>
              )}
            </div>

            <div className="controls">
              {!isStarted ? (
                <button onClick={startInterview} className="btn-primary">
                  <Video size={20} /> Start Session
                </button>
              ) : (
                <button onClick={stopInterview} className="btn-danger">
                  <VideoOff size={20} /> End Session
                </button>
              )}
            </div>

            {isStarted && (
              <div className="card mt-4">
                <h2 className="card-title">
                  <Mic size={20} className="text-blue-400" />
                  AI Interviewer Active
                </h2>
                <p className="text-sm text-slate-400 mt-2">
                  The AI is listening and will speak dynamically. Please ensure your volume is up.
                </p>
              </div>
            )}
          </div>

          <div className="sidebar-section">
            <div className="card">
              <h2 className="card-title">
                Required Topics Checklist
              </h2>
              <ul className="topics-list">
                {TOPICS.map((topic, idx) => (
                  <li key={idx} className="topic-item">
                    <CheckCircle size={16} className="topic-icon-pending" />
                    <span className="text-sm">{topic}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="card">
              <h2 className="card-title">
                <AlertCircle className="icon-warning" size={20} />
                Live Metrics
              </h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={mockData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="time" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#fff' }} />
                    <Line type="monotone" dataKey="engagement" stroke="#34d399" strokeWidth={3} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="stress" stroke="#f87171" strokeWidth={3} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
