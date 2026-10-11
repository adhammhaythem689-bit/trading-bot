"""
Market data loading and quality checks.

Centralizes the validation the master-prompt audit flagged as missing:
duplicate detection, gap detection, and basic sanity checks on prices.
"""
import pandas as pd


class DataQualityWarning:
    def __init__(self, kind, detail):
        self.kind = kind
        self.detail = detail

    def __repr__(self):
        return f"DataQualityWarning({self.kind}: {self.detail})"


def load_ohlcv_csv(path, timeframe_hours=1):
    """Load an OHLCV CSV and run basic data-quality checks.

    Returns (dataframe, list_of_warnings). Never raises on data-quality
    issues, callers decide whether warnings are acceptable; it only raises
    on structurally broken input (missing required columns).
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return validate_ohlcv(df, timeframe_hours, source=path)


def validate_ohlcv(df, timeframe_hours=1, source="dataframe"):
    """Same checks as load_ohlcv_csv, for data already in memory (e.g. a live fetch)."""
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")

    warnings = []

    dupes = df["timestamp"].duplicated().sum()
    if dupes:
        warnings.append(DataQualityWarning("duplicate_timestamps", f"{dupes} duplicate rows"))
        df = df.drop_duplicates(subset="timestamp", keep="first")

    df = df.sort_values("timestamp").reset_index(drop=True)

    if len(df) > 1:
        expected_step = pd.Timedelta(hours=timeframe_hours)
        actual_steps = df["timestamp"].diff().dropna()
        gaps = actual_steps[actual_steps > expected_step]
        if len(gaps):
            worst = gaps.max()
            warnings.append(DataQualityWarning(
                "missing_candles",
                f"{len(gaps)} gap(s) larger than {expected_step}, worst gap: {worst}"
            ))

    bad_prices = df[(df[["open", "high", "low", "close"]] <= 0).any(axis=1)]
    if len(bad_prices):
        warnings.append(DataQualityWarning("non_positive_price", f"{len(bad_prices)} row(s)"))

    return df, warnings
