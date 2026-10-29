# NSE Lens — personal Indian stock screener

A local browser dashboard built for Deepak. No broker login or OpenAI API key is needed. Internet access is required for market data. This package does not execute trades.

## Start on Windows

1. Install Python 3.11 or newer from https://www.python.org/downloads/windows/ if needed. Enable the Python launcher during installation.
2. Extract this entire ZIP into a normal folder (do not run from inside the ZIP).
3. Double-click **Start-Windows.bat**. The first run creates an isolated environment and installs dependencies; this can take several minutes.
4. Your browser should open automatically. Otherwise open **http://localhost:8501**.
5. Choose **Nifty 50**, then **Scan stocks**. Move to Nifty 500 after confirming your connection works.
6. Leave the terminal open while using the app. Press Ctrl+C in it to stop. Double-click the launcher to start again.

If `py` is not recognized, install/enable the Python launcher, or use the manual commands below with your installed Python executable.

## macOS / Linux

Install Python 3.11+ and run `bash start.sh` from the extracted folder. On some Linux distributions install the OS package for Python venv first.

## Manual launch

Run from this folder:

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.address localhost --server.port 8501
# macOS/Linux: replace .venv\Scripts\python with .venv/bin/python
```

## Features

- Nifty 50 or Nifty 500 membership downloaded from official index CSVs.
- Custom NSE symbols (e.g. `RELIANCE, TCS, M&M`) or uploaded official constituent CSV.
- Default filters: **0 < trailing P/E < 20**, **volume ratio > 2**, **daily Wilder RSI(14) > 50**, all required together.
- Adjustable thresholds, RSI 7/14/21, daily or provisional-today mode.
- Matches, all usable scanned stocks, and data-quality tabs.
- Sorting, transparent score, CSV exports, manual refresh, optional 60-second auto-refresh.
- Coverage counts and actual daily bar dates. No demonstration prices in the application.
- P/E and membership disk caches reduce requests; both have a 24-hour freshness window.

## Exact calculations and interpretation

Volume ratio uses the selected daily volume divided by the preceding 20 session volumes' arithmetic mean, excluding the selected session. No time-of-day scaling is applied. Today's partial volume will normally be lower than a full day's total.

RSI uses one year of adjusted daily closing prices. Average gain/loss is seeded with a simple mean of the first N price changes, then smoothed recursively with Wilder's formula `(previous * (N-1) + change) / N`. All-gain history returns 100, all-loss history 0, flat history 50. Missing/invalid history is rejected.

Daily mode excludes today's bar before 16:00 IST, allowing it afterward if returned by Yahoo. This 30-minute buffer after the regular session is a heuristic, not an exchange holiday/special-session calendar or a guarantee of finalized data. On weekends/holidays it uses the latest available bar. Stocks whose latest usable bar predates the newest bar in that scan are excluded and reported. A calendar age over four days produces a warning.

Price is the unadjusted selected daily close, or the provisional daily bar price if enabled. It is not a separately fetched live LTP. P/E is the provider's latest trailing P/E and can refer to a different quote time than the daily close. The P/E fetch timestamp indicates when it was retrieved, not when underlying earnings were reported. This is a present-day screener, not a historical backtester.

All comparisons are strict: P/E=20, volume ratio=2 or RSI=50 fails the default filter. Missing, zero and negative P/E fail.

Score (0–100):

`100 × (0.30 × clip(1 − PE / PE_limit, 0, 1) + 0.40 × clip(volume_ratio / (2 × volume_limit), 0, 1) + 0.30 × RSI / 100)`

Invalid P/E contributes zero valuation points. Passing stocks sort first, then descending score, then ticker. This is an explicitly chosen heuristic because the transcript did not provide its ranking formula. It is not backtested and has no implied return probability. Volume alone cannot identify institutional accumulation.

## Refresh and errors

An official index list may occasionally have more/fewer entries than its name suggests (for example around corporate actions); the app uses the downloaded list and shows the actual count.

First Nifty 500 scan may take several minutes: P/E requires per-stock requests. Three fundamental workers and small price batches limit request pressure. Fundamentals retry once after an exception; failed/missing P/E is not cached. History failures are listed; manual refresh retries them. There is no promise of an unlimited/free real-time feed.

Auto-refresh checks for another scan every 60 seconds while the session is active, with at least 60 seconds since the previous scan completed. It is not a background scheduler and does not keep running after the app is stopped. Threshold changes reuse the scan immediately. Universe, RSI period or provisional-mode changes require **Scan stocks**. The app warns when displayed results use previous settings.

If official index downloads fail, the app tries another official endpoint, then an existing disk cache with a dated warning. If no cache exists, use custom symbols or upload a constituent CSV containing `Symbol` and optionally `Company Name`. Official lists:

- https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv
- https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv

If Yahoo data is blocked or throttled, wait and retry a smaller custom list. Complete download failure is explicitly shown as a data failure, not as zero matching stocks. Invalid P/E and other issues are visible in Data quality. There is no fallback to fabricated quotes.

The app binds to localhost. To remove caches, stop it and delete `.cache` in this folder. To reinstall dependencies, delete `.venv/installed.ok` and restart the launcher. If port 8501 is busy, stop the other Streamlit instance or use `--server.port 8502` in a manual launch.

## Data use and sources

For your own research. yfinance is unofficial and Yahoo's data terms apply. A 60-second refresh does not make delayed data real-time. No paid data subscription or OpenAI API usage is built into this app; your internet/computer costs and data-provider restrictions still apply.

- https://ranaroussi.github.io/yfinance/
- https://ranaroussi.github.io/yfinance/reference/yfinance.functions.html
- https://docs.streamlit.io/develop/concepts/architecture/fragments

## Tests

From this folder: `python -m pip install pytest`, then `python -m pytest -q`.

Tests cover a published-style Wilder RSI numerical example, rising/falling/flat histories, exclusion of current volume from the average, session cutoff, invalid histories, strict thresholds, missing/negative P/E, symbol validation, dashboard filtering, and explicit download-failure messaging. UI tests use isolated synthetic fixtures, never displayed as real application quotes.

See VALIDATION.md for the checks run during creation.
