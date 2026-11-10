"""
Local dashboard for the paper trading bot.

This is a website, but a LOCAL one: it only runs on your own machine at
http://127.0.0.1:5000, nobody else on the internet can see it. It just reads
the state/log files the paper trader (06_paper_trade.py) writes and displays
them, it doesn't control the bot.

Written for someone who does NOT read code: plain-English labels, no raw
jargon like "volatility=low" or win-rate tables. If you want the full
technical detail, read learned_filters.json / paper_trade_log.csv directly.

Run it with:  python dashboard.py
Then open:    http://127.0.0.1:5000  in your browser
"""
from flask import Flask, jsonify, render_template_string
import json
import os
import re
import pandas as pd
from engine.config import DEFAULT_CONFIG

app = Flask(__name__)

STATE_FILE = "paper_state.json"
LOG_FILE = "paper_trade_log.csv"
LEARNED_FILTERS_FILE = "learned_filters.json"
RELEARN_HISTORY_FILE = "relearn_history.csv"
LATEST_DAILY_RUNLOG = os.path.join("runlog", "latest_daily.json")

# condition_combo() in engine/features.py only bins on volatility right now
# (see that file's own comment for why). If it ever adds another dimension,
# an unrecognized combo string just falls back to showing itself as-is below.
FRIENDLY_BUCKET_NAMES = {
    "volatility=low": "Calm market days",
    "volatility=medium": "Normal market days",
    "volatility=high": "Wild, swingy days",
}

PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Trading Bot Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body { font-family: -apple-system, Segoe UI, Arial, sans-serif; background: #0f1115; color: #e8e8e8; margin: 0; padding: 24px; max-width: 900px; }
        h1 { font-size: 22px; color: #fff; margin-bottom: 2px; }
        h2 { font-size: 16px; color: #fff; margin: 0 0 4px; }
        .subtitle { color: #999; font-size: 13px; margin-top: 0; margin-bottom: 24px; }
        .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
        .card { background: #1a1d24; border-radius: 10px; padding: 18px 22px; min-width: 170px; flex: 1; }
        .card .label { font-size: 13px; color: #999; }
        .card .value { font-size: 28px; font-weight: 700; margin-top: 6px; }
        .card .sub { font-size: 12px; color: #999; margin-top: 4px; }
        .pos { color: #4ade80; }
        .neg { color: #f87171; }
        .warn { color: #fbbf24; }
        .halted { background: #3a1a1a; border: 1px solid #f87171; }
        .section { background: #1a1d24; border-radius: 10px; padding: 18px 22px; margin-bottom: 20px; }
        .big-verdict { font-size: 17px; line-height: 1.5; }
        .badges { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
        .badge { background: #12151b; border-radius: 8px; padding: 12px 16px; min-width: 150px; flex: 1; }
        .badge .name { font-size: 13px; color: #ccc; margin-bottom: 6px; }
        .badge .status { font-size: 14px; font-weight: 600; }
        .activity-row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid #262a33; font-size: 13px; }
        .activity-row:last-child { border-bottom: none; }
        .activity-time { color: #777; font-size: 12px; white-space: nowrap; }
        .activity-desc { flex: 2; }
        .activity-amount { text-align: right; white-space: nowrap; }
        .note { color: #999; font-size: 12px; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>Your Trading Bot</h1>
    <p class="subtitle">Paper trading (fake money, real market prices) on Bitcoin. Updates every 30 seconds.</p>

    <div class="cards" id="cards"></div>

    <div class="section">
        <h2>Money over time</h2>
        <canvas id="equityChart" height="80"></canvas>
    </div>

    <div class="section">
        <h2>Is it learning?</h2>
        <p class="big-verdict" id="learningVerdict"></p>
        <div class="badges" id="learningBadges"></div>
    </div>

    <div class="section">
        <h2>What it's been doing</h2>
        <div id="activityList"></div>
    </div>

    <script>
        let chart;

        function fmtMoney(n) { return '$' + n.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

        async function refresh() {
            const res = await fetch('/api/status');
            const data = await res.json();

            const pnlClass = data.return_pct >= 0 ? 'pos' : 'neg';
            const statusText = data.trading_halted ? 'Stopped (lost too much, paused for safety)' : 'Running normally';
            const positionText = data.in_position ? 'Holding Bitcoin right now' : 'Waiting on the sidelines (cash)';

            document.getElementById('cards').innerHTML = `
                <div class="card">
                    <div class="label">Account is worth</div>
                    <div class="value">${fmtMoney(data.equity)}</div>
                    <div class="sub ${pnlClass}">${data.return_pct >= 0 ? '+' : ''}${data.return_pct.toFixed(1)}% since it started with $1,000</div>
                </div>
                <div class="card">
                    <div class="label">Right now</div>
                    <div class="value" style="font-size:18px;">${positionText}</div>
                    <div class="sub">Bitcoin price: ${data.last_price ? fmtMoney(data.last_price) : '--'}</div>
                </div>
                <div class="card ${data.trading_halted ? 'halted' : ''}">
                    <div class="label">Status</div>
                    <div class="value ${data.trading_halted ? 'neg' : 'pos'}" style="font-size:18px;">${statusText}</div>
                </div>
            `;

            const labels = data.history.map(h => h.timestamp);
            const equity = data.history.map(h => h.equity);
            if (!chart) {
                const ctx = document.getElementById('equityChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: labels, datasets: [{ label: 'Account value ($)', data: equity, borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.1)', fill: true, tension: 0.2, pointRadius: 0 }] },
                    options: { responsive: true, plugins: { legend: { display: false } },
                        scales: { x: { ticks: { color: '#888', maxTicksLimit: 6 } }, y: { ticks: { color: '#888' } } } }
                });
            } else {
                chart.data.labels = labels;
                chart.data.datasets[0].data = equity;
                chart.update();
            }

            const learning = data.learning;
            if (learning.bucket_count === 0) {
                document.getElementById('learningVerdict').textContent =
                    "Not enough trade history yet to say anything about this.";
            } else if (learning.reliable_count === 0) {
                document.getElementById('learningVerdict').innerHTML =
                    `Still learning &mdash; it needs at least ${learning.min_samples} real trades in a type of market `
                    + `before it trusts what it has seen. None of its ${learning.bucket_count} market types have enough yet.`;
            } else {
                document.getElementById('learningVerdict').innerHTML =
                    `Making progress &mdash; it now trusts ${learning.reliable_count} of ${learning.bucket_count} market types `
                    + `(based on ${learning.min_samples}+ real trades each).`;
            }

            document.getElementById('learningBadges').innerHTML = learning.buckets.map(b => {
                let statusText, statusClass;
                if (!b.reliable) { statusText = 'Still watching, not trusted yet'; statusClass = ''; }
                else if (b.avg_pnl_pct >= 0) { statusText = 'Profitable so far'; statusClass = 'pos'; }
                else { statusText = 'Losing money so far'; statusClass = 'neg'; }
                return `<div class="badge">
                    <div class="name">${b.name}</div>
                    <div class="status ${statusClass}">${statusText}</div>
                </div>`;
            }).join('');

            document.getElementById('activityList').innerHTML = data.recent_events.slice().reverse().map(e => `
                <div class="activity-row">
                    <div class="activity-time">${e.timestamp}</div>
                    <div class="activity-desc">${e.description}</div>
                    <div class="activity-amount ${e.pnl_class}">${e.amount}</div>
                </div>
            `).join('') || '<p class="note">No activity recorded yet.</p>';
        }
        refresh();
        setInterval(refresh, 30000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/status")
def status():
    state = {"cash": DEFAULT_CONFIG.starting_balance, "btc": 0.0, "in_position": False, "trading_halted": False}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

    history = []
    recent_events = []
    last_price = None
    if os.path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        history = log_df[["timestamp", "equity"]].to_dict("records")
        recent_events = [_describe_event(row) for row in log_df.tail(15).to_dict("records")]
        if len(log_df):
            last_price = float(log_df["price"].iloc[-1])

    equity = state["cash"] + state["btc"] * (last_price or 0)
    start = DEFAULT_CONFIG.starting_balance
    return_pct = (equity - start) / start * 100

    return jsonify({
        "equity": equity,
        "return_pct": return_pct,
        "in_position": state["in_position"],
        "trading_halted": state["trading_halted"],
        "last_price": last_price,
        "history": history,
        "recent_events": recent_events,
        "learning": _learning_status(),
    })


def _describe_event(row):
    """Turn one raw log row's technical `note` into a plain-English activity line."""
    note = str(row.get("note", "")).split(" | ")[0]  # drop the trailing news/fear_greed tag
    price = float(row["price"])
    timestamp = row["timestamp"]

    pnl_match = re.search(r"pnl ([+-]?\d+\.?\d*)%", note)
    pnl = float(pnl_match.group(1)) if pnl_match else None

    if note.startswith("BUY"):
        description, amount, pnl_class = f"Bought Bitcoin at ${price:,.0f}", "", ""
    elif note.startswith("SELL"):
        description = f"Sold Bitcoin at ${price:,.0f}"
        amount = f"{pnl:+.1f}%" if pnl is not None else ""
        pnl_class = "pos" if (pnl or 0) >= 0 else "neg"
    elif note.startswith("STOP-LOSS"):
        description = f"Safety stop: sold at ${price:,.0f} to limit the loss"
        amount = f"{pnl:+.1f}%" if pnl is not None else ""
        pnl_class = "neg"
    elif note.startswith("KILL_SWITCH"):
        description, amount, pnl_class = "Paused trading — losses got too big", "", "warn"
    elif note.startswith("SKIPPED"):
        description, amount, pnl_class = "Skipped a trade — this market pattern looked unreliable", "", ""
    elif note == "hold":
        description, amount, pnl_class = "No action — just watching the market", "", ""
    else:
        description, amount, pnl_class = note, "", ""

    return {"timestamp": timestamp, "description": description, "amount": amount, "pnl_class": pnl_class}


def _learning_status():
    buckets = []
    if os.path.exists(LEARNED_FILTERS_FILE):
        with open(LEARNED_FILTERS_FILE) as f:
            learned = json.load(f)
        buckets = [
            {"name": FRIENDLY_BUCKET_NAMES.get(combo, combo), **info}
            for combo, info in learned.items()
        ]
        buckets.sort(key=lambda b: b["n"], reverse=True)

    return {
        "buckets": buckets,
        "bucket_count": len(buckets),
        "reliable_count": sum(1 for b in buckets if b["reliable"]),
        "min_samples": DEFAULT_CONFIG.min_samples,
    }


if __name__ == "__main__":
    print("\nDashboard running at http://127.0.0.1:5000 (local only)\n")
    app.run(debug=False, port=5000)
