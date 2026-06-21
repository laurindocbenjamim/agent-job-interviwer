/**
 * Interview actions: start, stop, timer, violations report, and attempt management.
 */

/* ─── Question Timer & Submission ─── */
let questionTimerInterval = null;
const QUESTION_LIMIT = parseInt('{{ question_time_limit_seconds }}') || 60;

function startQuestionTimer() {
    if (questionTimerInterval) clearInterval(questionTimerInterval);
    State.remainingSeconds = QUESTION_LIMIT;
    updateTimerDisplay();

    const btnSubmit = $('btn-submit-answer');
    if (btnSubmit) btnSubmit.disabled = false;

    questionTimerInterval = setInterval(() => {
        State.remainingSeconds--;
        updateTimerDisplay();
        if (State.remainingSeconds <= 0) {
            submitAnswer(true);
        }
    }, 1000);
}

function updateTimerDisplay() {
    const mins = Math.floor(State.remainingSeconds / 60);
    const secs = State.remainingSeconds % 60;
    const el = $('timer-value');
    if (el) {
        el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        el.className = State.remainingSeconds <= 60 ? 'timer-value warning' : 'timer-value';
    }
}

let currentInputType = 'voice';

async function submitAnswer(isAutoTimeout = false) {
    if (questionTimerInterval) clearInterval(questionTimerInterval);
    
    let answerText = "";
    const container = $('dynamic-input-container');

    // "No Speech" Detection Logic
    if (isAutoTimeout && currentInputType === 'voice') {
        if (!State.hasSpoken) {
            // User was completely silent during the time limit
            const textEl = $('agent-speech-text');
            if (textEl) textEl.textContent = "I can't hear you. Let's move to the next question.";
            if (typeof playAgentSpeech === 'function') {
                playAgentSpeech("I can't hear you. Let's move to the next question.", async () => {
                    await sendSubmit("[Candidate did not speak]");
                });
            } else {
                await sendSubmit("[Candidate did not speak]");
            }
            return;
        } else {
            answerText = "[Candidate answered via voice]";
        }
    } else {
        // Collect answer based on input type
        if (currentInputType === 'text') {
            const textarea = container.querySelector('textarea');
            if (textarea) answerText = textarea.value;
        } else if (currentInputType === 'multiple_choice') {
            const selected = container.querySelector('input[type="radio"]:checked');
            if (selected) answerText = selected.value;
        } else if (currentInputType === 'checkbox') {
            const checked = container.querySelectorAll('input[type="checkbox"]:checked');
            const vals = Array.from(checked).map(el => el.value);
            if (vals.length > 0) answerText = vals.join(', ');
        } else {
            answerText = "[Candidate answered via voice]";
        }
    }

    await sendSubmit(answerText);
}

async function sendSubmit(answerText) {
    const btnSubmit = $('btn-submit-answer');
    const speechText = $('agent-speech-text');
    if (btnSubmit) btnSubmit.disabled = true;
    if (speechText) speechText.textContent = "Analyzing answer and generating next question...";

    try {
        const response = await fetch(`/interview/${State.candidateId}/submit`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answer: answerText })
        });
        const data = await response.json();
        
        if (data.interview_complete) {
            endInterview('completed');
            return;
        }

        const topicEl = $('current-topic');
        if (topicEl) topicEl.textContent = data.current_topic || "Next Question";
        
        if (speechText) speechText.textContent = data.text_to_speak;

        renderDynamicInputs(data.input_type || 'voice', data.options || []);

        // Reset tracking variables
        State.hasSpoken = false;

        // Play audio via Web Speech API and animate avatar
        if (typeof playAgentSpeech === 'function') {
            playAgentSpeech(data.text_to_speak, () => {
                // Restart timer once agent finishes speaking
                startQuestionTimer();
            });
        } else {
            startQuestionTimer();
        }

    } catch (err) {
        console.error("Failed to submit answer:", err);
        if (speechText) speechText.textContent = "Connection error. Please try submitting again.";
        if (btnSubmit) btnSubmit.disabled = false;
    }
}

