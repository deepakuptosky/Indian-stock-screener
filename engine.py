"""Pure calculations; no network or UI dependencies."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

IST = ZoneInfo('Asia/Kolkata')

def wilder_rsi(close, period=14):
    values = pd.to_numeric(close, errors='coerce').to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) <= period or not np.isfinite(values).all():
        return pd.Series(out, index=close.index)
    changes = np.diff(values)
    gains, losses = np.maximum(changes, 0), np.maximum(-changes, 0)
    gain, loss = gains[:period].mean(), losses[:period].mean()
    def value(g, l):
        return 50.0 if g == l == 0 else (100.0 if l == 0 else 100 - 100 / (1 + g / l))
    out[period] = value(gain, loss)
    for i in range(period + 1, len(values)):
        gain = (gain * (period - 1) + gains[i - 1]) / period
        loss = (loss * (period - 1) + losses[i - 1]) / period
        out[i] = value(gain, loss)
    return pd.Series(out, index=close.index)

def eligible_bars(frame, include_today=False, now=None):
    now = now or datetime.now(IST)
    now = now.astimezone(IST)
    frame = frame.copy().sort_index()
    frame = frame[~frame.index.duplicated(keep='last')]
    idx = pd.DatetimeIndex(frame.index)
    if idx.tz is not None:
        idx = idx.tz_convert(IST)
    dates = idx.date
    # Wait until 16:00 IST for the regular session's daily bar to settle.
    allow_today = include_today or now.time() >= time(16, 0)
    mask = dates <= now.date() if allow_today else dates < now.date()
    return frame.loc[mask]

def metrics(frame, period=14, include_today=False, now=None):
    bars = eligible_bars(frame, include_today, now)
    if len(bars) < max(21, period + 1):
        raise ValueError('Insufficient history (need 21 bars and RSI warm-up)')
    close = pd.to_numeric(bars['Close'], errors='coerce')
    volume = pd.to_numeric(bars['Volume'], errors='coerce')
    adjusted = pd.to_numeric(bars.get('Adj Close', close), errors='coerce')
    if not np.isfinite(close.iloc[-1]) or close.iloc[-1] <= 0:
        raise ValueError('Invalid latest closing price')
    recent = volume.iloc[-21:]
    if not np.isfinite(recent).all() or (recent < 0).any() or recent.iloc[:-1].mean() <= 0:
        raise ValueError('Invalid volume history')
    rsi = float(wilder_rsi(adjusted, period).iloc[-1])
    if not np.isfinite(rsi):
        raise ValueError('Missing adjusted price history for RSI')
    return {'Price ₹': float(close.iloc[-1]), 'Volume': float(volume.iloc[-1]),
            '20D avg volume': float(recent.iloc[:-1].mean()),
            'Volume ratio': float(volume.iloc[-1] / recent.iloc[:-1].mean()),
            'RSI': rsi, 'Bar date': str(pd.Timestamp(bars.index[-1]).date())}

def screen(frame, pe_max=20.0, volume_min=2.0, rsi_min=50.0):
    result = frame.copy()
    if result.empty:
        return result
    result['P/E pass'] = result['P/E'].gt(0) & result['P/E'].lt(pe_max)
    result['Volume pass'] = result['Volume ratio'].gt(volume_min)
    result['RSI pass'] = result['RSI'].gt(rsi_min)
    result['All pass'] = result[['P/E pass', 'Volume pass', 'RSI pass']].all(axis=1)
    # Transparent heuristic; not a prediction or a backtested strategy.
    value = (1 - result['P/E'] / pe_max).clip(0, 1).where(result['P/E'].gt(0), 0)
    volume = (result['Volume ratio'] / (2 * volume_min)).clip(0, 1)
    result['Score'] = (100 * (0.3 * value + 0.4 * volume + 0.3 * result['RSI'] / 100)).round(2)
    return result.sort_values(['All pass', 'Score', 'Ticker'], ascending=[False, False, True]).reset_index(drop=True)
