import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Activity, Radio } from 'lucide-react';
import './AdminMonitoringPage.css';

export const AdminMonitoringPage: React.FC = () => {
  const { candidateId } = useParams<{ candidateId: string }>();
  const [candidateImage, setCandidateImage] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [status, setStatus] = useState<string>('Connecting...');
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  
  useEffect(() => {
    if (!candidateId) return;
    
    setStatus('Waiting for secure feed...');
    const ws = new WebSocket(`ws://localhost:8000/admin/ws/interview/${candidateId}`);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.image) {
          setCandidateImage(data.image);
          setStatus('Connected');
        }
        if (data.audio_level !== undefined) {
          // Normalize audio level for visual display (0-100%)
          const level = Math.min(100, data.audio_level * 500); 
          setAudioLevel(level);
        }
        if (data.start_time) {
          setStartTime(data.start_time);
        }
        if (data.end_time) {
          setEndTime(data.end_time);
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
    <div className="admin-monitoring-container">
      <header className="monitoring-header">
        <h1>Monitoring Session: <span className="session-id">{candidateId}</span></h1>
        <div className="session-times">
          {startTime && <span className="time-badge start">Started: {new Date(startTime).toLocaleTimeString()}</span>}
          {endTime && <span className="time-badge end">Ended: {new Date(endTime).toLocaleTimeString()}</span>}
        </div>
      </header>

      <div className="monitoring-content">
        <div className="video-feed-card">
          {candidateImage ? (
            <img src={candidateImage} alt="Candidate Feed" className="candidate-video-stream" />
          ) : (
            <div className="video-placeholder">
              <Radio size={48} className="radar-icon" />
              <p>{status}</p>
            </div>
          )}
        </div>

        <div className="audio-wavelength-card">
          <div className="card-header">
            <Activity size={16} /> CANDIDATE AUDIO WAVELENGTH
          </div>
          <div className="audio-visualizer">
            <div 
              className="audio-bar" 
              style={{ width: `${audioLevel}%`, opacity: audioLevel > 5 ? 1 : 0.3 }}
            ></div>
          </div>
        </div>
        
        <div className="actions-card">
          <button 
            className="btn-primary w-full"
            onClick={() => window.open(`http://localhost:8000/admin/report/${candidateId}/pdf`, '_blank')}
          >
            Print PDF Report
          </button>
        </div>
      </div>
    </div>
  );
};
