import { useEffect, useRef, useState } from 'react';

export function useWebRTC(candidateId: string) {
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isStarted, setIsStarted] = useState(false);
  const [status, setStatus] = useState<string>('idle');
  const [agentMessage, setAgentMessage] = useState<any>(null);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);

  // Initialize hidden audio element for remote AI voice
  useEffect(() => {
    const audio = new Audio();
    audio.autoplay = true;
    audioRef.current = audio;
  }, []);

  const toggleAudio = () => {
    if (audioRef.current) {
      audioRef.current.muted = !audioRef.current.muted;
      setIsAudioEnabled(!audioRef.current.muted);
    }
  };

  const connectEarly = async () => {
    try {
      setStatus('connecting');
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true, // Capture candidate's voice
      });
      setStream(mediaStream);

      if (localVideoRef.current) {
        localVideoRef.current.srcObject = mediaStream;
      }

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      // Create data channel to receive text_to_speak from backend
      const dataChannel = pc.createDataChannel('agent_text');
      dataChannelRef.current = dataChannel;
      
      dataChannel.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setAgentMessage(data);
        } catch (e) {
          console.error("Failed to parse datachannel message", e);
        }
      };

      // Handle incoming AI voice track
      pc.ontrack = (event) => {
        if (event.track.kind === 'audio' && audioRef.current) {
          audioRef.current.srcObject = event.streams[0];
        }
      };

      mediaStream.getTracks().forEach((track) => {
        pc.addTrack(track, mediaStream);
      });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const response = await fetch(`http://localhost:8000/interview/${candidateId}/offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sdp: pc.localDescription?.sdp,
          type: pc.localDescription?.type,
        }),
      });

      const answer = await response.json();
      await pc.setRemoteDescription(answer);

      setStatus('connected');
    } catch (err) {
      console.error('Failed to start WebRTC', err);
      setStatus('error');
    }
  };

  useEffect(() => {
    connectEarly();
    return () => {
      stopInterview();
    };
  }, [candidateId]);

  const startInterview = async () => {
    try {
      const res = await fetch(`http://localhost:8000/interview/${candidateId}/start`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.start_time) {
        setStartTime(data.start_time);
      }
      setIsStarted(true);
      setStatus('active');
    } catch (err) {
      console.error('Failed to start interview', err);
    }
  };

  const stopInterview = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }
    setIsStarted(false);
    setStatus('stopped');
    setAgentMessage(null);
  };

  const submitAnswer = async () => {
    try {
      await fetch(`http://localhost:8000/interview/${candidateId}/submit`, {
        method: 'POST'
      });
    } catch (err) {
      console.error('Failed to submit answer', err);
    }
  };

  const finalizeSession = async () => {
    try {
      const res = await fetch(`http://localhost:8000/interview/${candidateId}/finalize`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.end_time) {
        setEndTime(data.end_time);
      }
      stopInterview();
      setStatus('completed');
    } catch (err) {
      console.error('Failed to finalize session', err);
    }
  };



  return { 
    localVideoRef, 
    isStarted, 
    status, 
    agentMessage,
    isAudioEnabled,
    startTime,
    endTime,
    startInterview, 
    stopInterview,
    toggleAudio,
    submitAnswer,
    finalizeSession
  };
}
