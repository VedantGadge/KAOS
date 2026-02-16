// Log Interceptor
(function() {
    const consoleOutput = document.getElementById('console-output');
    const originalConsole = {
        log: console.log,
        info: console.info,
        warn: console.warn,
        error: console.error,
        debug: console.debug
    };

    function appendLog(level, args) {
        if (!consoleOutput) return;

        const entry = document.createElement('div');
        entry.className = `log-entry log-${level}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
                } catch (e) {
                    return '[Unserializable Object]';
                }
            }
            return String(arg);
        }).join(' ');

        entry.innerHTML = `
            <span class="log-time">${timestamp}</span>
            <span class="log-level">${level}</span>
            <span class="log-message">${message}</span>
        `;

        consoleOutput.appendChild(entry);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    console.log = (...args) => {
        originalConsole.log.apply(console, args);
        appendLog('info', args);
    };

    console.info = (...args) => {
        originalConsole.info.apply(console, args);
        appendLog('info', args);
    };

    console.warn = (...args) => {
        originalConsole.warn.apply(console, args);
        appendLog('warn', args);
    };

    console.error = (...args) => {
        originalConsole.error.apply(console, args);
        appendLog('error', args);
    };

    console.debug = (...args) => {
        originalConsole.debug.apply(console, args);
        appendLog('debug', args);
    };

    window.clearLogs = () => {
        consoleOutput.innerHTML = '';
        console.info('Console cleared');
    };

    // Initial log
    setTimeout(() => {
        console.info('KAOS Control Plane Console initialized.');
        console.debug('Polling backend every 2s...');
    }, 500);
})();

const AGENTS = ['ingestion', 'triager', 'review_manager', 'ops_manager'];

// Poll interval
setInterval(fetchStatus, 2000);
fetchStatus(); // Initial load

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const statusMap = await response.json();
        renderAgents(statusMap);
        updateSystemStatus(true);
    } catch (error) {
        console.error('Failed to fetch status:', error);
        updateSystemStatus(false);
    }
}

function updateSystemStatus(online) {
    const badge = document.getElementById('system-status');
    const dot = badge.querySelector('.dot');
    if (online) {
        badge.innerHTML = '<span class="dot"></span> System Ready';
        badge.style.color = 'var(--success)';
        badge.style.background = 'rgba(16, 185, 129, 0.1)';
        dot.style.backgroundColor = 'var(--success)';
    } else {
        badge.innerHTML = '<span class="dot" style="background:var(--error)"></span> Backend Offline';
        badge.style.color = 'var(--error)';
        badge.style.background = 'rgba(239, 68, 68, 0.1)';
    }
}

function renderAgents(statusMap) {
    const grid = document.getElementById('agents-grid');
    grid.innerHTML = '';

    AGENTS.forEach(agent => {
        const isRunning = statusMap[agent] === 'running';
        const card = document.createElement('div');
        card.className = `card agent-card ${isRunning ? 'running' : 'stopped'}`;
        
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <div class="agent-name">${agent.replace('_', ' ')}</div>
                    <div class="agent-status ${isRunning ? 'status-running' : 'status-stopped'}">
                        ${isRunning ? '<i class="fa-solid fa-circle-play"></i> Running' : '<i class="fa-solid fa-circle-stop"></i> Stopped'}
                    </div>
                </div>
                <div class="card-icon ${isRunning ? 'success' : 'error'}">
                    <i class="fa-solid fa-robot"></i>
                </div>
            </div>
            <div class="card-content">
                <p>${getAgentDescription(agent)}</p>
            </div>
            <div class="card-actions">
                ${isRunning 
                    ? `<button onclick="stopAgent('${agent}')" class="btn btn-danger"><i class="fa-solid fa-power-off"></i> Stop</button>`
                    : `<button onclick="startAgent('${agent}')" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start</button>`
                }
            </div>
        `;
        grid.appendChild(card);
    });
}

function getAgentDescription(agent) {
    const desc = {
        'ingestion': 'Entry point for all external webhooks (Sentry, GitHub).',
        'triager': 'Analyzes new bugs and assigns them to the right team.',
        'review_manager': 'Orchestrates CI/CD pipeline and PR reviews.',
        'ops_manager': 'Manages deployment and monitors system health.'
    };
    return desc[agent] || 'Autonomous Agent';
}

async function startAgent(name) {
    showToast(`Starting ${name}...`, 'info');
    try {
        const res = await fetch(`/api/agents/${name}/start`, { method: 'POST' });
        if (res.ok) {
            showToast(`${name} started successfully`, 'success');
            fetchStatus();
        } else {
            throw new Error('Failed to start');
        }
    } catch (e) {
        showToast(`Error starting ${name}`, 'error');
    }
}

async function stopAgent(name) {
    if (!confirm(`Are you sure you want to stop ${name}?`)) return;
    
    showToast(`Stopping ${name}...`, 'info');
    try {
        const res = await fetch(`/api/agents/${name}/stop`, { method: 'POST' });
        if (res.ok) {
            showToast(`${name} stopped successfully`, 'success');
            fetchStatus();
        } else {
            throw new Error('Failed to stop');
        }
    } catch (e) {
        showToast(`Error stopping ${name}`, 'error');
    }
}

async function simulate(type, option = null) {
    showToast(`Triggering simulation: ${type} ${option ? '(' + option + ')' : ''}...`, 'info');
    
    let payload = {
        service_name: 'payment-service'
    };

    if (type === 'sentry_error' || type === 'pr_open') {
        payload.error_message = 'Simulation Test Error';
        if (type === 'pr_open') {
            const authorSelect = document.getElementById('pr-author-select');
            if (authorSelect) {
                payload.pr_author = authorSelect.value;
            }
        }
    } else if (type === 'pr_decision') {
        payload.pr_id = 101;
        payload.decision = option; // APPROVED or CHANGES_REQUESTED
        payload.comment = option === 'APPROVED' ? 'Looks good to me!' : 'Please fix the logic error.';
    } else if (type === 'deployment') {
        payload.status = option; // success or failure
        const reviewerSelect = document.getElementById('deploy-reviewer-select');
        if (reviewerSelect) {
            payload.reviewer = reviewerSelect.value;
        }
    }

    try {
        const res = await fetch(`/api/simulate/${type}`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            const data = await res.json();
            showToast(`Simulation triggered! ID: ${data.event_id || 'OK'}`, 'success');
        } else {
            throw new Error('Simulation failed');
        }
    } catch (e) {
        showToast(`Simulation failed: ${e.message}`, 'error');
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fa-solid ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
