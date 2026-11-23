---
name: Trading Bot Expert
description: Expert knowledge in building, debugging, and optimizing Python-based cryptocurrency trading bots, specifically using Binance API and technical analysis libraries.
---

# Trading Bot Expert Skill

This skill provides expertise in developing, maintaining, and optimizing cryptocurrency trading bots. Use this skill when the user asks for help with trading logic, exchange APIs (specifically Binance), technical indicators, or risk management systems.

## Key Capabilities

1.  **Exchange Integration**:
    *   Deep knowledge of `binance-connector-python` and `ccxt`.
    *   Handling API rate limits, WebSocket streams for real-time data, and signed requests for trading.
    *   Distinction between Spot and Futures (UM/CM) APIs.

2.  **Technical Analysis (TA)**:
    *   Implementing indicators using `pandas-ta` or `ta-lib` (RSI, MACD, Bollinger Bands, ATR, Moving Averages).
    *   Detecting chart patterns (Candlestick patterns, divergence, support/resistance).
    *   Multi-timeframe analysis (checking confirmation across 15m, 1h, 4h).

3.  **Risk Management**:
    *   Calculating position size based on portfolio percentage and risk limits.
    *   Implementing dynamic Stop Loss (SL) and Take Profit (TP) mechanisms (Trailing Stop, Breakeven).
    *   Leverage management and liquidation avoidance.

4.  **Bot Architecture**:
    *   **Loop Structure**: Separating the "Tick" (monitoring) loop from the "Analysis" (reporting) loop.
    *   **State Management**: Persisting open positions and trade history (e.g., using JSON, SQLite, or Redis) to survive restarts.
    *   **Error Handling**: Robust try-catch blocks for network requests and API errors.
    *   **Notifications**: Integrating Telegram/Discord bots for real-time alerts.

## Common Patterns & Snippets

### Robust API Fetching
Always wrap API calls in a retry loop with exponential backoff.

```python
def robust_api_call(call_func, retries=3):
    for i in range(retries):
        try:
            return call_func()
        except Exception as e:
            time.sleep(1 * (i + 1))
    return None
```

### Main Loop Pattern
Use a non-blocking loop logic to ensure responsivenss.

```python
last_analysis_time = 0
ANALYSIS_INTERVAL = 900 # 15 min
TICK_INTERVAL = 10      # 10 sec

while True:
    now = time.time()
    
    # 1. High-Frequency Tasks (SL/TP, Order Updates)
    check_open_positions()
    
    # 2. Low-Frequency Tasks (Market Analysis, New Signals)
    if now - last_analysis_time >= ANALYSIS_INTERVAL:
        run_market_analysis()
        last_analysis_time = now
        
    time.sleep(TICK_INTERVAL)
```

## Best Practices
-   **Never block the main loop**: Avoid long `time.sleep()` calls that prevent SL/TP checks. Use timestamp comparisons instead.
-   **Log everything**: Log entry/exit prices, signal reasons, and errors to a file for debugging.
-   **Dry Run Mode**: Always implement a `dry_run` flag to test logic without real funds.
-   **Security**: Never hardcode API keys. Use environment variables.
