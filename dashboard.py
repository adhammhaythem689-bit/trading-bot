"""
Local dashboard for the paper trading bot.

This is a website, but a LOCAL one: it only runs on your own machine at
http://127.0.0.1:5000, nobody else on the internet can see it. It just reads
the state/log files the paper trader (06_paper_trade.py) writes and displays
them, it doesn't control the bot.

Run it with:  python dashboard.py
Then open:    http://127.0.0.1:5000  in your browser
"""
from flask import Flask, jsonify, render_template_string
import json
import os
import pandas as pd

app = Flask(__name__)

STATE_FILE = "paper_state.json"
LOG_FILE = "paper_trade_log.csv"

PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Trading Bot Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body { font-family: -apple-system, Segoe UI, Arial, sans-serif; background: #0f1115; color: #e8e8e8; margin: 0; padding: 24px; }
        h1 { font-size: 20px; color: #fff; }
        .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
        .card { background: #1a1d24; border-radius: 10px; padding: 16px 20px; min-width: 150px; }
        .card .label { font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
        .card .value { font-size: 24px; font-weight: 600; margin-top: 4px; }
        .pos { color: #4ade80; }
        .neg { color: #f87171; }
        .halted { background: #3a1a1a; border: 1px solid #f87171; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
        th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #262a33; }
        th { color: #999; text-transform: uppercase; font-size: 11px; }
        #chart-container { background: #1a1d24; border-radius: 10px; padding: 16px; margin-bottom: 24px; }
        .note { color: #999; font-size: 12px; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>Paper Trading Bot &mdash; BTC/USDT (MA crossover + risk management)</h1>
    <p class="note">Running locally on this machine only. Auto-refreshes every 30s.</p>

    <div class="cards" id="cards"></div>

    <div id="chart-container">
        <canvas id="equityChart" height="90"></canvas>
    </div>

    <div id="chart-container">
        <h3 style="margin-top:0; font-size:14px; color:#999;">Recent events</h3>
        <table id="logTable">
            <thead><tr><th>Time</th><th>Event</th><th>Price</th><th>Equity</th><th>Note</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>

    <script>
        let chart;
        async function refresh() {
            const res = await fetch('/api/status');
            const data = await res.json();

            const cardsEl = document.getElementById('cards');
            const pnlClass = data.return_pct >= 0 ? 'pos' : 'neg';
            cardsEl.innerHTML = `
                <div class="card"><div class="label">Equity</div><div class="value">$${data.equity.toFixed(2)}</div></div>
                <div class="card"><div class="label">Return</div><div class="value ${pnlClass}">${data.return_pct >= 0 ? '+' : ''}${data.return_pct.toFixed(2)}%</div></div>
                <div class="card"><div class="label">Position</div><div class="value">${data.in_position ? 'LONG' : 'FLAT'}</div></div>
                <div class="card ${data.trading_halted ? 'halted' : ''}"><div class="label">Status</div><div class="value">${data.trading_halted ? 'HALTED' : 'Active'}</div></div>
                <div class="card"><div class="label">Last price</div><div class="value">$${data.last_price ? data.last_price.toFixed(2) : '--'}</div></div>
            `;

            const labels = data.history.map(h => h.timestamp);
            const equity = data.history.map(h => h.equity);
            if (!chart) {
                const ctx = document.getElementById('equityChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: labels, datasets: [{ label: 'Equity ($)', data: equity, borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.1)', fill: true, tension: 0.2, pointRadius: 0 }] },
                    options: { responsive: true, plugins: { legend: { labels: { color: '#ccc' } } },
                        scales: { x: { ticks: { color: '#888', maxTicksLimit: 8 } }, y: { ticks: { color: '#888' } } } }
                });
            } else {
                chart.data.labels = labels;
                chart.data.datasets[0].data = equity;
                chart.update();
            }

            const tbody = document.querySelector('#logTable tbody');
            tbody.innerHTML = data.recent_events.slice().reverse().map(e => `
                <tr><td>${e.timestamp}</td><td>${e.event}</td><td>$${parseFloat(e.price).toFixed(2)}</td><td>$${parseFloat(e.equity).toFixed(2)}</td><td>${e.note}</td></tr>
            `).join('');
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
    state = {"cash": 1000.0, "btc": 0.0, "in_position": False, "trading_halted": False}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

    history = []
    recent_events = []
    last_price = None
    if os.path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        history = log_df[["timestamp", "equity"]].to_dict("records")
        recent_events = log_df.tail(20).to_dict("records")
        if len(log_df):
            last_price = float(log_df["price"].iloc[-1])

    equity = state["cash"] + state["btc"] * (last_price or 0)
    return_pct = (equity - 1000.0) / 1000.0 * 100

    return jsonify({
        "equity": equity,
        "return_pct": return_pct,
        "in_position": state["in_position"],
        "trading_halted": state["trading_halted"],
        "last_price": last_price,
        "history": history,
        "recent_events": recent_events,
    })


if __name__ == "__main__":
    print("\nDashboard running at http://127.0.0.1:5000 (local only)\n")
    app.run(debug=False, port=5000)
