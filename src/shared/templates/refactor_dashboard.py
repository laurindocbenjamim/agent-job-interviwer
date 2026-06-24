import os

path = "/Users/fetiwaetika/agents-projects/agent-job-interviwer/src/shared/templates/admin_dashboard.html"
with open(path, "r") as f:
    content = f.read()

# The content-area starts exactly with:
content_area_start = '<div class="content-area">'
idx_start = content.find(content_area_start)
if idx_start == -1:
    print("Could not find content-area")
    exit(1)

# The content-area ends before the <script> block
script_start = content.rfind('<script>')
if script_start == -1:
    print("Could not find script block")
    exit(1)

script_end = content.rfind('</script>')

content_area = content[idx_start + len(content_area_start) : script_start].strip()
# Remove the trailing '</div>\n    </div>' from content_area
if content_area.endswith("</div>"):
    content_area = content_area.rsplit("</div>", 1)[0].strip()
if content_area.endswith("</div>"):
    content_area = content_area.rsplit("</div>", 1)[0].strip()

script_content = content[script_start + len('<script>') : script_end].strip()

# Update the script
script_content = script_content.replace(
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
{script_content}
</script>
{{% endblock %}}
"""
with open(path, "w") as f:
    f.write(new_html)
print("Dashboard refactored!")
