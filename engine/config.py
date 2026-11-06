"""
Single source of truth for strategy and risk parameters.

Before this module existed, SHORT_WINDOW/LONG_WINDOW/RISK_PER_TRADE/etc. were
copy-pasted constants in five different scripts, which already caused one
real bug (a feature computed differently in different copies). Every script
should import StrategyConfig from here instead of declaring its own copy.
"""
from dataclasses import dataclass, asdict
import json


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "ma_crossover"
    version: str = "1.1"  # bump this whenever the signal logic itself changes
    short_window: int = 24
    long_window: int = 72
    starting_balance: float = 1000.0
    fee_rate: float = 0.001

    # risk management -- set risk_per_trade to None to disable position sizing
    # (all-in on every signal), used by the "baseline, no risk management" backtest
    risk_per_trade: float | None = 0.02
    stop_loss_pct: float | None = 0.03
    max_drawdown_kill: float | None = 0.20

    # self-learning filter
    min_samples: int = 30
    # Skip a reliable condition-combo only if it LOSES money on average, not
    # merely if it wins under 50% of the time. This strategy is a trend
    # follower with a sub-50% win rate by design (it wins rarely but big --
    # see optimization_results.csv: the best overall config wins only 33% of
    # trades yet returns +19%). A win-rate-vs-50% threshold would flag every
    # bucket as bad and skip every trade forever, which is the opposite of
    # what this filter is for.
    avg_pnl_skip_threshold_pct: float = 0.0

    def to_dict(self):
        return asdict(self)

    def fingerprint(self):
        """A short string identifying this exact config, for reproducibility records."""
        return json.dumps(self.to_dict(), sort_keys=True)


DEFAULT_CONFIG = StrategyConfig()
BASELINE_NO_RISK_CONFIG = StrategyConfig(
    name="ma_crossover_no_risk_mgmt",
    risk_per_trade=None, stop_loss_pct=None, max_drawdown_kill=None,
)
