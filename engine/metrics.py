"""
Performance metrics, computed one way, everywhere, instead of being
recalculated slightly differently in each script.
"""
import pandas as pd


def compute_metrics(result, starting_balance):
    trades_df = pd.DataFrame(result.trades)
    num_trades = len(trades_df)
    win_rate = (trades_df["pnl_pct"] > 0).mean() * 100 if num_trades else 0.0
    avg_win = trades_df.loc[trades_df["pnl_pct"] > 0, "pnl_pct"].mean() if num_trades else 0.0
    avg_loss = trades_df.loc[trades_df["pnl_pct"] <= 0, "pnl_pct"].mean() if num_trades else 0.0

    gross_win = trades_df.loc[trades_df["pnl_pct"] > 0, "pnl_pct"].sum() if num_trades else 0.0
    gross_loss = trades_df.loc[trades_df["pnl_pct"] <= 0, "pnl_pct"].sum() if num_trades else 0.0
    profit_factor = (gross_win / abs(gross_loss)) if gross_loss != 0 else float("inf") if gross_win > 0 else 0.0

    equity = pd.Series(result.equity_curve) if result.equity_curve else pd.Series([starting_balance])
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    return {
        "final_equity": result.final_equity,
        "return_pct": (result.final_equity - starting_balance) / starting_balance * 100,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "avg_win_pct": float(avg_win) if pd.notna(avg_win) else 0.0,
        "avg_loss_pct": float(avg_loss) if pd.notna(avg_loss) else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown_pct": float(max_drawdown) if pd.notna(max_drawdown) else 0.0,
        "trading_halted": result.trading_halted,
        "skipped_by_filter": result.skipped_by_filter,
    }


def buy_and_hold_return_pct(df):
    start_price = df["close"].iloc[0]
    end_price = df["close"].iloc[-1]
    return (end_price / start_price - 1) * 100
