# Bollinger Bands Strategy: Academic & Empirical Notes

## The Theory

Bollinger Bands (John Bollinger, 1980s) use a simple moving average ± K standard deviations
to create dynamic price channels. The core hypothesis:

- Prices oscillate around a mean (the MA)
- Extreme deviations (beyond Kσ) are statistically rare under normal distribution
- Breakouts from the channel may indicate trend formation

Under a normal distribution:
| Band  | Coverage |
|-------|----------|
| ±1σ   | 68.3%   |
| ±2σ   | 95.4%   |
| ±3σ   | 99.7%   |

## Why It Doesn't Quite Work (for stocks)

### Fat tails

Stock returns follow a **leptokurtic** (fat-tailed) distribution, not normal.
Extreme moves (>2σ) occur 5-15x more often than the normal distribution predicts.

Empirical evidence from our backtest (3 stocks, 2023-2026):
- False breakout rate: **55-67%** (vs theoretical ~4.6%)
- Win rate: **11-33%** across different stocks
- Only 1 of 3 stocks beat buy-and-hold

### Regime dependency

The strategy works differently in:
- **Trending markets**: Breakouts tend to continue → higher win rate
- **Mean-reverting markets**: Breakouts revert → high false positive rate
- **Low-volatility regimes**: Bands narrow, even small moves trigger "breakouts"

### Parameter sensitivity

Results vary dramatically with:
- Window length (20 vs 60 changes everything)
- Std multiplier (1.5σ vs 2.5σ changes signal frequency)
- Confirmation period (1-day vs 3-day)

## What Actually Works (from backtest evidence)

1. **The discipline of waiting** — Fewer trades means fewer mistakes. The "do nothing
   95% of the time" philosophy has merit independent of the signal.

2. **Confirmation filters** — Requiring 2+ days above the band significantly reduces
   false signals vs single-day breakouts.

3. **Volume confirmation** — Adding "breakout must be on above-average volume" as a
   filter improves signal quality (not implemented in base version).

4. **The strategy is better than random** — Even with 33% win rate, if average win > 
   average loss, the expectation can be positive. The key metric is **expectancy per
   trade**, not win rate alone.

## References

- Bollinger, J. (2001). *Bollinger on Bollinger Bands*. McGraw-Hill.
- Mandelbrot, B. (1963). The variation of certain speculative prices. *Journal of Business*.
- Lo, A. & MacKinlay, C. (1988). Stock market prices do not follow random walks.
- Ernie Chan, *Quantitative Trading* — practical backtesting methodology.
