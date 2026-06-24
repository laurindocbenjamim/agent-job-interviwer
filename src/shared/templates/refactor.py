import os
import re

base_dir = "/Users/fetiwaetika/agents-projects/agent-job-interviwer/src/shared/templates"

def process_dashboard():
    path = os.path.join(base_dir, "admin_dashboard.html")
    with open(path, "r") as f:
        content = f.read()

    # Extract the custom styles specifically for dashboard (if any). Let's keep them all just to be safe, except the ones that clash.
    # Actually, layout.html has all the CSS needed. We can just extract everything inside <div class="content-area"> and <script> tags.
    
    content_area_match = re.search(r'<div class="content-area">(.*?)<script>', content, re.DOTALL)
    script_match = re.search(r'<script>(.*?)</script>\s*</body>', content, re.DOTALL)
    
    if not content_area_match or not script_match:
        print("Failed to match dashboard")
        return

    # Extract up to the last 2 closing divs before <script>
    content_area_raw = content_area_match.group(1)
    content_area = content_area_raw.rsplit("</div>", 2)[0]
    script = script_match.group(1)

    # Need to update the candidate UUID in the dashboard logic to be an input field
    # In dashboard, when selecting a session: 
    # document.getElementById('topbar-title').innerHTML = `Monitoring Session: <span style="color:var(--accent-blue); margin-left:0.5rem;">${id}</span>`;
    # We change it to an input field with copy icon.
    script = script.replace(
        "`Monitoring Session: <span style=\"color:var(--accent-blue); margin-left:0.5rem;\">${id}</span>`",
        "`Monitoring Session: <input type='text' readonly value='${id}' id='uuid-copy' style='background:transparent; border:none; color:var(--accent-blue); margin-left:0.5rem; font-size:inherit; font-family:inherit; outline:none; font-weight:bold; width: 330px;' /> <button onclick='navigator.clipboard.writeText(\"${id}\"); this.innerHTML=\"✅\"' style='background:transparent; border:none; cursor:pointer; font-size:1.2rem;' title='Copy UUID'>📋</button>`"
    )

    new_html = f"""{{% extends "admin_layout.html" %}}

{{% block sidebar_sessions %}}
        <div class="sidebar-action" style="padding: 1rem; border-bottom: 1px solid var(--glass-border); display: flex; flex-direction: column; gap: 0.5rem; justify-content: center; width: 100%;">
            <button class="action-btn" data-tooltip="Configure Interview" onclick="openConfigPopup()" style="width: 100%; padding: 0.75rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); color: var(--text-primary); font-weight: 600; font-family: inherit; font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 0.5rem; transition: all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.03)'">
                <span>⚙️</span> <span class="sidebar-btn-text">Configure Interview</span>
            </button>
        </div>
        <div class="sessions-list" id="sessions-list">
            <!-- Populated by JS -->
            <div class="session-info" style="color:var(--text-secondary); padding: 1rem; text-align: center;">Loading...</div>
        </div>
{{% endblock %}}

{{% block topbar_content %}}
    <div id="topbar-title">Select a session to monitor</div>
{{% endblock %}}

{{% block content %}}
<div class="content-area">
{content_area}
</div>
{{% endblock %}}

{{% block extra_js %}}
<script>
{script}
</script>
{{% endblock %}}
"""
    with open(path, "w") as f:
        f.write(new_html)


def process_candidates():
    path = os.path.join(base_dir, "admin_candidates.html")
    with open(path, "r") as f:
        content = f.read()

    # Extract the <div class="container"> content and <script> content
    container_match = re.search(r'<div class="container">(.*?)</div>\s*<script>', content, re.DOTALL)
    script_match = re.search(r'<script>(.*?)</script>\s*</body>', content, re.DOTALL)
    
    if not container_match or not script_match:
        print("Failed to match candidates")
        return

    container = container_match.group(1)
    script = script_match.group(1)
    
    # Update candidate ID copy icon in candidates directory too!
    script = script.replace(
        "<strong>Candidate ID (UUID):</strong> <span style=\"font-family: monospace; color: var(--accent-blue); word-break: break-all;\">${data.candidate_id}</span>",
        "<strong>Candidate ID (UUID):</strong> <input type='text' readonly value='${data.candidate_id}' style='background:transparent; border:none; color:var(--accent-blue); margin-left:0.5rem; font-size:inherit; font-family:monospace; outline:none; font-weight:bold; width: 280px;' /> <button onclick='navigator.clipboard.writeText(\"${data.candidate_id}\"); this.innerHTML=\"✅\"' style='background:transparent; border:none; cursor:pointer; font-size:1.2rem;' title='Copy UUID'>📋</button>"
    )

    new_html = f"""{{% extends "admin_layout.html" %}}

{{% block topbar_content %}}
    <div id="topbar-title">Candidate Directory</div>
{{% endblock %}}

{{% block content %}}
<div class="content-area-full">
    <div class="container" style="max-width: 1000px; width: 100%; display: flex; flex-direction: column; gap: 2rem;">
{container}
    </div>
</div>
{{% endblock %}}

{{% block extra_js %}}
<script>
{script}
</script>
{{% endblock %}}
"""
    with open(path, "w") as f:
        f.write(new_html)

