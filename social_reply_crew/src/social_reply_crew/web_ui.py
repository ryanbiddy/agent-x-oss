from __future__ import annotations

"""
Local web UI for Agent X digest.
Run with: social-reply-crew ui
Opens at http://localhost:7842
"""

import threading
import webbrowser

from flask import Flask, jsonify, render_template_string, request

from social_reply_crew.db import save_approved_reply
from social_reply_crew.digest import get_refined_reply
from social_reply_crew.memory_store import load_memory_context
from social_reply_crew.voice_intake import get_voice_context_for_prompt

app = Flask(__name__)

_session_state = {
    "tweets": [],
    "current_index": 0,
    "approved": [],
    "skipped": [],
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Agent X Digest</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'IBM Plex Mono', 'Courier New', monospace; background: #0a0a0a; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  header { padding: 12px 24px; border-bottom: 1px solid #1e1e1e; display: flex; align-items: center; gap: 12px; }
  .dot { width: 7px; height: 7px; background: #3b82f6; border-radius: 50%; }
  .title { font-size: 12px; font-weight: 600; letter-spacing: 0.1em; }
  .subtitle { font-size: 11px; color: #555; }
  .stats { margin-left: auto; display: flex; gap: 20px; font-size: 11px; color: #555; }
  .stats span { color: #3b82f6; }
  .main { display: flex; flex: 1; overflow: hidden; }
  .queue { width: 280px; border-right: 1px solid #1e1e1e; overflow-y: auto; padding: 12px; }
  .queue-item { padding: 10px 12px; border-radius: 6px; border: 1px solid #1e1e1e; margin-bottom: 8px; cursor: pointer; }
  .queue-item:hover { border-color: #3b82f6; }
  .queue-item.active { border-color: #3b82f6; background: #0d1f3c; }
  .queue-item.done { opacity: 0.4; }
  .queue-handle { font-size: 11px; color: #3b82f6; font-weight: 600; }
  .queue-preview { font-size: 11px; color: #666; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .queue-score { font-size: 10px; color: #444; margin-top: 4px; }
  .center { flex: 1; padding: 24px; overflow-y: auto; }
  .context-card { background: #111; border: 1px solid #1e1e1e; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
  .context-handle { font-size: 14px; font-weight: 600; color: #3b82f6; }
  .context-meta { display: flex; gap: 16px; margin-top: 6px; font-size: 11px; color: #666; }
  .context-bio { font-size: 12px; color: #888; margin-top: 6px; line-height: 1.5; }
  .context-interaction { font-size: 11px; margin-top: 8px; padding-top: 8px; border-top: 1px solid #1e1e1e; color: #555; }
  .why-surfaced { display: inline-block; background: #0d1f3c; color: #60a5fa; font-size: 10px; padding: 2px 8px; border-radius: 4px; margin-top: 6px; }
  .tweet-box { background: #111; border: 1px solid #1e1e1e; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
  .tweet-label { font-size: 10px; color: #555; letter-spacing: 0.1em; margin-bottom: 8px; }
  .tweet-text { font-size: 13px; line-height: 1.6; color: #ccc; }
  .tweet-link { font-size: 11px; color: #3b82f6; margin-top: 6px; display: block; }
  .reply-options { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }
  .reply-card { background: #111; border: 1px solid #1e1e1e; border-radius: 8px; padding: 16px; }
  .reply-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .reply-label { font-size: 10px; color: #555; letter-spacing: 0.1em; }
  .char-count { font-size: 10px; }
  .char-ok { color: #22c55e; }
  .char-warn { color: #f59e0b; }
  .char-over { color: #ef4444; }
  .reply-text { font-size: 13px; line-height: 1.6; color: #e0e0e0; margin-bottom: 12px; }
  .reply-why { font-size: 11px; color: #555; margin-bottom: 12px; }
  .reply-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .btn { padding: 6px 14px; border-radius: 5px; border: none; cursor: pointer; font-family: inherit; font-size: 11px; letter-spacing: 0.05em; }
  .btn-approve { background: #3b82f6; color: white; }
  .btn-tune { background: none; border: 1px solid #333; color: #888; }
  .btn-tune:hover { border-color: #3b82f6; color: #3b82f6; }
  .tune-bar { background: #0f0f0f; border: 1px solid #1e1e1e; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }
  .tune-label { font-size: 10px; color: #555; letter-spacing: 0.1em; margin-bottom: 8px; }
  .tune-btns { display: flex; gap: 6px; flex-wrap: wrap; }
  .skip-btn { padding: 8px 16px; background: none; border: 1px solid #1e1e1e; border-radius: 6px; color: #555; cursor: pointer; font-family: inherit; font-size: 11px; }
  .skip-btn:hover { border-color: #555; color: #888; }
  .sidebar { width: 220px; border-left: 1px solid #1e1e1e; padding: 16px; overflow-y: auto; }
  .sidebar-section { margin-bottom: 20px; }
  .sidebar-label { font-size: 10px; color: #555; letter-spacing: 0.1em; margin-bottom: 8px; }
  .sidebar-stat { font-size: 22px; font-weight: 500; color: #e0e0e0; }
  .sidebar-sub { font-size: 11px; color: #555; margin-top: 2px; }
  .approved-item { font-size: 11px; color: #888; padding: 6px 0; border-bottom: 1px solid #1a1a1a; line-height: 1.4; }
</style>
</head>
<body>
<header>
  <div class="dot"></div>
  <span class="title">AGENT X</span>
  <span class="subtitle">/ daily digest</span>
  <div class="stats">
    <div>Queue: <span id="queue-count">0</span></div>
    <div>Approved: <span id="approved-count">0</span></div>
    <div>Skipped: <span id="skipped-count">0</span></div>
  </div>
</header>

<div class="main">
  <div class="queue" id="tweet-queue">
    <div style="font-size:10px;color:#555;letter-spacing:0.1em;margin-bottom:12px;">TWEET QUEUE</div>
  </div>
  <div class="center" id="main-panel">
    <div style="text-align:center;padding:60px 0;color:#444;font-size:13px;">
      Loading digest...
    </div>
  </div>
  <div class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-label">APPROVED</div>
      <div class="sidebar-stat" id="stat-approved">0</div>
      <div class="sidebar-sub">this session</div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-label">RECENT PICKS</div>
      <div id="approved-list"></div>
    </div>
  </div>
</div>

<script>
let state = { tweets: [], currentIdx: 0, approved: [], skipped: [] };
const tuneMap = {
  f: 'Funnier',
  t: 'Technical',
  s: 'Shorter',
  p: 'Personal',
  b: 'Bolder',
  r: 'Rewrite'
};

async function loadDigest() {
  const res = await fetch('/api/digest');
  const data = await res.json();
  state.tweets = data.tweets || [];
  renderQueue();
  if (state.tweets.length > 0) renderTweet(0);
  updateStats();
}

function renderQueue() {
  const el = document.getElementById('tweet-queue');
  const items = state.tweets.map((t, i) => `
    <div class="queue-item ${i === state.currentIdx ? 'active' : ''} ${state.skipped.includes(i) || state.approved.find(a => a.idx === i) ? 'done' : ''}"
         onclick="renderTweet(${i})">
      <div class="queue-handle">${t.handle}</div>
      <div class="queue-preview">${(t.text || '').substring(0, 55)}...</div>
      <div class="queue-score">score: ${t.score || '-'}</div>
    </div>
  `).join('');
  el.innerHTML = '<div style="font-size:10px;color:#555;letter-spacing:0.1em;margin-bottom:12px;">TWEET QUEUE</div>' + items;
  document.getElementById('queue-count').textContent = state.tweets.length;
}

function charClass(n) {
  return n > 280 ? 'char-over' : n > 240 ? 'char-warn' : 'char-ok';
}

function renderTweet(idx) {
  state.currentIdx = idx;
  const t = state.tweets[idx];
  if (!t) return;
  const ctx = t.user_context || {};
  const inter = t.interaction || {};

  document.getElementById('main-panel').innerHTML = `
    <div class="context-card">
      <div class="context-handle">${t.handle}</div>
      <div class="context-meta">
        ${ctx.followers && ctx.followers !== 'unknown' ? `<span>Followers: ${ctx.followers}</span>` : ''}
        ${t.score ? `<span>Score: ${t.score}</span>` : ''}
      </div>
      ${ctx.bio ? `<div class="context-bio">${ctx.bio}</div>` : ''}
      <div class="context-interaction">
        ${inter.replied_before
          ? `Replied ${inter.total_replies}x - last: ${(inter.last_reply_date || '').substring(0, 10)}`
          : 'First time replying to this account'}
      </div>
      ${t.why_surfaced ? `<div class="why-surfaced">${t.why_surfaced}</div>` : ''}
    </div>

    <div class="tweet-box">
      <div class="tweet-label">ORIGINAL TWEET</div>
      <div class="tweet-text">${t.text}</div>
      ${t.link ? `<a class="tweet-link" href="${t.link}" target="_blank">${t.link}</a>` : ''}
    </div>

    <div class="tune-bar">
      <div class="tune-label">FINE-TUNE</div>
      <div class="tune-btns">
        ${Object.entries(tuneMap).map(([code, label]) =>
          `<button class="btn btn-tune" onclick="tuneReply(${idx}, '${code}')">${label}</button>`
        ).join('')}
      </div>
    </div>

    <div class="reply-options">
      ${(t.replies || []).map((r, i) => `
        <div class="reply-card">
          <div class="reply-header">
            <span class="reply-label">OPTION ${i + 1}</span>
            <span class="char-count ${charClass((r.text || '').length)}">${(r.text || '').length}/280</span>
          </div>
          <div class="reply-text">${r.text || ''}</div>
          ${r.why ? `<div class="reply-why">${r.why}</div>` : ''}
          <div class="reply-actions">
            <button class="btn btn-approve" onclick="approveReply(${idx}, ${i})">Approve</button>
          </div>
        </div>
      `).join('')}
    </div>

    <button class="skip-btn" onclick="skipTweet(${idx})">Skip</button>
  `;
  renderQueue();
}

async function tuneReply(tweetIdx, modifier) {
  const t = state.tweets[tweetIdx];
  const res = await fetch('/api/tune', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ tweet_text: t.text, replies: t.replies, modifier })
  });
  const data = await res.json();
  if (data.refined) {
    state.tweets[tweetIdx].replies = data.refined;
    renderTweet(tweetIdx);
  }
}

async function approveReply(tweetIdx, replyIdx) {
  const t = state.tweets[tweetIdx];
  const reply = t.replies[replyIdx];
  state.approved.push({ idx: tweetIdx, handle: t.handle, reply: reply.text });
  await fetch('/api/approve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ tweet: t, reply: reply.text })
  });
  updateStats();
  renderQueue();
  const next = state.tweets.findIndex((_, i) =>
    i > tweetIdx && !state.skipped.includes(i) && !state.approved.find(a => a.idx === i)
  );
  if (next >= 0) renderTweet(next);
}

function skipTweet(idx) {
  if (!state.skipped.includes(idx)) state.skipped.push(idx);
  const next = state.tweets.findIndex((_, i) =>
    i > idx && !state.skipped.includes(i) && !state.approved.find(a => a.idx === i)
  );
  if (next >= 0) renderTweet(next);
  updateStats();
  renderQueue();
}

function updateStats() {
  document.getElementById('stat-approved').textContent = state.approved.length;
  document.getElementById('approved-count').textContent = state.approved.length;
  document.getElementById('skipped-count').textContent = state.skipped.length;
  const list = document.getElementById('approved-list');
  list.innerHTML = state.approved.slice(-5).reverse().map(a => `
    <div class="approved-item"><strong>${a.handle}</strong><br>${a.reply.substring(0, 60)}...</div>
  `).join('');
}

loadDigest();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/digest")
def get_digest():
    return jsonify({"tweets": _session_state["tweets"]})


@app.route("/api/approve", methods=["POST"])
def approve_reply():
    data = request.json or {}
    tweet = data.get("tweet", {})
    reply = data.get("reply", "")
    try:
        save_approved_reply(
            source_handle=tweet.get("handle", ""),
            tweet_url=tweet.get("link", ""),
            tweet_text=tweet.get("text", ""),
            reply_text=reply,
        )
    except Exception:
        return jsonify({"ok": False}), 500
    return jsonify({"ok": True})


@app.route("/api/tune", methods=["POST"])
def tune_reply():
    data = request.json or {}
    modifier = data.get("modifier", "r")
    tweet_text = data.get("tweet_text", "")
    current_replies = data.get("replies", [])
    voice_context = get_voice_context_for_prompt(load_memory_context())

    refined = []
    for reply in current_replies:
        refined_text = get_refined_reply(
            original_tweet=tweet_text,
            current_reply=reply.get("text", ""),
            modifier=modifier,
            voice_context=voice_context,
        )
        refined.append(
            {
                "text": refined_text,
                "why": f"Refined: {modifier}",
                "style_label": reply.get("style_label", "Refined"),
            }
        )

    return jsonify({"refined": refined})


def load_session_tweets(tweets: list) -> None:
    """Load tweets into the web UI session."""
    _session_state["tweets"] = tweets
    _session_state["current_index"] = 0
    _session_state["approved"] = []
    _session_state["skipped"] = []


def start_ui(port: int = 7842, open_browser: bool = True) -> None:
    """Start the web UI server."""
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"\nAgent X UI running at http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")
    app.run(port=port, debug=False, use_reloader=False)
