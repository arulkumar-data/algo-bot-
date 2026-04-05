# MT5 Algo Trading Bot

A Python-based algorithmic trading bot for MetaTrader 5.  
**Version 1** uses a simple **EMA Crossover** strategy on **EURUSD M15**.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **OS** | Windows (MT5 Python package is Windows-only) |
| **Python** | 3.9 – 3.12 recommended |
| **MetaTrader 5** | Desktop terminal installed and running |
| **Broker Account** | Demo/paper account logged in inside MT5 |
| **Algo Trading** | Must be **enabled** in MT5 → Tools → Options → Expert Advisors → ☑ Allow algorithmic trading |

---

## Quick Start

```bash
# 1. Clone / copy this folder
cd mt5_algo_bot

# 2. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file from the template
copy .env.example .env
# Then edit .env and fill in your MT5 login, password, server

# 5. Make sure MT5 desktop terminal is open and logged in

# 6. Run the bot
python main.py
```

---

## Project Structure

```
mt5_algo_bot/
├── README.md              ← You are here
├── requirements.txt       ← Python dependencies
├── .env.example           ← Template for secrets
├── .gitignore             ← Files excluded from git
├── config.py              ← Central configuration loader
├── main.py                ← Entry point
│
├── data/
│   ├── raw/               ← Raw OHLCV data downloads
│   └── processed/         ← Cleaned / indicator-enriched data
│
├── strategy/
│   └── strategy.py        ← EMA crossover signal logic
│
├── mt5/
│   ├── connection.py      ← MT5 terminal init / shutdown
│   ├── market_data.py     ← Fetch candles & ticks
│   ├── orders.py          ← Send / modify / close orders
│   └── account.py         ← Account balance & equity info
│
├── backtest/
│   ├── engine.py          ← Walk-forward backtest loop
│   └── metrics.py         ← Performance calculators
│
├── risk/
│   └── rules.py           ← Position sizing & daily limits
│
├── execution/
│   ├── paper_trader.py    ← Demo / paper trade execution
│   └── live_trader.py     ← Live execution (Phase 6)
│
└── logs/
    └── bot.log            ← Auto-created runtime log
```

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Foundation | ✅ Done | Project structure, config, entry point |
| 2 — MT5 Connection | ⬜ Pending | Connect to terminal, fetch data |
| 3 — Strategy | ⬜ Pending | EMA crossover signal generation |
| 4 — Backtesting | ⬜ Pending | Historical simulation & metrics |
| 5 — Paper Trading | ⬜ Pending | Demo order execution |
| 6 — Live Skeleton | ⬜ Pending | Live trading with safety guards |

---

## Strategy (Version 1): EMA Crossover

- **Fast EMA**: 20 periods  
- **Slow EMA**: 50 periods  
- **Buy**: Fast EMA crosses above Slow EMA  
- **Sell**: Fast EMA crosses below Slow EMA  
- **Stop Loss**: 50 pips  
- **Take Profit**: 100 pips  
- **Max trades/day**: 5  
- **Max daily loss**: 3% of account balance  
- **Risk per trade**: 1% of account balance  

---

## ⚠️ Disclaimer

This bot is for **educational purposes only**. Always test on a **demo account** first.  
The authors are not responsible for any financial losses.
