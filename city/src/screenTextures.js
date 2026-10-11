// Draws department-specific monitor content onto a canvas, used as a texture
// on the in-room monitor mesh. All values come from the real city_data.json
// passed in, nothing here is invented -- an empty/idle department draws an
// honest "No data yet" screen instead of a fake chart.
import * as THREE from "three";

function baseCtx(w = 512, h = 320) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#070a12";
  ctx.fillRect(0, 0, w, h);
  return { canvas, ctx, w, h };
}

function drawHeader(ctx, title, color) {
  ctx.fillStyle = color;
  ctx.font = "bold 22px monospace";
  ctx.fillText(title, 16, 32);
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.5;
  ctx.beginPath();
  ctx.moveTo(16, 42);
  ctx.lineTo(496, 42);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function drawLine(ctx, label, value, y, color = "#e5e7eb") {
  ctx.fillStyle = "#9ca3af";
  ctx.font = "14px monospace";
  ctx.fillText(label, 16, y);
  ctx.fillStyle = color;
  ctx.font = "bold 16px monospace";
  ctx.fillText(String(value), 260, y);
}

function drawEmptyState(ctx, w, h, message) {
  ctx.fillStyle = "#4b5563";
  ctx.font = "16px monospace";
  ctx.fillText(message, 16, h / 2);
}

function drawSparkline(ctx, values, x, y, w, h, color) {
  if (!values || values.length < 2) return;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const px = x + (i / (values.length - 1)) * w;
    const py = y + h - ((v - min) / range) * h;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.08;
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x, y + h);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;
}

function buildTexture(canvas) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function drawBacktestingScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  drawHeader(ctx, "BACKTEST // " + (data.strategy_name || "---"), color);
  if (!data.metrics) {
    drawEmptyState(ctx, w, h, "No backtest run yet.");
    return buildTexture(canvas);
  }
  drawLine(ctx, "VERSION", data.strategy_version, 70);
  drawLine(ctx, "RETURN", data.metrics.return_pct + "%", 92,
    data.metrics.return_pct >= 0 ? "#34d399" : "#f87171");
  drawLine(ctx, "TRADES", data.metrics.num_trades, 114);
  drawLine(ctx, "WIN RATE", data.metrics.win_rate + "%", 136);
  drawLine(ctx, "MAX DRAWDOWN", data.metrics.max_drawdown_pct + "%", 158, "#f87171");
  drawLine(ctx, "BUY & HOLD", data.buy_and_hold_pct + "%", 180);
  drawSparkline(ctx, data.equity_sparkline, 16, 210, w - 32, 90, color);
  return buildTexture(canvas);
}

export function drawDataScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  drawHeader(ctx, "DATA FEED // " + (data.source || "---"), color);
  if (!data.candle_count) {
    drawEmptyState(ctx, w, h, "No dataset loaded yet.");
    return buildTexture(canvas);
  }
  drawLine(ctx, "CANDLES", data.candle_count, 70);
  drawLine(ctx, "EARLIEST", data.earliest_candle, 92);
  drawLine(ctx, "LATEST", data.latest_candle, 114);
  drawLine(ctx, "WARNINGS", data.warnings?.length || 0, 136, data.warnings?.length ? "#fbbf24" : "#34d399");
  (data.warnings || []).slice(0, 4).forEach((wmsg, i) => {
    ctx.fillStyle = "#fbbf24";
    ctx.font = "11px monospace";
    ctx.fillText("! " + wmsg.slice(0, 48), 16, 162 + i * 16);
  });
  return buildTexture(canvas);
}

export function drawValidationScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  drawHeader(ctx, "VALIDATION // TRAIN-TEST SPLIT", color);
  if (!data.method) {
    drawEmptyState(ctx, w, h, "No validation run yet.");
    return buildTexture(canvas);
  }
  drawLine(ctx, "METHOD", data.method, 70);
  drawLine(ctx, "BEST COMBO", data.best_training_combo, 92);
  drawLine(ctx, "TRAIN RETURN", data.training_return_pct + "%", 114);
  drawLine(ctx, "STATUS", (data.status || "").toUpperCase(), 136, "#fbbf24");
  ctx.fillStyle = "#fbbf24";
  ctx.font = "11px monospace";
  wrapText(ctx, data.caveat || "", 16, 170, w - 32, 14);
  return buildTexture(canvas);
}

export function drawOperationsScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  drawHeader(ctx, "LIVE PAPER TRADING", color);
  if (data.cash === undefined) {
    drawEmptyState(ctx, w, h, "No live session yet.");
    return buildTexture(canvas);
  }
  drawLine(ctx, "CASH", "$" + data.cash, 70);
  drawLine(ctx, "BTC HELD", data.btc, 92);
  drawLine(ctx, "IN POSITION", data.in_position, 114);
  drawLine(ctx, "HALTED", data.trading_halted, 136, data.trading_halted ? "#f87171" : "#34d399");
  drawLine(ctx, "LAST CANDLE", data.last_candle_ts, 158);
  ctx.fillStyle = "#6b7280";
  ctx.font = "11px monospace";
  ctx.fillText("RECENT TICKS", 16, 190);
  (data.recent_log || []).slice(-5).forEach((row, i) => {
    ctx.fillStyle = "#9ca3af";
    ctx.font = "10px monospace";
    ctx.fillText(`${row.timestamp}  ${(row.note || "").slice(0, 36)}`, 16, 208 + i * 15);
  });
  return buildTexture(canvas);
}

export function drawSelfLearningScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  drawHeader(ctx, "PATTERN ANALYSIS", color);
  if (data.total_combos === undefined) {
    drawEmptyState(ctx, w, h, "No analysis run yet.");
    return buildTexture(canvas);
  }
  drawLine(ctx, "TRADES ANALYZED", data.total_trades, 70);
  drawLine(ctx, "RELIABLE PATTERNS", `${data.reliable_combos} / ${data.total_combos}`, 92,
    data.reliable_combos > 0 ? "#34d399" : "#fbbf24");
  drawLine(ctx, "FILTER HELPED LAST RUN", data.filter_helped_last_run, 114);
  ctx.fillStyle = "#6b7280";
  ctx.font = "11px monospace";
  wrapText(ctx, "A pattern only counts once it has 30+ historical trades backing it.", 16, 150, w - 32, 14);
  return buildTexture(canvas);
}

export function drawNotImplementedScreen(data, color) {
  const { canvas, ctx, w, h } = baseCtx();
  ctx.fillStyle = "#1f2937";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#6b7280";
  ctx.font = "bold 18px monospace";
  ctx.fillText("NOT IMPLEMENTED", 16, h / 2 - 10);
  ctx.font = "12px monospace";
  wrapText(ctx, data.note || "", 16, h / 2 + 18, w - 32, 16);
  return buildTexture(canvas);
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text).split(" ");
  let line = "", cy = y;
  for (const word of words) {
    const test = line + word + " ";
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, cy);
      line = word + " ";
      cy += lineHeight;
    } else {
      line = test;
    }
  }
  ctx.fillText(line, x, cy);
}

export const SCREEN_DRAWERS = {
  backtesting: drawBacktestingScreen,
  data_collection: drawDataScreen,
  validation: drawValidationScreen,
  operations: drawOperationsScreen,
  self_learning: drawSelfLearningScreen,
  strategy_discovery: drawNotImplementedScreen,
  machine_learning: drawNotImplementedScreen,
};
