import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useWebRTC } from './hooks/useWebRTC';
import { Video, VideoOff, Mic, Clock, Send, Save, Activity, CheckCircle2 } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import { AgentAvatar } from './components/AgentAvatar';
import './InterviewPage.css';

const QUESTION_TIME_LIMIT = 120; // Seconds

export const InterviewPage: React.FC = () => {
  const { candidateId } = useParams<{ candidateId: string }>();
  const { 
    localVideoRef, 
    isStarted, 
    status, 
    startTime,
    endTime,
    startInterview, 
    submitAnswer,
    finalizeSession,
    agentMessage
  } = useWebRTC(candidateId || 'default');

  const [timeLeft, setTimeLeft] = useState(QUESTION_TIME_LIMIT);
  const [isAnswering, setIsAnswering] = useState(false);

  // Timer logic
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (isStarted && isAnswering && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
    } else if (timeLeft === 0 && isAnswering) {
      handleSubmit();
    }
    return () => clearInterval(timer);
  }, [isStarted, isAnswering, timeLeft]);

  // When a new question arrives, start the timer
  useEffect(() => {
    if (agentMessage && agentMessage.text_to_speak) {
      if (agentMessage.interview_complete) {
        setIsAnswering(false);
      } else {
        setTimeLeft(QUESTION_TIME_LIMIT);
        setIsAnswering(true);
      }
    }
  }, [agentMessage]);

  const handleSubmit = () => {
    setIsAnswering(false);
    submitAnswer();
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  // Enforce light theme for this page
  useEffect(() => {
    const originalTheme = document.documentElement.getAttribute('data-theme');
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.classList.add('force-white-bg');
    
    return () => {
      if (originalTheme) {
        document.documentElement.setAttribute('data-theme', originalTheme);
      } else {
        document.documentElement.removeAttribute('data-theme');
      }
      document.body.classList.remove('force-white-bg');
    };
  }, []);

  return (
    <div className="interview-container">
      <header className="interview-header">
        <div className="logo-container">
          <div className="logo-icon-small">K</div>
          <h1 className="title-gradient">KIMET.AI Interview</h1>
        </div>
        <div className="status-badges flex gap-4 items-center">
          {startTime && <span className="text-sm text-slate-500">Started: {new Date(startTime).toLocaleTimeString()}</span>}
          {endTime && <span className="text-sm text-slate-500">Ended: {new Date(endTime).toLocaleTimeString()}</span>}
          <span className={`status-badge ${status.toLowerCase()}`}>
            <Activity size={14} className="pulse-icon" />
            {status.toUpperCase()}
          </span>
          {isStarted && !agentMessage?.interview_complete && (
            <button onClick={finalizeSession} className="btn-danger flex items-center gap-2 px-4 py-2">
              <Save size={16} /> Finalize Interview
            </button>
          )}
        </div>
      </header>

      <div className="interview-layout-structured">
        {/* Left Side: Cameras & Avatars */}
        <div className="sidebar-cameras">
          <div className="camera-card glass-panel">
            <h3 className="camera-title">Your Feed</h3>
            <div className="video-wrapper small">
              <video
                ref={localVideoRef}
                autoPlay
                playsInline
                muted
                className={`video-element ${!isStarted ? 'hidden' : ''}`}
              />
              {!isStarted && (
                <div className="video-placeholder">
                  <VideoOff size={32} />
                  <p>Camera Off</p>
                </div>
              )}
            </div>
            
            {!isStarted && (
              <div className="controls mt-4 w-full">
                <button onClick={startInterview} className="btn-primary w-full justify-center">
                  <Video size={20} /> Start Session
                </button>
              </div>
            )}
          </div>
          
          <div className="camera-card glass-panel">
            <h3 className="camera-title">AI Interviewer</h3>
            <div className="video-wrapper small ai-wrapper overflow-hidden">
              {!isStarted ? (
                <div className="video-placeholder">
                  <p>AI Offline</p>
                </div>
              ) : (
                <Canvas camera={{ position: [0, 0, 3], fov: 40 }}>
                  <ambientLight intensity={0.5} />
                  <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} />
                  <Environment preset="city" />
                  <AgentAvatar agentMessage={agentMessage} />
                  <OrbitControls enableZoom={false} enablePan={false} minPolarAngle={Math.PI / 2} maxPolarAngle={Math.PI / 2} />
                </Canvas>
              )}
            </div>
          </div>
        </div>

        {/* Center: Question Panel */}
        <div className="main-question-panel">
          {isStarted ? (
            <div className="question-card glass-panel">
              <div className="question-header">
                <h2 className="topic-title">
                  <Mic size={24} className="text-accent" />
                  {agentMessage?.current_topic || "Initializing..."}
                </h2>
                
                {isAnswering && (
                  <div className={`timer-display ${timeLeft < 30 ? 'text-red-500' : 'text-slate-600'}`}>
                    <Clock size={20} />
                    <span className="font-mono text-2xl">{formatTime(timeLeft)}</span>
                  </div>
                )}
              </div>

              <div className="question-body">
                <p className="question-text">
                  {agentMessage?.text_to_speak || "Please wait while the AI Interviewer analyzes your profile..."}
                </p>
              </div>

              {agentMessage?.interview_complete ? (
                <div className="completion-area">
                  <div className="completion-icon">
                    <CheckCircle2 size={48} />
                  </div>
                  <h3>Interview Complete</h3>
                  <p>Thank you for your time. Your responses have been recorded.</p>
                  <button onClick={finalizeSession} className="btn-primary px-8 py-3 text-lg">
                    Submit & Return
                  </button>
                </div>
              ) : (
                <div className="question-footer flex justify-end">
                  <button 
                    onClick={handleSubmit} 
                    disabled={!isAnswering}
                    className={`btn-primary flex items-center gap-2 px-8 py-3 text-lg ${!isAnswering ? 'disabled' : ''}`}
                  >
                    <Send size={20} /> Submit Answer
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state glass-panel">
              <div className="empty-state-icon">
                <Video size={48} />
              </div>
              <h2>Ready for your interview?</h2>
              <p>Make sure you are in a quiet room with good lighting. Click "Start Session" when you are ready to begin.</p>
              <button onClick={startInterview} className="btn-primary mt-4">
                Start Session
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
