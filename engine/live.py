"""
Catch-up logic for the live paper trader.

GitHub's free scheduler skips runs, sometimes for hours. The bot used to look
only at the newest candle, so a crossover inside a gap was lost for good.
Now each run looks at every closed candle since the last one it handled, and
the latest crossover among them decides what to do.

A missed signal is acted on at the CURRENT close, not the close of the
candle where it happened: the bot wasn't running then and couldn't have
traded at that price. The delay is recorded so it's visible, not hidden.
"""
import pandas as pd


def new_candles_since(df, last_candle_ts):
    """Rows of df newer than last_candle_ts, and whether df even reaches back
    far enough to cover the whole gap."""
    if last_candle_ts is None:
        return df.iloc[[-1]], True
    last = pd.Timestamp(last_candle_ts)
    new = df[df["timestamp"] > last]
    covers_gap = len(df) > 0 and df["timestamp"].iloc[0] <= last + pd.Timedelta(hours=1)
    return new, covers_gap


def effective_signal(new_rows):
    """(change, cross_timestamp, missed_candles) the bot should act on now.

    change is +1 (buy), -1 (sell) or 0. The latest crossover in the new rows
    wins, since it's the one that set the current trend direction.
    """
    missed = max(0, len(new_rows) - 1)
    crosses = new_rows[new_rows["position_change"].fillna(0) != 0]
    if crosses.empty:
        return 0, None, missed
    last = crosses.iloc[-1]
    return int(last["position_change"]), last["timestamp"], missed
