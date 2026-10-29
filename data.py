"""Yahoo market data and official index membership, with local disk caching."""
import io
import json
import re
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import yfinance as yf
from engine import IST, metrics

CACHE = Path(__file__).parent / '.cache'
HEADERS = {'User-Agent': 'Mozilla/5.0 (personal stock research)'}

def stamp():
    return datetime.now(IST).isoformat(timespec='seconds')

def parse_symbols(text):
    symbols = []
    for item in re.split(r'[\s,;]+', text.upper().strip()):
        if not item:
            continue
        base = item.removesuffix('.NS')
        if not re.fullmatch(r'[A-Z0-9&_-]+', base):
            raise ValueError(f'Invalid NSE symbol: {item}')
        if base not in symbols:
            symbols.append(base)
    if not symbols or len(symbols) > 600:
        raise ValueError('Enter between 1 and 600 NSE symbols.')
    return pd.DataFrame({'Symbol': symbols, 'Company Name': symbols})

def parse_constituents(text):
    frame = pd.read_csv(io.StringIO(text))
    if 'Symbol' not in frame:
        raise ValueError('CSV must contain a Symbol column (official NSE format).')
    frame = frame.dropna(subset=['Symbol']).copy()
    frame['Symbol'] = frame['Symbol'].astype(str).str.strip().str.upper()
    if not frame['Symbol'].str.fullmatch(r'[A-Z0-9&_-]+').all():
        raise ValueError('CSV contains invalid NSE symbols.')
    if 'Company Name' not in frame:
        frame['Company Name'] = frame['Symbol']
    frame = frame.drop_duplicates('Symbol')
    if not 1 <= len(frame) <= 600:
        raise ValueError('CSV must contain 1–600 stocks.')
    return frame[['Symbol', 'Company Name']]

def universe(name):
    CACHE.mkdir(exist_ok=True)
    number = {'Nifty 50': '50', 'Nifty 500': '500'}[name]
    path = CACHE / f'nifty{number}.json'
    cached = None
    try:
        cached = json.loads(path.read_text())
        if time.time() - cached['time'] < 86400:
            return parse_constituents(cached['csv']), f"Official membership cached at {cached['at']}"
    except (OSError, ValueError, KeyError):
        cached = None
    errors = []
    for base in ['https://www.niftyindices.com/IndexConstituent/',
                 'https://nsearchives.nseindia.com/content/indices/']:
        try:
            response = requests.get(base + f'ind_nifty{number}list.csv', headers=HEADERS, timeout=15)
            response.raise_for_status()
            frame = parse_constituents(response.text)
            if len(frame) < int(number) * .9:
                raise ValueError('Unexpectedly small index list')
            at = stamp()
            path.write_text(json.dumps({'time': time.time(), 'at': at, 'csv': response.text}))
            return frame, f'Official membership fetched at {at}'
        except Exception as exc:
            errors.append(type(exc).__name__)
    if cached:
        return parse_constituents(cached['csv']), f"WARNING: using older membership from {cached['at']}; official download failed."
    raise RuntimeError('Official index download unavailable (' + ', '.join(errors) + '). Use Custom symbols or upload an official constituent CSV.')

def fundamental(symbol):
    CACHE.mkdir(exist_ok=True)
    # Symbols are validated upstream; filenames remain safe even for '&'.
    path = CACHE / (symbol + '.json')
    try:
        cached = json.loads(path.read_text())
        if time.time() - cached['time'] < 86400:
            return cached['pe'], cached['at'], ''
    except (OSError, ValueError, KeyError):
        pass
    error = ''
    for attempt in range(2):
        try:
            info = yf.Ticker(symbol + '.NS').get_info()
            pe = info.get('trailingPE')
            pe = float(pe) if pe is not None else None
            if pe is not None and not __import__('math').isfinite(pe):
                pe = None
            at = stamp()
            if pe is not None:
                temp = path.with_suffix('.tmp')
                temp.write_text(json.dumps({'pe': pe, 'at': at, 'time': time.time()}))
                temp.replace(path)
            return pe, at, '' if pe is not None else 'Trailing P/E unavailable'
        except Exception as exc:
            error = f'P/E download failed: {type(exc).__name__}'
            if attempt == 0:
                time.sleep(1)
    return None, stamp(), error

def scan(members, period=14, include_today=False, progress=None):
    frames, issues = {}, []
    symbols = members['Symbol'].tolist()
    names = members.set_index('Symbol')['Company Name'].to_dict()
    for start in range(0, len(symbols), 40):
        batch = symbols[start:start + 40]
        try:
            raw = yf.download([s + '.NS' for s in batch], period='1y', interval='1d',
                              auto_adjust=False, group_by='ticker', threads=4,
                              progress=False, timeout=15)
            for symbol in batch:
                try:
                    frame = raw[symbol + '.NS'] if isinstance(raw.columns, pd.MultiIndex) else raw
                    frame = frame.dropna(how='all')
                    if frame.empty:
                        raise ValueError('No daily price data returned')
                    frames[symbol] = metrics(frame, period, include_today)
                except Exception as exc:
                    issues.append({'Ticker': symbol, 'Issue': str(exc)})
        except Exception as exc:
            issues.extend({'Ticker': s, 'Issue': f'Price download failed: {type(exc).__name__}'} for s in batch)
        if progress:
            progress(.5 * min(start + 40, len(symbols)) / len(symbols), 'Downloading daily prices')
    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fundamental, symbol): symbol for symbol in frames}
        for i, future in enumerate(as_completed(futures)):
            symbol = futures[future]
            try:
                pe, pe_at, error = future.result()
            except Exception as exc:
                pe, pe_at, error = None, stamp(), f'P/E unavailable: {type(exc).__name__}'
            if error:
                issues.append({'Ticker': symbol, 'Issue': error})
            rows.append({'Ticker': symbol, 'Company': names[symbol], **frames[symbol],
                         'P/E': pe, 'P/E fetched IST': pe_at})
            if progress:
                progress(.5 + .5 * (i + 1) / max(1, len(futures)), 'Checking trailing P/E')
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame['P/E'] = pd.to_numeric(frame['P/E'], errors='coerce')
        latest = frame['Bar date'].max()
        old = frame['Bar date'] != latest
        issues.extend({'Ticker': s, 'Issue': f'Older bar than scan latest session ({latest}); excluded'} for s in frame.loc[old, 'Ticker'])
        frame = frame.loc[~old].reset_index(drop=True)
    return frame, pd.DataFrame(issues, columns=['Ticker', 'Issue']), stamp()
