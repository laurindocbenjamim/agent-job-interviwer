import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Activity, Clock, FileText, CheckCircle2, Copy } from 'lucide-react';
import './AdminMonitoringPage.css';

export const AdminMonitoringPage: React.FC = () => {
  const { candidateId } = useParams<{ candidateId: string }>();
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [status, setStatus] = useState<string>('Connecting...');
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  
  useEffect(() => {
    if (!candidateId) return;
    
    setStatus('Establishing secure connection...');
    const ws = new WebSocket(`ws://localhost:8000/admin/ws/interview/${candidateId}`);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.audio_level !== undefined) {
          // Normalize audio level for visual display (0-100%)
          const level = Math.min(100, data.audio_level * 500); 
          setAudioLevel(level);
          setStatus('Connected & Monitoring');
        }
        if (data.start_time) {
          setStartTime(data.start_time);
        }
        if (data.end_time) {
          setEndTime(data.end_time);
          setStatus('Session Completed');
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };
    
    ws.onclose = () => {
      setStatus('Disconnected');
    };
    
    return () => {
      ws.close();
    };
  }, [candidateId]);

  return (
    <div className="admin-container fade-in">
      <header className="monitoring-header glass-panel">
        <div className="header-content">
          <h1>Session Monitoring</h1>
          <div className="session-id-badge" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            ID: <input 
              type="text" 
              readOnly 
              value={candidateId || ''} 
              style={{ background: 'transparent', border: 'none', color: 'inherit', outline: 'none', width: '150px', cursor: 'text' }}
            />
            <button 
              onClick={() => navigator.clipboard.writeText(candidateId || '')} 
              style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex' }}
              title="Copy ID"
            >
              <Copy size={16} className="text-accent" />
            </button>
          </div>
        </div>
        <div className="session-times">
          <div className="status-indicator">
            <span className={`status-dot ${status === 'Connected & Monitoring' ? 'active' : ''}`}></span>
            {status}
          </div>
          {startTime && (
            <div className="time-badge">
              <Clock size={16} /> 
              <span>Started: {new Date(startTime).toLocaleTimeString()}</span>
            </div>
          )}
          {endTime && (
            <div className="time-badge end">
              <CheckCircle2 size={16} />
              <span>Ended: {new Date(endTime).toLocaleTimeString()}</span>
            </div>
          )}
        </div>
      </header>

      <div className="monitoring-grid">
        <div className="monitoring-card glass-panel audio-card">
          <div className="card-header">
            <h3><Activity size={20} className="text-accent" /> Candidate Audio Wavelength</h3>
          </div>
          <div className="audio-visualizer-container">
            <div className="audio-level-text">{Math.round(audioLevel)}%</div>
            <div className="audio-visualizer">
              <div 
                className="audio-bar" 
                style={{ 
                  height: `${Math.max(4, audioLevel)}%`, 
                  opacity: audioLevel > 5 ? 1 : 0.5 
                }}
              ></div>
            </div>
          </div>
        </div>
        
        <div className="monitoring-card glass-panel action-card">
          <div className="card-header">
            <h3><FileText size={20} className="text-accent" /> Actions & Reports</h3>
          </div>
          <div className="card-body centered">
            <p className="action-desc">Generate a comprehensive summary report of the candidate's performance after the interview is complete.</p>
            <button 
              className="btn-primary w-full mt-4"
              onClick={() => window.open(`http://localhost:8000/admin/report/${candidateId}/pdf`, '_blank')}
            >
              <FileText size={18} /> Print PDF Report
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
