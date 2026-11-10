"""
Candidate strategies for the research engine.

Each strategy turns OHLCV data into a TARGET position per candle: 1 = hold
BTC, 0 = hold cash, -1 = short BTC (profit when price falls). No leverage.
Only the "_ls" strategies ever return -1. The target at candle t uses only
data up to and including t's close; the simulator applies it from the NEXT
candle, so no strategy can trade on information it didn't have.

Every strategy is a plain function plus a small parameter grid. Grids are
kept small on purpose: the more combinations tried, the more likely one
looks good by luck (the research report counts them).
"""
import numpy as np
import pandas as pd


def _hold_between(enter, exit_):
    """1 from an entry condition until an exit condition, 0 otherwise."""
    state = pd.Series(np.nan, index=enter.index)
    state[enter] = 1.0
    state[exit_ & ~enter] = 0.0
    return state.ffill().fillna(0.0)


def sma_cross(df, short, long):
    s = df["close"].rolling(short).mean()
    l = df["close"].rolling(long).mean()
    return (s > l).astype(float).where(l.notna(), 0.0)


def ema_cross(df, short, long):
    s = df["close"].ewm(span=short, adjust=False).mean()
    l = df["close"].ewm(span=long, adjust=False).mean()
    warm = pd.Series(np.arange(len(df)) >= long, index=df.index)
    return ((s > l) & warm).astype(float)


def price_above_sma(df, window):
    """Trend state: hold whenever price is above its long average."""
    m = df["close"].rolling(window).mean()
    return (df["close"] > m).astype(float).where(m.notna(), 0.0)


def donchian_breakout(df, entry, exit_):
    """Buy a breakout above the prior `entry`-hour high, sell below the prior `exit_`-hour low."""
    upper = df["high"].rolling(entry).max().shift(1)
    lower = df["low"].rolling(exit_).min().shift(1)
    return _hold_between(df["close"] > upper, df["close"] < lower)


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def rsi_reversion(df, low, high, trend_window):
    """Buy oversold dips (RSI < low), sell when RSI recovers above high.
    trend_window > 0 only allows entries while price is above that long average."""
    r = rsi(df["close"])
    enter = r < low
    if trend_window:
        enter &= df["close"] > df["close"].rolling(trend_window).mean()
    return _hold_between(enter, r > high)


def bollinger_reversion(df, window, k):
    """Buy a close below the lower band, sell when price gets back to the middle."""
    mid = df["close"].rolling(window).mean()
    sd = df["close"].rolling(window).std()
    return _hold_between(df["close"] < mid - k * sd, df["close"] > mid)


def momentum(df, lookback):
    """Time-series momentum: hold while the last `lookback` hours were positive."""
    return (df["close"].pct_change(lookback) > 0).astype(float)


def sma_cross_ls(df, short, long):
    """Long when the short average is above the long one, short when below."""
    s = df["close"].rolling(short).mean()
    l = df["close"].rolling(long).mean()
    return pd.Series(np.where(s > l, 1.0, -1.0), index=df.index).where(l.notna(), 0.0)


def ema_cross_ls(df, short, long):
    s = df["close"].ewm(span=short, adjust=False).mean()
    l = df["close"].ewm(span=long, adjust=False).mean()
    warm = pd.Series(np.arange(len(df)) >= long, index=df.index)
    return pd.Series(np.where(s > l, 1.0, -1.0), index=df.index).where(warm, 0.0)


def price_vs_sma_ls(df, window):
    """Long while price is above its long average, short while below."""
    m = df["close"].rolling(window).mean()
    return pd.Series(np.where(df["close"] > m, 1.0, -1.0), index=df.index).where(m.notna(), 0.0)


def donchian_ls(df, entry, exit_):
    """Long on a breakout above the prior `entry`-hour high, short on a break
    below the prior `entry`-hour low; each side exits on the opposite `exit_`-hour extreme."""
    upper_e, lower_e = df["high"].rolling(entry).max().shift(1), df["low"].rolling(entry).min().shift(1)
    upper_x, lower_x = df["high"].rolling(exit_).max().shift(1), df["low"].rolling(exit_).min().shift(1)
    long_state = _hold_between(df["close"] > upper_e, df["close"] < lower_x)
    short_state = _hold_between(df["close"] < lower_e, df["close"] > upper_x)
    return long_state - short_state


STRATEGIES = {
    "sma_cross": {
        "family": "Trend following", "fn": sma_cross,
        "label": "SMA crossover (the current bot's family)",
        "grid": [{"short": s, "long": l} for s in (12, 24, 48) for l in (72, 120, 168) if s < l],
    },
    "ema_cross": {
        "family": "Trend following", "fn": ema_cross,
        "label": "EMA crossover",
        "grid": [{"short": s, "long": l} for s in (12, 24, 48) for l in (72, 120, 168) if s < l],
    },
    "price_above_sma": {
        "family": "Trend following", "fn": price_above_sma,
        "label": "Hold while price is above its long average",
        "grid": [{"window": w} for w in (72, 168, 336, 720)],
    },
    "donchian_breakout": {
        "family": "Breakout", "fn": donchian_breakout,
        "label": "Donchian channel breakout",
        "grid": [{"entry": e, "exit_": x} for e in (24, 72, 168) for x in (12, 24, 72) if x <= e],
    },
    "rsi_reversion": {
        "family": "Mean reversion", "fn": rsi_reversion,
        "label": "RSI oversold bounce",
        "grid": [{"low": lo, "high": hi, "trend_window": t}
                 for lo in (25, 30) for hi in (50, 60) for t in (0, 168)],
    },
    "bollinger_reversion": {
        "family": "Mean reversion", "fn": bollinger_reversion,
        "label": "Bollinger band bounce",
        "grid": [{"window": w, "k": k} for w in (20, 48) for k in (2.0, 2.5)],
    },
    "momentum": {
        "family": "Momentum", "fn": momentum,
        "label": "Time-series momentum",
        "grid": [{"lookback": lb} for lb in (24, 72, 168, 336)],
    },
    "sma_cross_ls": {
        "family": "Long/short trend", "fn": sma_cross_ls,
        "label": "SMA crossover, long or short",
        "grid": [{"short": s, "long": l} for s in (12, 24, 48) for l in (72, 120, 168) if s < l],
    },
    "ema_cross_ls": {
        "family": "Long/short trend", "fn": ema_cross_ls,
        "label": "EMA crossover, long or short",
        "grid": [{"short": s, "long": l} for s in (12, 24, 48) for l in (72, 120, 168) if s < l],
    },
    "price_vs_sma_ls": {
        "family": "Long/short trend", "fn": price_vs_sma_ls,
        "label": "Long above / short below the long average",
        "grid": [{"window": w} for w in (72, 168, 336, 720)],
    },
    "donchian_ls": {
        "family": "Long/short trend", "fn": donchian_ls,
        "label": "Donchian channel breakout, long or short",
        "grid": [{"entry": e, "exit_": x} for e in (24, 72, 168) for x in (12, 24, 72) if x <= e],
    },
}