function renderDynamicInputs(inputType, options) {
    currentInputType = inputType;
    const container = $('dynamic-input-container');
    if (!container) return;
    
    container.innerHTML = ''; // Clear previous inputs
    
    const baseStyle = 'width: 100%; padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color); background: var(--bg-card); color: var(--text-primary); outline: none; font-size: 1.1rem;';

    if (inputType === 'text') {
        const textarea = document.createElement('textarea');
        textarea.rows = 4;
        textarea.placeholder = "Type your answer here...";
        textarea.style.cssText = baseStyle + ' resize: vertical;';
        container.appendChild(textarea);
    } 
    else if (inputType === 'multiple_choice') {
        options.forEach((opt, idx) => {
            const label = document.createElement('label');
            label.style.cssText = 'display: flex; align-items: center; gap: 0.75rem; padding: 1rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.5rem; cursor: pointer;';
            
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'dynamic_radio';
            radio.value = opt;
            radio.style.cssText = 'width: 1.25rem; height: 1.25rem; accent-color: #3b82f6;';
            
            label.appendChild(radio);
            label.appendChild(document.createTextNode(opt));
            container.appendChild(label);
        });
    }
    else if (inputType === 'checkbox') {
        options.forEach((opt, idx) => {
            const label = document.createElement('label');
            label.style.cssText = 'display: flex; align-items: center; gap: 0.75rem; padding: 1rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.5rem; cursor: pointer;';
            
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = opt;
            cb.style.cssText = 'width: 1.25rem; height: 1.25rem; accent-color: #3b82f6;';
            
            label.appendChild(cb);
            label.appendChild(document.createTextNode(opt));
            container.appendChild(label);
        });
    }
    else {
        // Voice
        const info = document.createElement('div');
        info.innerHTML = '<span style="font-size: 2rem;">🎙️</span><p style="margin: 0; color: #94a3b8; font-size: 1rem;">Speak your answer clearly. Auto-submits when time expires.</p>';
        info.style.cssText = 'display: flex; align-items: center; justify-content: center; gap: 1rem; padding: 1.5rem; background: rgba(59, 130, 246, 0.1); border: 1px dashed rgba(59, 130, 246, 0.4); border-radius: 0.75rem; text-align: center;';
        container.appendChild(info);
    }
}

/* ─── Start Interview ─── */
function startInterview() {
    State.attemptsUsed++;
    State.violationsLog = [];
    State.isFinished = false;

    // Record start time
    const startTimeStr = new Date().toLocaleTimeString();
    State.startTime = startTimeStr;
    const startEl = $('live-start-time');
    if (startEl) startEl.textContent = startTimeStr;
    const endEl = $('live-end-time');
    if (endEl) endEl.textContent = '-';

    // Wire the preview stream to the live video element
    const liveVideo = $('webcam-live');
    if (liveVideo && State.localStream) liveVideo.srcObject = State.localStream;

    const liveAttempt = $('live-attempt');
    if (liveAttempt) liveAttempt.textContent = `${State.attemptsUsed} / ${TOTAL_ATTEMPTS}`;

    updateAttemptDisplay();
    showPhase('interview');
    connectWebSocket();
    startFrameStreaming();
    
    // Start brightness check loop during interview
    State.brightnessInterval = setInterval(checkBrightness, 2000);

    // Initial question fetch
    submitAnswer();
}

/* ─── Stop Interview ─── */
function stopInterview() {
    endInterview('user_stopped');
}

