/**
 * Interview actions: start, stop, timer, violations report, and attempt management.
 */

/* ─── Timer ─── */
function startTimer() {
    State.remainingSeconds = INTERVIEW_DURATION * 60;
    updateTimerDisplay();

    State.timerInterval = setInterval(() => {
        State.remainingSeconds--;
        updateTimerDisplay();

        if (State.remainingSeconds <= 0) {
            endInterview('time_expired');
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

/* ─── Start Interview ─── */
function startInterview() {
    State.attemptsUsed++;
    State.violationsLog = [];
    State.remainingSeconds = INTERVIEW_DURATION * 60;

    // Wire the preview stream to the live video element
    const liveVideo = $('webcam-live');
    if (liveVideo && State.localStream) liveVideo.srcObject = State.localStream;

    const liveAttempt = $('live-attempt');
    if (liveAttempt) liveAttempt.textContent = `${State.attemptsUsed} / ${TOTAL_ATTEMPTS}`;

    updateAttemptDisplay();
    showPhase('interview');
    connectWebSocket();
    startFrameStreaming();
    startTimer();

    // Start brightness check loop during interview
    State.brightnessInterval = setInterval(checkBrightness, 2000);
}

/* ─── Stop Interview ─── */
function stopInterview() {
    endInterview('user_stopped');
}

function endInterview(reason) {
    // Clear timers
    if (State.timerInterval) { clearInterval(State.timerInterval); State.timerInterval = null; }
    if (State.brightnessInterval) { clearInterval(State.brightnessInterval); State.brightnessInterval = null; }
    stopFrameStreaming();

    // Close WebSocket
    if (State.ws) { State.ws.close(); State.ws = null; }

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
