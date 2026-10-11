"""
Step 7: self-analysis layer -- built on the shared engine.

Labels every historical trade with the market conditions present at its
entry, then computes a win rate per condition-combination, refusing to
trust combinations with fewer than config.min_samples examples.
"""
import json
from engine.config import DEFAULT_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.learning import label_trades_with_conditions, learn_filters

config = DEFAULT_CONFIG
df, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
for w in warnings:
    print(f"Data quality warning: {w}")

prepared = prepare(df, config)
labeled, bins = label_trades_with_conditions(prepared, config)
print(f"Total trades analyzed: {len(labeled)}")

filters = learn_filters(labeled, config.min_samples)
rows = sorted(filters.items(), key=lambda kv: kv[1]["win_rate"], reverse=True)

print("\n" + "=" * 70)
print(f"WIN RATE BY CONDITION COMBINATION  (reliable = at least {config.min_samples} trades)")
print("=" * 70)
for combo, info in rows:
    print(f"{combo:70s} n={info['n']:<4d} win_rate={info['win_rate']:>5.1f}% "
          f"avg_pnl={info['avg_pnl_pct']:>6.2f}% reliable={info['reliable']}")

reliable = [(c, i) for c, i in rows if i["reliable"]]
print(f"\n{len(reliable)} of {len(rows)} combinations have enough trades to trust.")
if reliable:
    print(f"Best reliable combo:  {reliable[0][0]}  ({reliable[0][1]['win_rate']}% win rate, n={reliable[0][1]['n']})")
    worst = min(reliable, key=lambda kv: kv[1]["win_rate"])
    print(f"Worst reliable combo: {worst[0]}  ({worst[1]['win_rate']}% win rate, n={worst[1]['n']})")
else:
    print("None of the combinations have enough samples yet to be trustworthy.")
    print("This is an honest result, not a bug: with this many condition dimensions,")
    print("most buckets will have only a handful of examples until much more trade")
    print("history accumulates (more paper trading time, or more historical data).")

with open("learned_filters.json", "w") as f:
    json.dump(filters, f, indent=2)
print("\nSaved lookup table to learned_filters.json")

labeled.to_csv("trades_with_conditions.csv", index=False)
print("Saved full trade+conditions log to trades_with_conditions.csv")
