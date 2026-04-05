// Jarvis Dashboard - Frontend Logic

const API = '';

// === CHAT ===
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    input.value = '';

    // Try AI chat first, fallback to basic chat
    try {
        const aiResp = await fetch(`${API}/api/ai/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message}),
        });
        const aiData = await aiResp.json();
        if (aiData.response) {
            addMessage(aiData.response, 'jarvis');
            return;
        }
        if (aiData.fallback_response) {
            // Use basic chat engine
            const resp = await fetch(`${API}/api/chat`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message}),
            });
            const data = await resp.json();
            addMessage(data.response, 'jarvis');
            return;
        }
    } catch (e) {
        // Fallback to basic
    }

    try {
        const resp = await fetch(`${API}/api/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message}),
        });
        const data = await resp.json();
        addMessage(data.response, 'jarvis');
    } catch (e) {
        addMessage('Connection error. Please check the server.', 'jarvis');
    }
}

function addMessage(text, sender) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${sender === 'jarvis' ? 'jarvis-msg' : 'user-msg'}`;
    div.innerHTML = `
        <span class="sender">${sender === 'jarvis' ? 'JARVIS' : 'YOU'}</span>
        <p>${escapeHtml(text)}</p>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// === WEATHER ===
async function getWeather() {
    const city = prompt('Enter city name:', 'New York') || 'New York';
    try {
        const resp = await fetch(`${API}/api/weather/current/${encodeURIComponent(city)}`);
        const data = await resp.json();
        const panel = document.getElementById('weather-content');

        if (data.mock_data) {
            const w = data.mock_data;
            panel.innerHTML = `
                <p><strong>${w.city}</strong></p>
                <p>${w.temperature}°F - ${w.description}</p>
                <p>Humidity: ${w.humidity}% | Wind: ${w.wind_speed} mph</p>
                <p class="hint">${w.note}</p>
            `;
        } else {
            panel.innerHTML = `
                <p><strong>${data.city}, ${data.country}</strong></p>
                <p>${data.temperature}°F - ${data.description}</p>
                <p>Feels like: ${data.feels_like}°F</p>
                <p>Humidity: ${data.humidity}% | Wind: ${data.wind_speed} mph</p>
            `;
        }
        addMessage(`Weather for ${city}: ${data.temperature || data.mock_data?.temperature}°F, ${data.description || data.mock_data?.description}`, 'jarvis');
    } catch (e) {
        addMessage('Unable to fetch weather data.', 'jarvis');
    }
}

// === NEWS ===
async function getNews() {
    try {
        const resp = await fetch(`${API}/api/news/top?count=5`);
        const data = await resp.json();
        const articles = data.articles || data.mock_data || [];
        let msg = 'Top Headlines:\n\n';
        articles.forEach((a, i) => {
            msg += `${i + 1}. ${a.title} (${a.source})\n`;
        });
        addMessage(msg, 'jarvis');
    } catch (e) {
        addMessage('Unable to fetch news.', 'jarvis');
    }
}

// === SYSTEM STATUS ===
async function getSystemStatus() {
    try {
        const resp = await fetch(`${API}/api/system/status`);
        const data = await resp.json();
        addMessage(data.report, 'jarvis');
    } catch (e) {
        addMessage('Unable to get system status.', 'jarvis');
    }
}

// === QUOTES ===
async function getQuote() {
    try {
        const resp = await fetch(`${API}/api/utils/quote`);
        const data = await resp.json();
        addMessage(`"${data.quote}" — ${data.author}`, 'jarvis');
    } catch (e) {
        addMessage('Unable to fetch quote.', 'jarvis');
    }
}

// === TASKS ===
async function addTask() {
    const input = document.getElementById('task-input');
    const content = input.value.trim();
    if (!content) return;
    input.value = '';
    try {
        await fetch(`${API}/api/system/tasks`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content}),
        });
        loadTasks();
    } catch (e) {
        addMessage('Failed to add task.', 'jarvis');
    }
}

async function loadTasks() {
    try {
        const resp = await fetch(`${API}/api/system/tasks`);
        const data = await resp.json();
        document.getElementById('tasks-content').innerHTML =
            `<pre style="font-size:0.8rem;color:var(--text-dim);white-space:pre-wrap">${escapeHtml(data.report)}</pre>`;
    } catch (e) {
        document.getElementById('tasks-content').innerHTML =
            '<p class="panel-placeholder">Unable to load tasks</p>';
    }
}