function endInterview(reason) {
    State.isFinished = true;
    isSpeaking = false;
    
    // Clear speech timeout
    if (State.speechTimeout) {
        clearTimeout(State.speechTimeout);
        State.speechTimeout = null;
    }

    // Set end time
    const endTimeStr = new Date().toLocaleTimeString();
    State.endTime = endTimeStr;
    const endEl = $('live-end-time');
    if (endEl) endEl.textContent = endTimeStr;

    // Clear timers
    if (State.timerInterval) { clearInterval(State.timerInterval); State.timerInterval = null; }
    if (State.brightnessInterval) { clearInterval(State.brightnessInterval); State.brightnessInterval = null; }
    stopFrameStreaming();

    // Close WebSocket
    if (State.ws) { State.ws.close(); State.ws = null; }

    // Stop active or queued speech synthesis immediately
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
            window.speechSynthesis.resume();
            window.speechSynthesis.cancel();
        }
    }

    // Update post-interview UI
    const reasonEl = $('end-reason');
    if (reasonEl) {
        const reasons = {
            time_expired: '⏱️ Time expired — interview complete',
            user_stopped: '⏹️ You stopped the interview',
            terminated: '🚫 Session ended due to violations',
        };
        reasonEl.textContent = reasons[reason] || 'Interview ended';
    }

    // Show/hide restart button based on remaining attempts
    const restartBtn = $('btn-restart');
    const attemptsInfo = $('attempts-remaining');
    const remaining = TOTAL_ATTEMPTS - State.attemptsUsed;

    if (restartBtn) {
        if (remaining > 0) {
            restartBtn.style.display = 'inline-flex';
            if (attemptsInfo) attemptsInfo.textContent = `${remaining} attempt${remaining > 1 ? 's' : ''} remaining`;
        } else {
            restartBtn.style.display = 'none';
            if (attemptsInfo) attemptsInfo.textContent = 'All attempts used';
        }
    }

    showPhase('post');
}

/* ─── Restart ─── */
function restartInterview() {
    if (State.attemptsUsed >= TOTAL_ATTEMPTS) return;
    showPhase('preview');
}

/* ─── Attempt Display ─── */
function updateAttemptDisplay() {
    const el = $('attempt-counter');
    if (el) el.textContent = `Attempt ${State.attemptsUsed} of ${TOTAL_ATTEMPTS}`;
}

/* ─── Violations Report ─── */
async function loadViolationsReport() {
    const container = $('violations-container');
    if (!container) return;

    container.innerHTML = '<p style="color:var(--text-muted);text-align:center;">Loading...</p>';

    try {
        const res = await fetch(`/interview/${State.candidateId}/violations`);
        const report = await res.json();

        if (!report.events || report.events.length === 0) {
            container.innerHTML = `
                <div class="clean-result">
                    <div class="result-emoji">✅</div>
                    <p>No violations detected. Great job!</p>
                </div>`;
            return;
        }

        let html = `<p style="color:var(--text-secondary);margin-bottom:0.75rem;">
            ${report.total_violations} violation${report.total_violations > 1 ? 's' : ''} detected
            (${report.total_strikes} strike${report.total_strikes > 1 ? 's' : ''})
        </p><div class="violations-list">`;

        report.events.forEach((ev, i) => {
            const time = new Date(ev.timestamp).toLocaleTimeString();
            const type = ev.violation_type.replace(/_/g, ' ');
            html += `
                <div class="violation-card" style="animation-delay:${i * 0.08}s">
                    <div class="violation-number">${ev.strike_number || (i + 1)}</div>
                    <div class="violation-body">
                        <div class="violation-type">${type}</div>
                        <div class="violation-time">${time}</div>
                        <div class="violation-detail">
                            Gaze metric: ${ev.details?.cause?.gaze_metric?.toFixed(4) || 'N/A'}
                        </div>
                    </div>
                </div>`;
        });

        html += '</div>';
        container.innerHTML = html;
    } catch (err) {
        // Fallback to local violations log
        if (State.violationsLog.length === 0) {
            container.innerHTML = `
                <div class="clean-result">
                    <div class="result-emoji">✅</div>
                    <p>No violations detected. Great job!</p>
                </div>`;
            return;
        }

        let html = `<p style="color:var(--text-secondary);margin-bottom:0.75rem;">
            ${State.violationsLog.length} violation${State.violationsLog.length > 1 ? 's' : ''} detected
        </p><div class="violations-list">`;

        State.violationsLog.forEach((v, i) => {
            const time = new Date(v.timestamp).toLocaleTimeString();
            html += `
                <div class="violation-card" style="animation-delay:${i * 0.08}s">
                    <div class="violation-number">${v.strike}</div>
                    <div class="violation-body">
                        <div class="violation-type">${v.type.replace(/_/g, ' ')}</div>
                        <div class="violation-time">${time}</div>
                    </div>
                </div>`;
        });

        html += '</div>';
        container.innerHTML = html;
    }
}

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initCamera();
    showPhase('preview');
    setInterval(checkBrightness, 3000);
    updateAttemptDisplay();
});
