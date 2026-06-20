import { useEffect, useRef, useState } from 'react';

export function useWebRTC(candidateId: string) {
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isStarted, setIsStarted] = useState(false);
  const [status, setStatus] = useState<string>('idle');

  // Initialize hidden audio element for remote AI voice
  useEffect(() => {
    const audio = new Audio();
    audio.autoplay = true;
    audioRef.current = audio;
  }, []);

  const startInterview = async () => {
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

      setIsStarted(true);
      setStatus('connected');
    } catch (err) {
      console.error('Failed to start WebRTC', err);
      setStatus('error');
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
  };

  useEffect(() => {
    return () => {
      stopInterview();
    };
  }, []);

  return { localVideoRef, isStarted, status, startInterview, stopInterview };
}
