/**
 * Core interview engine: camera, audio analysis, WebSocket, and phase management.
 */

const INTERVIEW_DURATION = parseInt('{{ interview_duration_minutes }}') || 30;
const TOTAL_ATTEMPTS = parseInt('{{ total_user_attempt }}') || 1;

const State = {
    localStream: null,
    audioContext: null,
    analyser: null,
    ws: null,
    timerInterval: null,
    remainingSeconds: INTERVIEW_DURATION * 60,
    attemptsUsed: 0,
    violationsLog: [],
    currentPhase: 'preview',
    candidateId: window.location.pathname.split('/').pop() || 'candidate_123',
};

/* ─── DOM References ─── */
const $ = (id) => document.getElementById(id);
const video = $('webcam');
const canvas = $('buffer');
const ctx = canvas.getContext('2d');

/* ─── Theme Toggle ─── */
function initTheme() {
    const saved = localStorage.getItem('interview-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('interview-theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = $('theme-btn');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

/* ─── Phase Management ─── */
function showPhase(phase) {
    document.querySelectorAll('.phase').forEach(el => el.classList.remove('active'));
    const target = $(`phase-${phase}`);
    if (target) target.classList.add('active');
    State.currentPhase = phase;
}

/* ─── Camera & Mic Setup ─── */
async function initCamera() {
    // Request video and audio separately to avoid total failure if one device is missing
    try {
        const videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
        State.localStream = videoStream;
        video.srcObject = videoStream;
        updateEnvCheck('camera', true);
        updateEnvStatus('env-camera', 'Good', 'ok');
    } catch (err) {
        console.error('[Camera] Failed to access webcam:', err);
        updateEnvCheck('camera', false);
        updateEnvStatus('env-camera', 'Failed', 'error');
    }

    try {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Merge audio track into the main stream
        if (State.localStream) {
            audioStream.getAudioTracks().forEach(t => State.localStream.addTrack(t));
        } else {
            State.localStream = audioStream;
        }
        initAudioMeter(State.localStream);
        updateEnvCheck('mic', true);
    } catch (err) {
        console.error('[Audio] Failed to access microphone:', err);
        updateEnvCheck('mic', false);
        updateEnvStatus('env-voice', 'Unavailable', 'error');
    }

    checkPreviewReady();
}

function updateEnvStatus(id, text, cls) {
    const el = $(id);
    if (el) { el.textContent = text; el.className = 'env-status ' + cls; }
}

function initAudioMeter(stream) {
    State.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = State.audioContext.createMediaStreamSource(stream);
    State.analyser = State.audioContext.createAnalyser();
    State.analyser.fftSize = 256;
    source.connect(State.analyser);

    const dataArray = new Uint8Array(State.analyser.frequencyBinCount);
    const meterFill = $('audio-meter-fill');
    const voiceStatus = $('env-voice');

    setInterval(() => {
        if (!State.analyser) return;
        State.analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const pct = Math.min((avg / 80) * 100, 100);

        if (meterFill) meterFill.style.width = pct + '%';
        if (voiceStatus) {
            if (avg > 2 && avg < 15) {
                voiceStatus.textContent = 'Too Soft';
                voiceStatus.className = 'env-status warn';
            } else if (avg >= 15) {
                voiceStatus.textContent = 'Good';
                voiceStatus.className = 'env-status ok';
            } else {
                voiceStatus.textContent = 'Silent';
                voiceStatus.className = 'env-status warn';
            }
        }
    }, 300);
}

function checkBrightness() {
    if (!State.localStream) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let sum = 0;
    for (let i = 0; i < imageData.data.length; i += 4) {
        sum += (imageData.data[i] + imageData.data[i + 1] + imageData.data[i + 2]) / 3;
    }
    const avg = sum / (imageData.data.length / 4);
    const lightStatus = $('env-light');
    const overlay = $('bad-light-overlay');

    if (avg > 75) {
        if (lightStatus) { lightStatus.textContent = 'Good'; lightStatus.className = 'env-status ok'; }
        if (overlay) overlay.style.display = 'none';
        updateEnvCheck('light', true);
    } else {
        if (lightStatus) { lightStatus.textContent = 'Too Dark'; lightStatus.className = 'env-status error'; }
        if (overlay) overlay.style.display = 'flex';
        updateEnvCheck('light', false);
    }
}

function updateEnvCheck(type, ok) {
    const el = $(`check-${type}`);
    if (el) el.textContent = ok ? '✅' : '❌';
    checkPreviewReady();
}

function checkPreviewReady() {
    const btn = $('btn-start');
    if (btn) btn.disabled = !State.localStream;
}

/* ─── WebSocket ─── */
function connectWebSocket() {
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    State.ws = new WebSocket(`${scheme}//${window.location.host}/ws/interview/${State.candidateId}`);

    State.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateInterviewStatus(data);

        if (data.action === 'warn' || data.action === 'terminate') {
            State.violationsLog.push({
                timestamp: new Date().toISOString(),
                type: 'gaze_deviation',
                strike: data.current_strikes,
                quality: data.video_quality,
            });
        }

        if (data.action === 'terminate') {
            endInterview('terminated');
        }
    };

    State.ws.onerror = () => console.warn('[WS] Connection error');
}

function updateInterviewStatus(data) {
    const lightVal = $('live-light');
    const gazeVal = $('live-gaze');
    if (lightVal) {
        lightVal.textContent = data.video_quality;
        lightVal.className = 'status-val ' + (data.video_quality === 'Good' ? 'ok' : 'danger');
    }
    if (gazeVal) {
        const focused = data.action !== 'warn' && data.action !== 'terminate';
        gazeVal.textContent = focused ? 'Focused' : 'Looking Away';
        gazeVal.className = 'status-val ' + (focused ? 'ok' : 'danger');
    }
}

/* ─── Frame Streaming ─── */
let frameInterval = null;

function startFrameStreaming() {
    frameInterval = setInterval(() => {
        if (State.ws?.readyState === WebSocket.OPEN && State.localStream) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.4);
            State.ws.send(JSON.stringify({ image: dataUrl }));
        }
    }, 400);
}

function stopFrameStreaming() {
    if (frameInterval) { clearInterval(frameInterval); frameInterval = null; }
}
