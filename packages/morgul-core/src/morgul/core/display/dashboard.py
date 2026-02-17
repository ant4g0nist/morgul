"""Self-contained HTML dashboard for the Morgul web display."""

DASHBOARD_HTML: str = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morgul Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg: #0d1117;
    --panel-bg: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --blue: #58a6ff;
    --cyan: #56d4dd;
    --yellow: #d29922;
    --magenta: #bc8cff;
    --orange: #d18616;
    --status-bg: #21262d;
    --keyword: #ff7b72;
    --string: #a5d6ff;
    --comment: #8b949e;
    --number: #79c0ff;
    --builtin: #d2a8ff;
}

html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Menlo', monospace;
    font-size: 13px;
    overflow: hidden;
}

.container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto 1fr auto;
    height: 100vh;
    gap: 1px;
    background: var(--border);
}

.top-bar {
    grid-column: 1 / -1;
    background: var(--panel-bg);
    padding: 6px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid var(--border);
}

.top-bar svg { flex-shrink: 0; }

.top-bar .brand {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--text);
}

.top-bar .tagline {
    font-size: 11px;
    color: var(--text-dim);
    margin-left: 4px;
}

.pane {
    background: var(--panel-bg);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.pane-header {
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.pane-header.lldb { color: var(--green); }
.pane-header.chat { color: var(--blue); }

.pane-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
}

.pane-content::-webkit-scrollbar { width: 6px; }
.pane-content::-webkit-scrollbar-track { background: transparent; }
.pane-content::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

.status-bar {
    grid-column: 1 / -1;
    background: var(--status-bg);
    padding: 4px 12px;
    font-size: 11px;
    color: var(--text-dim);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    background: var(--yellow);
}
.status-dot.connected { background: var(--green); }
.status-dot.disconnected { background: var(--red); }

/* Event styling */
.event { margin-bottom: 4px; line-height: 1.5; }
.event pre {
    margin: 4px 0;
    padding: 6px 8px;
    background: var(--bg);
    border-radius: 4px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    font-size: 12px;
}

.step-divider {
    margin: 8px 0;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 11px;
    border-radius: 3px;
}

.step-divider.code-step {
    color: var(--cyan);
    border-left: 3px solid var(--cyan);
    background: rgba(86, 212, 221, 0.05);
}

.step-divider.repl-step {
    color: var(--magenta);
    border-left: 3px solid var(--magenta);
    background: rgba(188, 140, 255, 0.05);
}

.step-divider.llm-step {
    color: var(--blue);
    border-left: 3px solid var(--blue);
    background: rgba(88, 166, 255, 0.05);
}

.stdout { color: var(--green); }
.stderr { color: var(--red); }
.ok { color: var(--green); font-weight: 600; }
.fail { color: var(--red); font-weight: 600; }
.dim { color: var(--text-dim); }
.heal { color: var(--yellow); font-weight: 600; }
.reasoning { color: var(--text); }
.llm-timing { color: var(--text-dim); font-size: 11px; }
.llm-thinking {
    color: var(--blue);
    font-size: 11px;
    font-style: italic;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.llm-indicator { animation: pulse 1.5s ease-in-out infinite; }
.error-msg { color: var(--red); font-weight: 600; }

/* Copy button */
.copy-wrap { position: relative; }
.copy-btn {
    position: absolute;
    top: 6px;
    right: 6px;
    background: var(--border);
    border: none;
    color: var(--text-dim);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 3px;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s;
    font-family: inherit;
    z-index: 1;
}
.copy-wrap:hover .copy-btn { opacity: 1; }
.copy-btn:hover { background: var(--text-dim); color: var(--bg); }
.copy-btn.copied { background: var(--green); color: var(--bg); opacity: 1; }

/* Markdown rendered content in chat pane */
.md-content { line-height: 1.6; }
.md-content p { margin: 4px 0; }
.md-content ul, .md-content ol { margin: 4px 0 4px 20px; }
.md-content li { margin: 2px 0; }
.md-content code {
    background: var(--bg);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
}
.md-content pre {
    background: var(--bg);
    padding: 8px 10px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 6px 0;
    font-size: 12px;
    position: relative;
}
.md-content pre code {
    background: none;
    padding: 0;
}
.md-content blockquote {
    border-left: 3px solid var(--border);
    padding-left: 10px;
    color: var(--text-dim);
    margin: 4px 0;
}
.md-content h1, .md-content h2, .md-content h3,
.md-content h4, .md-content h5, .md-content h6 {
    margin: 8px 0 4px;
    color: var(--text);
}
.md-content h1 { font-size: 16px; }
.md-content h2 { font-size: 14px; }
.md-content h3 { font-size: 13px; }
.md-content strong { color: var(--text); }
.md-content a { color: var(--blue); text-decoration: none; }
.md-content table { border-collapse: collapse; margin: 6px 0; width: 100%; }
.md-content th, .md-content td {
    border: 1px solid var(--border);
    padding: 4px 8px;
    text-align: left;
    font-size: 12px;
}
.md-content th { background: var(--bg); color: var(--text); }
.md-content hr { border: none; border-top: 1px solid var(--border); margin: 8px 0; }

/* Basic syntax highlighting for code blocks */
.kw { color: var(--keyword); }
.str { color: var(--string); }
.cmt { color: var(--comment); font-style: italic; }
.num { color: var(--number); }
.bi { color: var(--builtin); }
</style>
</head>
<body>
<div class="container">
    <div class="top-bar">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="24" height="24" aria-label="Morgul">
            <path d="M22 12V52M22 12H27M22 52H27" fill="none" stroke="#c9d1d9" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M42 12V52M37 12H42M37 52H42" fill="none" stroke="#c9d1d9" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M37 22H28L34 32L28 42H37" fill="none" stroke="#c9d1d9" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="brand">MORGUL</span>
        <span class="tagline">debugger automation</span>
    </div>
    <div class="pane">
        <div class="pane-header lldb">LLDB</div>
        <div class="pane-content" id="lldb"></div>
    </div>
    <div class="pane">
        <div class="pane-header chat">Chat</div>
        <div class="pane-content" id="chat"></div>
    </div>
    <div class="status-bar">
        <span style="display:flex;align-items:center;gap:6px;">
            <span class="status-dot" id="statusDot"></span><span id="statusText">connecting...</span>
        </span>
        <span id="statusInfo">step 0 | 0s</span>
    </div>
</div>
<script>
(function() {
    var lldbPane = document.getElementById('lldb');
    var chatPane = document.getElementById('chat');
    var statusDot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');
    var statusInfo = document.getElementById('statusInfo');

    var stepCount = 0;
    var startTime = Date.now();
    var sessionEnded = false;
    var activeLlmIndicator = null;

    function updateStatus() {
        var elapsed = Math.floor((Date.now() - startTime) / 1000);
        statusInfo.textContent = 'step ' + stepCount + ' | ' + elapsed + 's';
    }

    setInterval(updateStatus, 1000);

    // Track user-initiated scrolling via wheel/touch — not confused by programmatic scrolls
    var userScrolledUp = { lldb: false, chat: false };
    var programmaticScroll = { lldb: false, chat: false };

    function onUserScroll(pane, key) {
        // Ignore scroll events triggered by our own autoScroll
        if (programmaticScroll[key]) return;
        var gap = pane.scrollHeight - pane.scrollTop - pane.clientHeight;
        userScrolledUp[key] = gap > 50;
    }

    lldbPane.addEventListener('wheel', function() { onUserScroll(lldbPane, 'lldb'); });
    lldbPane.addEventListener('touchmove', function() { onUserScroll(lldbPane, 'lldb'); });
    chatPane.addEventListener('wheel', function() { onUserScroll(chatPane, 'chat'); });
    chatPane.addEventListener('touchmove', function() { onUserScroll(chatPane, 'chat'); });

    function autoScroll(el) {
        var key = el === lldbPane ? 'lldb' : 'chat';
        if (!userScrolledUp[key]) {
            programmaticScroll[key] = true;
            el.scrollTop = el.scrollHeight;
            // Clear flag after browser processes the scroll
            setTimeout(function() { programmaticScroll[key] = false; }, 50);
        }
    }

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // Render markdown if marked.js is loaded, otherwise fall back to escaped text
    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(text);
            } catch(e) {
                return escapeHtml(text);
            }
        }
        return escapeHtml(text);
    }

    function makeCopyBtn(getText) {
        var btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'copy';
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var text = getText();
            navigator.clipboard.writeText(text).then(function() {
                btn.textContent = 'copied';
                btn.classList.add('copied');
                setTimeout(function() {
                    btn.textContent = 'copy';
                    btn.classList.remove('copied');
                }, 1500);
            });
        });
        return btn;
    }

    // Add copy buttons to all <pre> blocks inside an element
    function addCopyButtons(el) {
        var pres = el.querySelectorAll('pre');
        for (var i = 0; i < pres.length; i++) {
            (function(pre) {
                pre.style.position = 'relative';
                var btn = makeCopyBtn(function() { return pre.textContent; });
                pre.appendChild(btn);
            })(pres[i]);
        }
    }

    // Typewriter effect for streaming text into an element
    var typewriterQueue = [];
    var typewriterRunning = false;

    function typewrite(el, text, pane, charDelay) {
        typewriterQueue.push({ el: el, text: text, pane: pane, charDelay: charDelay || 8 });
        if (!typewriterRunning) drainTypewriterQueue();
    }

    function flushTypewriterQueue() {
        // Immediately dump all remaining text — called on session_end
        typewriterRunning = false;
        while (typewriterQueue.length > 0) {
            var job = typewriterQueue.shift();
            job.el.innerHTML += escapeHtml(job.text);
            autoScroll(job.pane);
        }
    }

    function drainTypewriterQueue() {
        if (typewriterQueue.length === 0) { typewriterRunning = false; return; }
        typewriterRunning = true;
        var job = typewriterQueue.shift();
        var i = 0;
        var escaped = escapeHtml(job.text);
        function tick() {
            if (sessionEnded) { job.el.innerHTML += escaped.slice(i); flushTypewriterQueue(); return; }
            var chunk = escaped.slice(i, i + 4);
            job.el.innerHTML += chunk;
            i += 4;
            autoScroll(job.pane);
            if (i < escaped.length) {
                setTimeout(tick, job.charDelay);
            } else {
                drainTypewriterQueue();
            }
        }
        tick();
    }

    function highlightPython(code) {
        var escaped = escapeHtml(code);
        // Comments
        escaped = escaped.replace(/(#[^\\n]*)/g, '<span class="cmt">$1</span>');
        // Strings (simple single/double quotes)
        escaped = escaped.replace(/(&quot;[^&]*?&quot;|'[^']*?'|"[^"]*?")/g, '<span class="str">$1</span>');
        // Keywords
        var kws = ['import','from','def','class','return','if','elif','else','for','while',
                    'try','except','finally','with','as','yield','raise','pass','break',
                    'continue','and','or','not','in','is','None','True','False','async','await'];
        var kwRe = new RegExp('\\\\b(' + kws.join('|') + ')\\\\b', 'g');
        escaped = escaped.replace(kwRe, '<span class="kw">$1</span>');
        // Builtins
        var bis = ['print','len','range','int','str','list','dict','set','type','isinstance',
                    'hasattr','getattr','setattr','enumerate','zip','map','filter','sorted','hex'];
        var biRe = new RegExp('\\\\b(' + bis.join('|') + ')\\\\b', 'g');
        escaped = escaped.replace(biRe, '<span class="bi">$1</span>');
        // Numbers
        escaped = escaped.replace(/\\b(0x[0-9a-fA-F]+|\\d+\\.?\\d*)\\b/g, '<span class="num">$1</span>');
        return escaped;
    }

    function appendTo(pane, html) {
        var div = document.createElement('div');
        div.className = 'event';
        div.innerHTML = html;
        pane.appendChild(div);
        autoScroll(pane);
    }

    function handleEvent(data) {
        var t = data.type;
        var et = data.event_type;

        if (t === 'execution') {
            if (et === 'code_start') {
                stepCount++;
                updateStatus();
                var html = '<div class="step-divider code-step">step ' + stepCount + '</div>';
                if (data.code) {
                    html += '<pre><code>' + highlightPython(data.code) + '</code></pre>';
                }
                appendTo(lldbPane, html);

            } else if (et === 'code_end') {
                var cls = data.succeeded ? 'ok' : 'fail';
                var label = data.succeeded ? 'ok' : 'FAIL';
                var dur = (data.duration || 0).toFixed(2);
                var div = document.createElement('div');
                div.className = 'event';
                div.innerHTML = '<span class="' + cls + '">' + label + ' (' + dur + 's)</span>';
                if (data.stdout) {
                    var pre = document.createElement('pre');
                    pre.className = 'stdout';
                    div.appendChild(pre);
                    lldbPane.appendChild(div);
                    typewrite(pre, data.stdout, lldbPane, 4);
                } else {
                    lldbPane.appendChild(div);
                    autoScroll(lldbPane);
                }
                if (data.stderr) {
                    var errDiv = document.createElement('div');
                    errDiv.className = 'event';
                    errDiv.innerHTML = '<pre class="stderr">' + escapeHtml(data.stderr) + '</pre>';
                    lldbPane.appendChild(errDiv);
                    autoScroll(lldbPane);
                }

            } else if (et === 'heal_start') {
                var attempt = data.attempt || '?';
                var max_r = data.max_retries || '?';
                appendTo(lldbPane, '<span class="heal">heal ' + attempt + '/' + max_r + '</span>');

            } else if (et === 'heal_end') {
                if (data.succeeded) {
                    appendTo(lldbPane, '<span class="ok">healed</span>');
                } else {
                    var html = '<span class="fail">heal failed</span>';
                    if (data.stderr) {
                        html += '<pre class="stderr">' + escapeHtml(data.stderr) + '</pre>';
                    }
                    appendTo(lldbPane, html);
                }

            } else if (et === 'repl_step') {
                var step = data.step || '?';
                var max_i = data.max_iterations || '?';
                appendTo(lldbPane, '<div class="step-divider repl-step">repl ' + step + '/' + max_i + '</div>');
                // Reset the LLM indicator for the new step
                activeLlmIndicator = null;
                appendTo(chatPane, '<div class="step-divider repl-step">step ' + step + '/' + max_i + '</div>');

            } else if (et === 'llm_response') {
                if (data.content) {
                    var div = document.createElement('div');
                    div.className = 'event copy-wrap';
                    var inner = document.createElement('div');
                    inner.className = 'md-content';
                    inner.innerHTML = renderMarkdown(data.content);
                    // Copy button for the whole message
                    div.appendChild(makeCopyBtn(function() { return data.content; }));
                    div.appendChild(inner);
                    // Copy buttons on individual code blocks
                    addCopyButtons(inner);
                    chatPane.appendChild(div);
                    autoScroll(chatPane);
                }
            }

        } else if (t === 'llm') {
            if (data.is_start) {
                var label = data.model_type || data.method || 'llm';
                // Create or reuse the thinking indicator — updates in-place
                if (!activeLlmIndicator) {
                    activeLlmIndicator = document.createElement('div');
                    activeLlmIndicator.className = 'event llm-indicator';
                    chatPane.appendChild(activeLlmIndicator);
                }
                activeLlmIndicator.innerHTML = '<span class="llm-thinking">thinking (' + escapeHtml(label) + ')...</span>';
                activeLlmIndicator.style.display = '';
                autoScroll(chatPane);
            } else {
                if (data.error) {
                    appendTo(chatPane, '<div class="error-msg">error: ' + escapeHtml(data.error) + '</div>');
                } else {
                    var info = (data.duration || 0).toFixed(1) + 's';
                    if (data.input_tokens != null) {
                        info += ' | ' + data.input_tokens + '+' + data.output_tokens + ' tok';
                    }
                    // Update the indicator with the result instead of appending
                    if (activeLlmIndicator) {
                        activeLlmIndicator.innerHTML = '<span class="llm-timing">' + info + '</span>';
                    }
                }
                activeLlmIndicator = null;
            }

        } else if (t === 'init') {
            startTime = Date.now();
            stepCount = 0;
            updateStatus();

        } else if (t === 'session_end') {
            sessionEnded = true;
            // Flush any remaining typewriter text immediately
            flushTypewriterQueue();
            statusDot.className = 'status-dot';
            statusDot.style.background = '#8b949e';
            statusText.textContent = 'session ended';
            if (evtSource) { evtSource.close(); }
            var elapsed = Math.floor((Date.now() - startTime) / 1000);
            var mins = Math.floor(elapsed / 60);
            var secs = elapsed % 60;
            var timeStr = mins > 0 ? mins + 'm ' + secs + 's' : secs + 's';
            appendTo(lldbPane, '<div class="step-divider code-step">session ended — ' + stepCount + ' steps, ' + timeStr + '</div>');
        }
    }

    // SSE connection
    var evtSource;

    function connect() {
        if (sessionEnded) return;
        evtSource = new EventSource('/events');

        evtSource.onopen = function() {
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'connected';
        };

        evtSource.onmessage = function(e) {
            try {
                var data = JSON.parse(e.data);
                handleEvent(data);
            } catch(err) {
                console.error('parse error:', err, e.data);
            }
        };

        evtSource.onerror = function() {
            if (sessionEnded) {
                evtSource.close();
                return;
            }
            statusDot.className = 'status-dot disconnected';
            statusText.textContent = 'disconnected — reconnecting...';
        };
    }

    connect();
})();
</script>
</body>
</html>
"""
