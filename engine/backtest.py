"""
The one canonical trade-simulation loop. Every script that used to have its
own copy of this (03, 04, 05, 07, 08) now calls run_backtest() here instead.

Behavior is controlled entirely through StrategyConfig:
  - risk_per_trade/stop_loss_pct/max_drawdown_kill = None disables that
    piece of risk management (used for the "baseline, no risk mgmt" report)
  - learned_filters + bins, if provided, skip trades whose condition-combo
    has a reliable (n >= config.min_samples) win rate below the threshold

This also means the live paper trader (06) and the backtester are no longer
two separate implementations that can quietly drift apart, 06 now calls the
same step-level decision function this module exposes.
"""
from dataclasses import dataclass, field
import pandas as pd
from engine.features import condition_combo


@dataclass
class BacktestResult:
    trades: list
    equity_curve: list
    final_equity: float
    trading_halted: bool
    halted_at: object = None
    skipped_by_filter: int = 0


def decide_entry_size(cash, price, config):
    """How much cash to commit to a new position.

    If risk_per_trade is set, size so that a stop-loss hit loses approximately
    risk_per_trade of CURRENT CASH (not total equity -- there is at most one
    open position at a time in this engine, so cash == available capital).
    If risk_per_trade is None, go all-in (used only for the no-risk-mgmt baseline).
    """
    if config.risk_per_trade is None or config.stop_loss_pct is None:
        return cash
    trade_capital = cash * config.risk_per_trade / config.stop_loss_pct
    return min(trade_capital, cash)


def run_backtest(df, config, learned_filters=None, bins=None):
    """df must already have signal + condition columns (see engine.features.prepare)."""
    cash = config.starting_balance
    btc = 0.0
    in_position = False
    entry_price = 0.0
    trading_halted = False
    halted_at = None
    peak_equity = config.starting_balance
    trades = []
    equity_curve = []
    skipped_by_filter = 0

    use_risk_mgmt = config.risk_per_trade is not None

    for _, row in df.iterrows():
        price = row["close"]
        equity_now = cash + btc * price
        peak_equity = max(peak_equity, equity_now)

        if use_risk_mgmt and config.max_drawdown_kill is not None:
            if not trading_halted and (equity_now - peak_equity) / peak_equity <= -config.max_drawdown_kill:
                trading_halted = True
                halted_at = row["timestamp"]

        stop_hit = (use_risk_mgmt and in_position and config.stop_loss_pct is not None
                    and price <= entry_price * (1 - config.stop_loss_pct))

        if stop_hit:
            cash += (btc * price) * (1 - config.fee_rate)
            trades.append({"exit_time": row["timestamp"], "exit_price": price,
                            "pnl_pct": (price - entry_price) / entry_price * 100, "reason": "stop_loss"})
            btc = 0.0
            in_position = False

        elif not trading_halted and row["position_change"] == 1 and not in_position:
            take_trade = True
            if learned_filters is not None and bins is not None:
                combo = condition_combo(row, bins)
                info = learned_filters.get(combo)
                if info and info["n"] >= config.min_samples and info["win_rate"] < config.win_rate_skip_threshold:
                    take_trade = False
                    skipped_by_filter += 1

            if take_trade:
                trade_capital = decide_entry_size(cash, price, config)
                btc = (trade_capital * (1 - config.fee_rate)) / price
                cash -= trade_capital
                entry_price = price
                in_position = True

        elif row["position_change"] == -1 and in_position:
            cash += (btc * price) * (1 - config.fee_rate)
            trades.append({"exit_time": row["timestamp"], "exit_price": price,
                            "pnl_pct": (price - entry_price) / entry_price * 100, "reason": "signal"})
            btc = 0.0
            in_position = False

        equity_curve.append(cash + btc * price)

    final_equity = equity_curve[-1] if equity_curve else config.starting_balance
    return BacktestResult(trades=trades, equity_curve=equity_curve, final_equity=final_equity,
                           trading_halted=trading_halted, halted_at=halted_at,
                           skipped_by_filter=skipped_by_filter)


def step_decision(state, row, config, learned_filters=None, bins=None):
    """Single-candle version of the same decision logic, for the live paper trader.

    `state` is a dict with keys: cash, btc, in_position, entry_price,
    peak_equity, trading_halted. Mutates and returns it, plus a note string
    describing what happened (used for logging).

    This exists specifically so the live trader and the backtester can never
    drift apart again, both call the identical stop-loss/sizing/filter logic.
    """
    price = row["close"]
    equity_now = state["cash"] + state["btc"] * price
    state["peak_equity"] = max(state["peak_equity"], equity_now)

    use_risk_mgmt = config.risk_per_trade is not None
    note = "hold"

    if use_risk_mgmt and config.max_drawdown_kill is not None:
        if not state["trading_halted"] and (equity_now - state["peak_equity"]) / state["peak_equity"] <= -config.max_drawdown_kill:
            state["trading_halted"] = True
            note = "KILL_SWITCH triggered"

    stop_hit = (use_risk_mgmt and state["in_position"] and config.stop_loss_pct is not None
                and price <= state["entry_price"] * (1 - config.stop_loss_pct))

    if stop_hit:
        state["cash"] += (state["btc"] * price) * (1 - config.fee_rate)
        pnl_pct = (price - state["entry_price"]) / state["entry_price"] * 100
        state["btc"] = 0.0
        state["in_position"] = False
        note = f"STOP-LOSS exit, pnl {pnl_pct:+.2f}%"

    elif not state["trading_halted"] and row["position_change"] == 1 and not state["in_position"]:
        take_trade = True
        if learned_filters is not None and bins is not None:
            combo = condition_combo(row, bins)
            info = learned_filters.get(combo)
            if info and info["n"] >= config.min_samples and info["win_rate"] < config.win_rate_skip_threshold:
                take_trade = False
                note = f"SKIPPED by filter ({combo}, win_rate={info['win_rate']:.1f}%, n={info['n']})"

        if take_trade:
            trade_capital = decide_entry_size(state["cash"], price, config)
            state["btc"] = (trade_capital * (1 - config.fee_rate)) / price
            state["cash"] -= trade_capital
            state["entry_price"] = price
            state["in_position"] = True
            note = f"BUY at {price:.2f}"

    elif row["position_change"] == -1 and state["in_position"]:
        state["cash"] += (state["btc"] * price) * (1 - config.fee_rate)
        pnl_pct = (price - state["entry_price"]) / state["entry_price"] * 100
        state["btc"] = 0.0
        state["in_position"] = False
        note = f"SELL at {price:.2f}, pnl {pnl_pct:+.2f}%"

    return state, note
