// Draws one employee's monitor from their real step outputs. If they have no
// logged work, the screen says so instead of showing a made-up chart.
import * as THREE from "three";
import { STATUS_LABELS, STATUS_COLORS, humanizeKey, formatValue, formatTime } from "./utils";

const W = 512, H = 320;

function canvas2d() {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#070a12";
  ctx.fillRect(0, 0, W, H);
  return { canvas, ctx };
}

function texture(canvas) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function header(ctx, title, color, status) {
  ctx.fillStyle = color;
  ctx.font = "bold 22px monospace";
  ctx.fillText(title.toUpperCase(), 16, 32);
  ctx.fillStyle = STATUS_COLORS[status] || "#6b7280";
  ctx.font = "bold 14px monospace";
  const label = STATUS_LABELS[status] || status;
  ctx.fillText(label.toUpperCase(), W - 16 - ctx.measureText(label.toUpperCase()).width, 30);
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.5;
  ctx.beginPath();
  ctx.moveTo(16, 42);
  ctx.lineTo(W - 16, 42);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function line(ctx, label, value, y, color = "#e5e7eb") {
  ctx.fillStyle = "#9ca3af";
  ctx.font = "13px monospace";
  ctx.fillText(label.slice(0, 22), 16, y);
  ctx.fillStyle = color;
  ctx.font = "bold 14px monospace";
  ctx.fillText(String(value).slice(0, 34), 210, y);
}

function sparkline(ctx, values, x, y, w, h, color) {
  if (!values || values.length < 2) return;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const px = x + (i / (values.length - 1)) * w;
    const py = y + h - ((v - min) / range) * h;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();
}

export function drawStepScreen(employee, steps, status, color) {
  const { canvas, ctx } = canvas2d();
  header(ctx, employee.title, color, status);
  if (!steps.length) {
    ctx.fillStyle = "#4b5563";
    ctx.font = "15px monospace";
    ctx.fillText("No run logged yet.", 16, H / 2);
    return texture(canvas);
  }
  let y = 66;
  const last = steps[steps.length - 1];
  line(ctx, "last run", formatTime(last.finished_at || last.started_at), y);
  y += 22;
  for (const step of steps) {
    if (step.error) {
      ctx.fillStyle = "#f87171";
      ctx.font = "12px monospace";
      ctx.fillText(("ERROR " + step.error).slice(0, 62), 16, y);
      y += 20;
    }
    for (const [key, value] of Object.entries(step.outputs || {})) {
      if (y > H - 12) break;
      if (Array.isArray(value) && value.length && String(value[0]).length > 30) {
        // long list items (headlines, warnings) get their own lines
        line(ctx, humanizeKey(key), "", y);
        y += 18;
        for (const item of value.slice(0, 3)) {
          if (y > H - 12) break;
          ctx.fillStyle = "#d1d5db";
          ctx.font = "11px monospace";
          ctx.fillText("· " + String(item).slice(0, 64), 24, y);
          y += 16;
        }
        continue;
      }
      line(ctx, humanizeKey(key), formatValue(value), y);
      y += 21;
    }
  }
  return texture(canvas);
}

export function drawBacktestScreen(employee, backtest, color) {
  const { canvas, ctx } = canvas2d();
  const status = backtest && backtest.metrics ? "done" : "no_data";
  header(ctx, employee.title, color, status);
  if (!backtest || !backtest.metrics) {
    ctx.fillStyle = "#4b5563";
    ctx.font = "15px monospace";
    ctx.fillText("No backtest exported yet.", 16, H / 2);
    return texture(canvas);
  }
  const m = backtest.metrics;
  line(ctx, "strategy", `${backtest.strategy_name} v${backtest.strategy_version}`, 66);
  line(ctx, "return", `${m.return_pct}%`, 88, m.return_pct >= 0 ? "#34d399" : "#f87171");
  line(ctx, "buy & hold", `${backtest.buy_and_hold_pct}%`, 110);
  line(ctx, "trades / win rate", `${m.num_trades} / ${m.win_rate}%`, 132);
  line(ctx, "max drawdown", `${m.max_drawdown_pct}%`, 154, "#f87171");
  sparkline(ctx, backtest.equity_sparkline, 16, 180, W - 32, 110, color);
  return texture(canvas);
}

export function drawEmptyRoomScreen(note) {
  const { canvas, ctx } = canvas2d();
  ctx.fillStyle = "#1f2937";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#6b7280";
  ctx.font = "bold 18px monospace";
  ctx.fillText("NOT IMPLEMENTED", 16, 60);
  ctx.font = "13px monospace";
  const words = (note || "").split(" ");
  let row = "", y = 92;
  for (const w of words) {
    if (ctx.measureText(row + w).width > W - 32) { ctx.fillText(row, 16, y); row = ""; y += 18; }
    row += w + " ";
  }
  ctx.fillText(row, 16, y);
  return texture(canvas);
}
