content = '''{% extends "base.html" %}
{% block title %}Activity Logs - BuildSmart{% endblock %}
{% block breadcrumb %}Activity Logs{% endblock %}

{% block topbar_right %}
<a href="{{ url_for('document.repository') }}" class="btn bto">
  <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
  Repository
</a>
{% endblock %}

{% block content %}

<div class="ph anim">
  <div class="ph-eye">// AUDIT TRAIL</div>
  <div class="ph-title">Activity Logs</div>
  <div class="ph-sub">Full record of every upload and version action in the system.</div>
</div>

<div class="panel anim d1">
  <div class="panel-head">
    <span class="ph-ico">
      <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    </span>
    <h2>System Logs</h2>
    <span class="ph-cnt">{{ logs|length }} events</span>
  </div>

  {% if logs %}
  <table class="dt">
    <thead>
      <tr>
        <th>Doc ID</th>
        <th>Action</th>
        <th>Performed By</th>
        <th>Timestamp</th>
      </tr>
    </thead>
    <tbody>
      {% for log in logs %}
      <tr>
        <td>
          <a href="{{ url_for('document.view_versions', document_id=log.document_id) }}"
             style="color:var(--amber);text-decoration:none;font-weight:500;">
            #{{ log.document_id }}
          </a>
        </td>
        <td>
          {% if log.action == 'UPLOAD' %}
            <span class="bdg bg2">{{ log.action }}</span>
          {% elif log.action == 'NEW_VERSION' %}
            <span class="bdg ba">{{ log.action }}</span>
          {% else %}
            <span class="bdg bx">{{ log.action }}</span>
          {% endif %}
        </td>
        <td style="color:var(--text-1);">{{ log.performed_by }}</td>
        <td style="font-size:0.85rem;">{{ log.timestamp }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% else %}
  <div class="empty">
    <div class="empty-ico">
      <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    </div>
    <h3>No Logs Yet</h3>
    <p>Activity will appear here after uploads.</p>
  </div>
  {% endif %}

</div>
{% endblock %}
'''

with open("templates/logs.html", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS - logs.html fixed!")