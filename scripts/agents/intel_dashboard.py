#!/usr/bin/env python3
"""
Intel Database Dashboard - Web UI for browsing agent intel

Run: python intel_dashboard.py
Open: http://localhost:5050
"""
import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

from intel_database import (
    get_connection, get_stats, get_agent_posting_schedule,
    get_all_posting_schedules, query_agent, fetch_agent_stats,
    get_trending_posts, get_hall_of_fame_posts, get_most_interactive_agents,
    query_shillers, query_websites
)

app = Flask(__name__)

# HTML Template with embedded CSS and JS
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Intel Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'SF Mono', 'Fira Code', monospace;
            background: #0a0a0a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #00ff88; margin-bottom: 10px; font-size: 1.8em; }
        h2 { color: #00aaff; margin: 20px 0 10px; font-size: 1.3em; border-bottom: 1px solid #333; padding-bottom: 5px; }
        h3 { color: #ffaa00; margin: 15px 0 8px; font-size: 1.1em; }

        .stats-bar {
            display: flex; gap: 20px; margin-bottom: 20px;
            background: #1a1a1a; padding: 15px; border-radius: 8px;
        }
        .stat-box {
            text-align: center; padding: 10px 20px;
            background: #252525; border-radius: 6px;
        }
        .stat-value { font-size: 1.8em; color: #00ff88; font-weight: bold; }
        .stat-label { font-size: 0.8em; color: #888; }

        .tabs {
            display: flex; gap: 5px; margin-bottom: 15px;
            border-bottom: 2px solid #333; padding-bottom: 10px;
        }
        .tab {
            padding: 8px 16px; background: #1a1a1a; border: none;
            color: #888; cursor: pointer; border-radius: 6px 6px 0 0;
            font-family: inherit; font-size: 0.9em;
        }
        .tab:hover { background: #252525; color: #fff; }
        .tab.active { background: #00ff88; color: #000; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        table {
            width: 100%; border-collapse: collapse;
            background: #1a1a1a; border-radius: 8px; overflow: hidden;
        }
        th {
            background: #252525; padding: 12px 10px; text-align: left;
            color: #00aaff; cursor: pointer; font-size: 0.85em;
            border-bottom: 2px solid #333;
        }
        th:hover { background: #333; }
        th.sorted-asc::after { content: ' ▲'; color: #00ff88; }
        th.sorted-desc::after { content: ' ▼'; color: #00ff88; }
        td {
            padding: 10px; border-bottom: 1px solid #252525;
            font-size: 0.9em;
        }
        tr:hover { background: #252525; }

        .agent-name { color: #00ff88; font-weight: bold; cursor: pointer; }
        .agent-name:hover { text-decoration: underline; }

        .badge {
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 0.75em; margin-left: 5px;
        }
        .badge-hyperactive { background: #ff4444; color: #fff; }
        .badge-very-active { background: #ff8800; color: #fff; }
        .badge-active { background: #ffcc00; color: #000; }
        .badge-regular { background: #00aaff; color: #fff; }
        .badge-casual { background: #888; color: #fff; }
        .badge-shill { background: #ff00ff; color: #fff; }

        .number { text-align: right; font-variant-numeric: tabular-nums; }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }

        .search-box {
            padding: 10px 15px; background: #1a1a1a; border: 1px solid #333;
            border-radius: 6px; color: #fff; width: 300px; margin-bottom: 15px;
            font-family: inherit;
        }
        .search-box:focus { outline: none; border-color: #00ff88; }

        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); z-index: 1000; overflow-y: auto;
        }
        .modal.active { display: flex; justify-content: center; padding: 50px 20px; }
        .modal-content {
            background: #1a1a1a; border-radius: 12px; padding: 25px;
            max-width: 800px; width: 100%; max-height: 90vh; overflow-y: auto;
        }
        .modal-close {
            float: right; background: none; border: none; color: #888;
            font-size: 1.5em; cursor: pointer;
        }
        .modal-close:hover { color: #ff4444; }

        .detail-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px; margin: 15px 0;
        }
        .detail-box {
            background: #252525; padding: 15px; border-radius: 8px; text-align: center;
        }
        .detail-value { font-size: 1.4em; color: #00ff88; }
        .detail-label { font-size: 0.8em; color: #888; margin-top: 5px; }

        .post-list { margin-top: 15px; }
        .post-item {
            background: #252525; padding: 12px; border-radius: 6px; margin-bottom: 8px;
        }
        .post-content { color: #e0e0e0; margin-bottom: 8px; }
        .post-meta { font-size: 0.8em; color: #888; }
        .post-meta span { margin-right: 15px; }

        .refresh-btn {
            background: #00ff88; color: #000; border: none; padding: 8px 16px;
            border-radius: 6px; cursor: pointer; font-family: inherit; font-weight: bold;
        }
        .refresh-btn:hover { background: #00cc66; }

        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .loading { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕵️ Intel Dashboard</h1>
        <p style="color: #888; margin-bottom: 20px;">MoltX Agent Intelligence Database</p>

        <div class="stats-bar">
            <div class="stat-box">
                <div class="stat-value">{{ stats.agents }}</div>
                <div class="stat-label">Agents Tracked</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{{ stats.posts }}</div>
                <div class="stat-label">Posts Stored</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{{ stats.unique_domains }}</div>
                <div class="stat-label">Domains Found</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{{ stats.patterns }}</div>
                <div class="stat-label">Patterns Detected</div>
            </div>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('agents')">👤 Agents</button>
            <button class="tab" onclick="showTab('schedules')">⏱️ Schedules</button>
            <button class="tab" onclick="showTab('trending')">🔥 Trending</button>
            <button class="tab" onclick="showTab('patterns')">🔍 Patterns</button>
        </div>

        <!-- AGENTS TAB -->
        <div id="tab-agents" class="tab-content active">
            <input type="text" class="search-box" placeholder="Search agents..." onkeyup="filterAgents(this.value)">
            <table id="agents-table">
                <thead>
                    <tr>
                        <th onclick="sortTable('agents-table', 0)">Agent</th>
                        <th onclick="sortTable('agents-table', 1)" class="number">Followers</th>
                        <th onclick="sortTable('agents-table', 2)" class="number">Views</th>
                        <th onclick="sortTable('agents-table', 3)" class="number">Posts</th>
                        <th onclick="sortTable('agents-table', 4)" class="number">Likes</th>
                        <th onclick="sortTable('agents-table', 5)">Last Seen</th>
                    </tr>
                </thead>
                <tbody>
                    {% for agent in agents %}
                    <tr>
                        <td><span class="agent-name" onclick="showAgentDetail('{{ agent.name }}')">{{ agent.avatar_emoji or '🤖' }} {{ agent.name }}</span></td>
                        <td class="number">{{ agent.current_followers or 0 }}</td>
                        <td class="number">{{ agent.current_views or 0 }}</td>
                        <td class="number">{{ agent.current_posts or 0 }}</td>
                        <td class="number">{{ agent.current_likes or 0 }}</td>
                        <td>{{ agent.last_seen[:10] if agent.last_seen else 'Unknown' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- SCHEDULES TAB -->
        <div id="tab-schedules" class="tab-content">
            <h3>⚡ Posting Schedules (agents with 3+ posts)</h3>
            <table id="schedules-table">
                <thead>
                    <tr>
                        <th onclick="sortTable('schedules-table', 0)">Agent</th>
                        <th onclick="sortTable('schedules-table', 1)" class="number">Avg Interval</th>
                        <th onclick="sortTable('schedules-table', 2)" class="number">Posts/Day</th>
                        <th onclick="sortTable('schedules-table', 3)">Schedule Type</th>
                        <th onclick="sortTable('schedules-table', 4)" class="number">Total Posts</th>
                        <th onclick="sortTable('schedules-table', 5)" class="number">Active Days</th>
                    </tr>
                </thead>
                <tbody>
                    {% for s in schedules %}
                    <tr>
                        <td><span class="agent-name" onclick="showAgentDetail('{{ s.agent }}')">{{ s.agent }}</span></td>
                        <td class="number">{{ "%.1f"|format(s.avg_interval_minutes) }}m</td>
                        <td class="number">{{ "%.1f"|format(s.posts_per_day) }}</td>
                        <td>
                            <span class="badge badge-{{ s.schedule_type }}">{{ s.schedule_type }}</span>
                        </td>
                        <td class="number">{{ s.total_posts }}</td>
                        <td class="number">{{ "%.1f"|format(s.active_days) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- TRENDING TAB -->
        <div id="tab-trending" class="tab-content">
            <h3>🔥 High Engagement Posts</h3>
            <div class="post-list">
                {% for post in trending %}
                <div class="post-item">
                    <div class="post-content">{{ post.content[:200] }}{% if post.content|length > 200 %}...{% endif %}</div>
                    <div class="post-meta">
                        <span class="agent-name" onclick="showAgentDetail('{{ post.agent_name }}')">@{{ post.agent_name }}</span>
                        <span>❤️ {{ post.likes }}</span>
                        <span>💬 {{ post.replies }}</span>
                        <span>🔁 {{ post.reposts }}</span>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- PATTERNS TAB -->
        <div id="tab-patterns" class="tab-content">
            <h3>🎯 Detected Shillers</h3>
            <table>
                <thead>
                    <tr>
                        <th>Agent</th>
                        <th>Pattern</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {% for name, desc, conf in shillers %}
                    <tr>
                        <td><span class="agent-name" onclick="showAgentDetail('{{ name }}')">@{{ name }}</span></td>
                        <td>{{ desc }}</td>
                        <td>{{ "%.0f"|format(conf * 100) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <h3 style="margin-top: 30px;">🌐 Top Domains Shared</h3>
            <table>
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th class="number">Agents</th>
                        <th class="number">Total Shares</th>
                    </tr>
                </thead>
                <tbody>
                    {% for domain, agents, shares in websites %}
                    <tr>
                        <td>{{ domain }}</td>
                        <td class="number">{{ agents }}</td>
                        <td class="number">{{ shares }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- AGENT DETAIL MODAL -->
    <div id="agent-modal" class="modal" onclick="if(event.target===this)closeModal()">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <div id="modal-body">Loading...</div>
        </div>
    </div>

    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector(`[onclick="showTab('${tabId}')"]`).classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
        }

        function sortTable(tableId, colIndex) {
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const th = table.querySelectorAll('th')[colIndex];
            const isAsc = th.classList.contains('sorted-asc');

            // Clear sort indicators
            table.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));

            rows.sort((a, b) => {
                let aVal = a.cells[colIndex].textContent.trim();
                let bVal = b.cells[colIndex].textContent.trim();

                // Try numeric sort
                const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
                const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));

                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return isAsc ? aNum - bNum : bNum - aNum;
                }
                return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
            });

            th.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
            rows.forEach(row => tbody.appendChild(row));
        }

        function filterAgents(query) {
            const rows = document.querySelectorAll('#agents-table tbody tr');
            query = query.toLowerCase();
            rows.forEach(row => {
                const name = row.cells[0].textContent.toLowerCase();
                row.style.display = name.includes(query) ? '' : 'none';
            });
        }

        function showAgentDetail(name) {
            const modal = document.getElementById('agent-modal');
            const body = document.getElementById('modal-body');
            body.innerHTML = '<div class="loading">Loading agent data...</div>';
            modal.classList.add('active');

            fetch('/api/agent/' + encodeURIComponent(name))
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        body.innerHTML = '<p style="color:#ff4444;">Error: ' + data.error + '</p>';
                        return;
                    }

                    let html = `
                        <h2>${data.avatar_emoji || '🤖'} ${data.display_name || data.name}</h2>
                        <p style="color:#888;">@${data.name}</p>
                        ${data.bio ? '<p style="margin:10px 0;">' + data.bio + '</p>' : ''}

                        <div class="detail-grid">
                            <div class="detail-box">
                                <div class="detail-value">${data.current_followers || 0}</div>
                                <div class="detail-label">Followers</div>
                            </div>
                            <div class="detail-box">
                                <div class="detail-value">${data.current_views || 0}</div>
                                <div class="detail-label">Views</div>
                            </div>
                            <div class="detail-box">
                                <div class="detail-value">${data.current_posts || 0}</div>
                                <div class="detail-label">Posts</div>
                            </div>
                            <div class="detail-box">
                                <div class="detail-value">${data.current_likes || 0}</div>
                                <div class="detail-label">Likes</div>
                            </div>
                        </div>
                    `;

                    if (data.schedule) {
                        const s = data.schedule;
                        html += `
                            <h3>⏱️ Posting Schedule</h3>
                            <div class="detail-grid">
                                <div class="detail-box">
                                    <div class="detail-value">${s.avg_interval_minutes ? s.avg_interval_minutes.toFixed(1) + 'm' : 'N/A'}</div>
                                    <div class="detail-label">Avg Interval</div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-value">${s.posts_per_day ? s.posts_per_day.toFixed(1) : 'N/A'}</div>
                                    <div class="detail-label">Posts/Day</div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-value"><span class="badge badge-${s.schedule_type}">${s.schedule_type}</span></div>
                                    <div class="detail-label">Type</div>
                                </div>
                            </div>
                        `;
                    }

                    if (data.recent_posts && data.recent_posts.length > 0) {
                        html += '<h3>📝 Recent Posts</h3><div class="post-list">';
                        data.recent_posts.slice(0, 5).forEach(post => {
                            html += `
                                <div class="post-item">
                                    <div class="post-content">${(post.content || '').substring(0, 200)}${(post.content || '').length > 200 ? '...' : ''}</div>
                                    <div class="post-meta">
                                        <span>❤️ ${post.likes || 0}</span>
                                        <span>💬 ${post.replies || 0}</span>
                                        <span>${post.timestamp ? post.timestamp.substring(0, 10) : ''}</span>
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                    }

                    if (data.patterns && data.patterns.length > 0) {
                        html += '<h3>🔍 Detected Patterns</h3><ul style="margin-left:20px;">';
                        data.patterns.forEach(p => {
                            html += `<li>${p.pattern_type}: ${p.description} (${Math.round(p.confidence * 100)}%)</li>`;
                        });
                        html += '</ul>';
                    }

                    if (data.websites && data.websites.length > 0) {
                        html += '<h3>🌐 Websites</h3><ul style="margin-left:20px;">';
                        data.websites.forEach(w => {
                            html += `<li><a href="${w[1]}" target="_blank" style="color:#00aaff;">${w[0]}</a></li>`;
                        });
                        html += '</ul>';
                    }

                    body.innerHTML = html;
                })
                .catch(err => {
                    body.innerHTML = '<p style="color:#ff4444;">Failed to load: ' + err + '</p>';
                });
        }

        function closeModal() {
            document.getElementById('agent-modal').classList.remove('active');
        }

        // Close modal on escape
        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
    </script>
</body>
</html>
"""


def get_all_agents():
    """Get all agents from database"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT name, display_name, avatar_emoji, bio, first_seen, last_seen,
               current_followers, current_following, current_views, current_posts, current_likes
        FROM agents
        ORDER BY current_followers DESC
    ''')
    columns = ['name', 'display_name', 'avatar_emoji', 'bio', 'first_seen', 'last_seen',
               'current_followers', 'current_following', 'current_views', 'current_posts', 'current_likes']
    agents = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return agents


@app.route('/')
def dashboard():
    """Main dashboard page"""
    stats = get_stats()
    agents = get_all_agents()
    schedules = get_all_posting_schedules(min_posts=3)
    trending = get_trending_posts(min_likes=1, limit=20)
    shillers = query_shillers()
    websites = query_websites()[:20]

    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        agents=agents,
        schedules=schedules,
        trending=trending,
        shillers=shillers,
        websites=websites
    )


@app.route('/api/agent/<name>')
def api_agent(name):
    """API endpoint for agent details"""
    try:
        agent = query_agent(name)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Add schedule
        schedule = get_agent_posting_schedule(name)
        agent['schedule'] = schedule

        return jsonify(agent)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint for database stats"""
    return jsonify(get_stats())


@app.route('/api/refresh/<name>')
def api_refresh(name):
    """Fetch fresh stats from MoltX API"""
    try:
        stats = fetch_agent_stats(name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050

    print("\n" + "="*50)
    print("🕵️  INTEL DASHBOARD")
    print("="*50)
    print(f"\nOpen in browser: http://localhost:{port}")
    print("Press Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=port, debug=True)
