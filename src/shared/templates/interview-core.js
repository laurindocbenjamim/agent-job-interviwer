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
    isFinished: false,
    speechTimeout: null,
    startTime: null,
    endTime: null,
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
async function getConnectedDevices() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoCameras = devices.filter(device => device.kind === 'videoinput');
        const select = $('camera-select');
        if (select && videoCameras.length > 0) {
            select.innerHTML = '';
            videoCameras.forEach(camera => {
                const option = document.createElement('option');
                option.value = camera.deviceId;
                option.text = camera.label || `Camera ${select.length + 1}`;
                select.appendChild(option);
            });
            select.onchange = () => {
                if (State.localStream) {
                    State.localStream.getVideoTracks().forEach(track => track.stop());
                }
                initCamera(select.value);
            };
        }
    } catch (e) {
        console.error("Error enumerating devices:", e);
    }
}

async function initCamera(deviceId = null) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error("Browser API navigator.mediaDevices.getUserMedia not available.");
        updateEnvStatus('env-camera', 'Unavailable', 'error');
        updateEnvStatus('env-voice', 'Unavailable', 'error');
        return;
    }

    try {
        const videoConstraints = deviceId ? { deviceId: { exact: deviceId } } : true;
        
        // Request both video and audio in a single prompt to ensure the popup shows correctly
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: videoConstraints, 
            audio: true 
        });
        
        State.localStream = stream;
        video.srcObject = stream;
        
        updateEnvCheck('camera', true);
        updateEnvStatus('env-camera', 'Good', 'ok');
        
        initAudioMeter(stream);
        updateEnvCheck('mic', true);
        
        // Populate dropdown on first load after permissions are granted
        if (!deviceId) getConnectedDevices();
        
    } catch (err) {
        console.error('[Camera/Mic] Failed to access devices:', err);
        updateEnvCheck('camera', false);
        updateEnvStatus('env-camera', 'Failed (Check Permissions)', 'error');
        updateEnvCheck('mic', false);
        updateEnvStatus('env-voice', 'Failed', 'error');
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

    // Global tracking flag for speech detection
    State.hasSpoken = false;

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
                State.hasSpoken = true; // User actually spoke!
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
    const isActive = '{{ is_active }}' === 'True';
    if (btn) btn.disabled = !State.localStream || !isActive;
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

/* ─── Web Speech API & 3D Avatar (Three-VRM) ─── */
let currentVrm = null;
let currentMixer = null;
const clock = new THREE.Clock();
let isSpeaking = false;
let blinkInterval = null;

function initAvatar() {
    const container = $('avatar-canvas');
    if (!container) return;

    const renderer = new THREE.WebGLRenderer({ canvas: container, alpha: true, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);

    const camera = new THREE.PerspectiveCamera(30.0, container.clientWidth / container.clientHeight, 0.1, 20.0);
    camera.position.set(0.0, 1.45, 1.5);

    const scene = new THREE.Scene();

    const light = new THREE.DirectionalLight(0xffffff, 1.0);
    light.position.set(1.0, 1.0, 1.0).normalize();
    scene.add(light);
    
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const loader = new THREE.GLTFLoader();
    
    // Choose model based on gender variable passed from Jinja
    const gender = '{{ avatar_gender }}';
    let modelUrl = 'https://models.readyplayer.me/64b58e7b9f36f6d6fc3a6566.glb'; // Default Female
    if (gender === 'male') {
        modelUrl = 'https://models.readyplayer.me/64b58e7b9f36f6d6fc3a6565.glb'; // Default Male
    }

    loader.load(
        modelUrl,
        (gltf) => {
            $('avatar-loading').style.display = 'none';
            THREE.VRMUtils.removeUnnecessaryJoints(gltf.scene);

            THREE.VRM.from(gltf).then((vrm) => {
                currentVrm = vrm;
                scene.add(vrm.scene);
                
                vrm.scene.rotation.y = Math.PI;
                
                blinkInterval = setInterval(() => {
                    if (currentVrm) {
                        currentVrm.blendShapeProxy.setValue(THREE.VRMBlendShapePresetName.Blink, 1.0);
                        setTimeout(() => {
                            if (currentVrm) currentVrm.blendShapeProxy.setValue(THREE.VRMBlendShapePresetName.Blink, 0.0);
                        }, 100);
                    }
                }, 4000);
            });
        },
        (progress) => console.log('Loading avatar...', 100.0 * (progress.loaded / progress.total), '%'),
        (error) => {
            console.error('[Avatar Load Error]', error);
            const loadingEl = $('avatar-loading');
            if (loadingEl) {
                loadingEl.textContent = 'AI Avatar Offline (Voice Mode Active)';
                loadingEl.style.color = 'var(--text-muted)';
            }
        }
    );

    function animate() {
        requestAnimationFrame(animate);
        const deltaTime = clock.getDelta();
        
        if (currentVrm) {
            currentVrm.update(deltaTime);
            
            if (isSpeaking) {
                const s = Math.sin(clock.elapsedTime * 15);
                const val = (s + 1) / 2 * 0.8;
                currentVrm.blendShapeProxy.setValue(THREE.VRMBlendShapePresetName.A, val);
            } else {
                currentVrm.blendShapeProxy.setValue(THREE.VRMBlendShapePresetName.A, 0.0);
            }
        }
        
        if (currentMixer) {
            currentMixer.update(deltaTime);
        }
        
        renderer.render(scene, camera);
    }
    animate();
}

function playAgentSpeech(text, onEndCallback) {
    if (State.isFinished) {
        isSpeaking = false;
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        return;
    }
    const audioToggle = $('audio-toggle-switch');
    isSpeaking = true;

    if (audioToggle && audioToggle.checked) {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice = voices.find(v => v.lang.includes('en-US') && v.name.includes('Google')) || voices.find(v => v.lang.includes('en'));
            if (preferredVoice) utterance.voice = preferredVoice;
            
            // Set speed from env variable
            const speedVar = parseFloat('{{ agent_speech_speed }}');
            utterance.rate = isNaN(speedVar) ? 1.0 : speedVar;
            utterance.pitch = 1.0;
            
            utterance.onend = () => {
                isSpeaking = false;
                if (State.isFinished) return;
                if (onEndCallback) onEndCallback();
            };
            
            window.speechSynthesis.speak(utterance);
        } else {
            console.warn("Web Speech API not supported.");
            State.speechTimeout = setTimeout(() => {
                isSpeaking = false;
                if (State.isFinished) return;
                if (onEndCallback) onEndCallback();
            }, text.length * 50);
        }
    } else {
        const durationMs = Math.max(2000, (text.split(' ').length / 2.5) * 1000);
        State.speechTimeout = setTimeout(() => {
            isSpeaking = false;
            if (State.isFinished) return;
            if (onEndCallback) onEndCallback();
        }, durationMs);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = () => { window.speechSynthesis.getVoices(); };
    }
    setTimeout(initAvatar, 500);
});