def process_voice():
    path = os.path.join(base_dir, "admin_voice_cloning.html")
    with open(path, "r") as f:
        content = f.read()

    container_match = re.search(r'<div class="container">(.*?)</div>\s*<script>', content, re.DOTALL)
    script_match = re.search(r'<script>(.*?)</script>\s*</body>', content, re.DOTALL)
    
    if not container_match or not script_match:
        print("Failed to match voice cloning")
        return

    container = container_match.group(1)
    script = script_match.group(1)

    # Inject the audio player after #status-msg
    audio_player_html = """
        <div id="audio-player-container" class="glass-card" style="display: none; margin-top: 1rem; align-items: center; justify-content: space-between;">
            <div style="flex: 1; display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 1.5rem;">🔊</span>
                <audio id="cloned-voice-audio" controls style="width: 100%; height: 36px;"></audio>
            </div>
            <div style="display: flex; gap: 0.5rem; margin-left: 1rem;">
                <a id="download-voice-btn" download="cloned_voice.wav" class="action-btn" style="background: rgba(59, 130, 246, 0.1); border: 1px solid var(--accent-blue); color: var(--accent-blue); padding: 0.5rem 1rem; text-decoration: none; display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    ⬇️ Download
                </a>
                <button onclick="deleteClonedVoice()" class="action-btn" style="background: rgba(239, 68, 68, 0.1); border: 1px solid var(--accent-red); color: var(--accent-red); padding: 0.5rem 1rem; display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    🗑️ Delete
                </button>
            </div>
        </div>
"""
    container = container.replace('<div id="status-msg"></div>', '<div id="status-msg"></div>' + audio_player_html)
    
    new_script = script + """

        async function checkExistingVoice() {
            try {
                const res = await fetch('/admin/voice/file', { method: 'HEAD' });
                if (res.ok) {
                    showAudioPlayer();
                }
            } catch(e) {}
        }
        
        function showAudioPlayer() {
            const playerContainer = document.getElementById('audio-player-container');
            const audio = document.getElementById('cloned-voice-audio');
            const downloadBtn = document.getElementById('download-voice-btn');
            
            playerContainer.style.display = 'flex';
            const audioUrl = `/admin/voice/file?t=${Date.now()}`;
            audio.src = audioUrl;
            downloadBtn.href = audioUrl;
        }

        async function deleteClonedVoice() {
            if(!confirm("Are you sure you want to delete the cloned voice?")) return;
            try {
                const res = await fetch('/admin/voice/file', { method: 'DELETE' });
                if (res.ok) {
                    document.getElementById('audio-player-container').style.display = 'none';
                    showStatus("Voice deleted successfully.", "success");
                }
            } catch(e) {
                console.error(e);
            }
        }

        // On load check
        document.addEventListener('DOMContentLoaded', checkExistingVoice);
"""

    # Inside startRecording / uploadAudioFile success, call showAudioPlayer()
    new_script = new_script.replace(
        "showStatus(`✅ ${data.message}`, 'success');",
        "showStatus(`✅ ${data.message}`, 'success'); showAudioPlayer();"
    )

    new_html = f"""{{% extends "admin_layout.html" %}}

{{% block topbar_content %}}
    <div id="topbar-title">Voice Cloning</div>
{{% endblock %}}

{{% block content %}}
<div class="content-area-full">
    <div class="container" style="max-width: 800px; width: 100%; display: flex; flex-direction: column; gap: 2rem;">
{container}
    </div>
</div>
{{% endblock %}}

{{% block extra_js %}}
<script>
{new_script}
</script>
{{% endblock %}}
"""
    with open(path, "w") as f:
        f.write(new_html)


process_dashboard()
process_candidates()
process_voice()