// === POMODORO ===
async function startPomodoro() {
    try {
        const resp = await fetch(`${API}/api/study/pomodoro/start`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
        const data = await resp.json();
        document.getElementById('pomodoro-status').textContent = data.message;
        addMessage(data.message, 'jarvis');
        // Poll status
        const interval = setInterval(async () => {
            const sr = await fetch(`${API}/api/study/pomodoro/status`);
            const sd = await sr.json();
            document.getElementById('pomodoro-status').textContent =
                sd.active ? `${sd.remaining_minutes} min remaining` : 'Session complete!';
            if (!sd.active) {
                clearInterval(interval);
                addMessage(`Pomodoro complete! ${sd.sessions_completed} session(s) done today.`, 'jarvis');
            }
        }, 30000);
    } catch (e) {
        addMessage('Failed to start Pomodoro.', 'jarvis');
    }
}

// === SCHEDULE ===
async function showSchedule() {
    try {
        const resp = await fetch(`${API}/api/study/schedule/today`);
        const data = await resp.json();
        let msg = `${data.message}\n\n`;
        data.classes.forEach(c => {
            msg += `${c.start_time}-${c.end_time}: ${c.name}`;
            if (c.location) msg += ` (${c.location})`;
            msg += '\n';
        });
        addMessage(msg, 'jarvis');
    } catch (e) {
        addMessage('Unable to load schedule.', 'jarvis');
    }
}

// === BUDGET ===
async function showBudget() {
    try {
        const resp = await fetch(`${API}/api/finance/expense/summary`);
        const data = await resp.json();
        const panel = document.getElementById('finance-content');

        let html = '';
        if (data.budget > 0) {
            const pct = Math.min(100, (data.total_spent / data.budget) * 100);
            const color = pct > 80 ? 'var(--danger)' : pct > 60 ? 'var(--warning)' : 'var(--secondary)';
            html += `<p>Budget: $${data.budget} | Spent: $${data.total_spent}</p>`;
            html += `<div class="budget-bar"><div class="budget-bar-fill" style="width:${pct}%;background:${color}"></div></div>`;
            if (data.remaining !== null) html += `<p>Remaining: $${data.remaining}</p>`;
        } else {
            html += `<p>Total spent: $${data.total_spent}</p>`;
        }

        if (data.by_category && Object.keys(data.by_category).length > 0) {
            html += '<div style="margin-top:10px">';
            for (const [cat, amt] of Object.entries(data.by_category)) {
                html += `<div class="budget-category"><span>${cat}</span><span>$${amt}</span></div>`;
            }
            html += '</div>';
        }
        panel.innerHTML = html || '<p class="panel-placeholder">No expenses yet</p>';
    } catch (e) {
        // Ignore
    }
}

async function addExpense() {
    const amount = parseFloat(document.getElementById('expense-amount').value);
    const category = document.getElementById('expense-category').value;
    if (!amount || amount <= 0) return;

    try {
        const resp = await fetch(`${API}/api/finance/expense/add`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({amount, category, description: ''}),
        });
        const data = await resp.json();
        document.getElementById('expense-amount').value = '';
        addMessage(data.message, 'jarvis');
        showBudget();
    } catch (e) {
        addMessage('Failed to log expense.', 'jarvis');
    }
}

// === GPA ===
async function showGPA() {
    const coursesStr = prompt(
        'Enter courses (format: Name:Grade:Credits, comma separated)\n' +
        'Example: Math:A:3, English:B+:3, Physics:A-:4'
    );
    if (!coursesStr) return;

    const courses = coursesStr.split(',').map(c => {
        const parts = c.trim().split(':');
        return {name: parts[0], grade: parts[1], credits: parseInt(parts[2]) || 3};
    });

    try {
        const resp = await fetch(`${API}/api/study/gpa/calculate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({courses}),
        });
        const data = await resp.json();
        let msg = `GPA Calculation:\n\n`;
        data.courses.forEach(c => {
            msg += `${c.name}: ${c.grade} (${c.credits} cr) = ${c.grade_points}\n`;
        });
        msg += `\nSemester GPA: ${data.semester_gpa}`;
        addMessage(msg, 'jarvis');
    } catch (e) {
        addMessage('Failed to calculate GPA. Check your input format.', 'jarvis');
    }
}

// === DICTIONARY ===
async function lookupWord() {
    const input = document.getElementById('dict-input');
    const word = input.value.trim();
    if (!word) return;

    try {
        const resp = await fetch(`${API}/api/study/dictionary/${encodeURIComponent(word)}`);
        const data = await resp.json();
        const result = document.getElementById('dict-result');

        if (data.found) {
            let html = `<strong>${data.word}</strong>`;
            if (data.phonetic) html += ` <em>${data.phonetic}</em>`;
            html += '<br>';
            data.meanings.forEach(m => {
                html += `<em>${m.part_of_speech}</em>: ${m.definitions[0].definition}<br>`;
            });
            result.innerHTML = html;
        } else {
            result.innerHTML = data.message;
        }
    } catch (e) {
        document.getElementById('dict-result').textContent = 'Lookup failed.';
    }
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    showBudget();

    // Focus chat input
    document.getElementById('chat-input').focus();
});
