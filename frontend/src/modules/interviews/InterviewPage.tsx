import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useWebRTC } from './hooks/useWebRTC';
import { Video, VideoOff, Mic, Clock, Send, Save } from 'lucide-react';
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
    isAudioEnabled,
    startTime,
    endTime,
    startInterview, 
    submitAnswer,
    finalizeSession
  } = useWebRTC(candidateId || 'default');

  const [timeLeft, setTimeLeft] = useState(QUESTION_TIME_LIMIT);
  const [isAnswering, setIsAnswering] = useState(false);

  // Timer logic
  useEffect(() => {
    let timer: NodeJS.Timeout;
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

  return (
    <div className="interview-container">
      <header className="interview-header">
        <h1 className="title-gradient">Interview AI</h1>
        <div className="status-badges flex gap-4 items-center">
          {startTime && <span className="text-sm text-slate-400">Started: {new Date(startTime).toLocaleTimeString()}</span>}
          {endTime && <span className="text-sm text-slate-400">Ended: {new Date(endTime).toLocaleTimeString()}</span>}
          <span className={`status-badge ${status}`}>
            {status.toUpperCase()}
          </span>
          {isStarted && (
            <button onClick={finalizeSession} className="btn-danger flex items-center gap-2 px-4 py-2">
              <Save size={16} /> Finalize Interview
            </button>
          )}
        </div>
      </header>

      <div className="interview-layout-structured">
        {/* Left Side: Cameras & Avatars */}
        <div className="sidebar-cameras">
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
          
          <div className="video-wrapper small bg-slate-900 flex items-center justify-center overflow-hidden">
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

          <div className="controls mt-4 w-full">
            {!isStarted && (
              <button onClick={startInterview} className="btn-primary w-full justify-center">
                <Video size={20} /> Start Session
              </button>
            )}
          </div>
        </div>

        {/* Center: Question Panel */}
        <div className="main-question-panel">
          {isStarted ? (
            <div className="question-card">
              <div className="question-header">
                <h2 className="text-xl font-bold flex items-center gap-2 text-slate-200">
                  <Mic size={24} className="text-blue-400" />
                  {agentMessage?.current_topic || "Initializing..."}
                </h2>
                
                {isAnswering && (
                  <div className={`timer-display ${timeLeft < 30 ? 'text-red-400' : 'text-slate-300'}`}>
                    <Clock size={20} />
                    <span className="font-mono text-2xl">{formatTime(timeLeft)}</span>
                  </div>
                )}
              </div>

              <div className="question-body my-8 p-6 bg-slate-800 rounded-lg border border-slate-700 min-h-[200px] flex items-center justify-center">
                <p className="text-2xl text-center leading-relaxed text-slate-100">
                  {agentMessage?.text_to_speak || "Please wait while the AI Interviewer analyzes your profile..."}
                </p>
              </div>

              {agentMessage?.interview_complete ? (
                <div className="text-center">
                  <h3 className="text-green-400 text-xl font-bold mb-4">Interview Complete</h3>
                  <button onClick={finalizeSession} className="btn-primary px-8 py-3 text-lg">
                    Submit & Finalize
                  </button>
                </div>
              ) : (
                <div className="question-footer flex justify-end">
                  <button 
                    onClick={handleSubmit} 
                    disabled={!isAnswering}
                    className={`btn-primary flex items-center gap-2 px-8 py-3 text-lg ${!isAnswering ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <Send size={20} /> Submit Answer
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500">
              <p className="text-xl">Click "Start Session" to begin the interview.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
