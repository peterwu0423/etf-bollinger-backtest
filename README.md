# ETF Bollinger Band Breakout Backtester

用统计学方法（布林带突破）过滤市场噪音，回测验证策略有效性。

## Features

- **布林带突破策略回测** — MA(N)±Kσ，N日确认入场，输出胜率/年化/假突破率
- **ETF 技术信号生成** — 布林带/MACD/RSI/均线系统/量比综合评分
- **A股数据源** — baostock 免费 API，前复权日线
- **命令行工具** — 参数化，支持自定义标的/窗口/标准差

## Quick Start

```bash
pip install baostock pandas numpy

# 回测沪深300指数（默认）
python scripts/bollinger_backtest.py

# 回测自定义标的
python scripts/bollinger_backtest.py --codes sh.600519 sh.000300 sz.000001

# 生成ETF技术信号
python scripts/etf_signal.py --codes sh.000300
```

## Strategy

**入场**: 连续 N 日收盘价突破 MA20 + 2σ 上轨
**出场**: 收盘价跌回上轨内 + MA20 走平

> ⚠️ 股价服从尖峰肥尾分布，实际假突破率通常远高于理论 4.6%。
> 回测验证是必经步骤，不可盲信理论。

## Example Output

```
Bollinger Band Breakout Strategy Backtest
Parameters: MA20, ±2.0σ, confirm=2d

  sh.000300
  Data range           2023-02-13 ~ 2026-06-01
  Total trades         9
  Win rate             33.3%
  Annualized return    7.21%
  Buy&Hold annual      7.4%
  False breakout       66.7%
```

## Project Structure

```
├── SKILL.md                        # Detailed skill documentation
├── scripts/
│   ├── bollinger_backtest.py       # Backtester (baostock data)
│   └── etf_signal.py              # Technical signal generator
└── references/
    └── methodology.md             # Academic notes & empirical findings
```

## License

MIT
