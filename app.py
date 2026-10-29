import io
from datetime import datetime
import pandas as pd
import streamlit as st
from engine import IST, screen
from data import universe, parse_symbols, parse_constituents, scan

st.set_page_config(page_title='NSE Lens · Personal Screener', page_icon='📈', layout='wide')
st.markdown('''<style>
.stApp {background:#0b1220} [data-testid="stSidebar"]{background:#111c2d}
h1,h2,h3 {letter-spacing:-.035em} [data-testid="stMetric"] {background:#142237;padding:16px;border:1px solid #233852;border-radius:12px}
</style>''', unsafe_allow_html=True)
st.caption('NSE LENS / PERSONAL RESEARCH')
st.title('Value meets momentum.')
st.write('Find Indian stocks where valuation, unusual volume and price momentum align.')
with st.sidebar:
    st.header('Screen controls')
    choice = st.selectbox('Stock universe', ['Nifty 50', 'Nifty 500', 'Custom symbols', 'Upload constituent CSV'])
    custom = st.text_area('NSE symbols', 'RELIANCE, TCS, HDFCBANK, INFY, ITC') if choice == 'Custom symbols' else ''
    upload = st.file_uploader('Official constituent CSV', type='csv') if choice == 'Upload constituent CSV' else None
    st.divider()
    pe_max = st.number_input('P/E below', min_value=1.0, max_value=200.0, value=20.0, step=1.0)
    volume_min = st.number_input('Volume ratio above', min_value=.1, max_value=20.0, value=2.0, step=.1)
    rsi_min = st.slider('RSI above', 0, 99, 50)
    period = st.selectbox('RSI period (daily bars)', [14, 7, 21])
    include_today = st.toggle('Include today’s provisional bar', value=False)
    auto = st.toggle('Auto-refresh every 60 seconds', value=False)
    st.caption('Auto-refresh runs while this app is open. P/E is cached for 24 hours. Price downloads may be delayed or throttled.')
    run = st.button('Scan stocks', type='primary', use_container_width=True)
    clear = st.button('Clear saved results', use_container_width=True)

if clear:
    st.session_state.pop('scan_result', None)
    st.session_state.pop('active_scan', None)

if include_today:
    st.warning('Provisional mode: today’s volume is incomplete and is compared with full sessions. RSI and matches may change before close.')

config = (choice, custom, upload.getvalue() if upload else None, period, include_today)
if run:
    try:
        if choice == 'Custom symbols':
            members, source = parse_symbols(custom), 'Your custom NSE list'
        elif choice == 'Upload constituent CSV':
            if upload is None:
                raise ValueError('Upload a CSV with a Symbol column first.')
            members, source = parse_constituents(upload.getvalue().decode('utf-8-sig')), 'Your uploaded constituent list'
        else:
            with st.spinner('Loading official index membership…'):
                members, source = universe(choice)
        st.session_state.active_scan = (config, members, source)
        st.session_state.pop('scan_result', None)
    except Exception as exc:
        st.error(str(exc))

@st.fragment(run_every='60s' if auto else None)
def results():
    active = st.session_state.get('active_scan')
    if not active:
        st.info('Choose a universe and click Scan stocks. Start with Nifty 50; the first Nifty 500 scan needs more time to collect P/E data.')
        st.markdown('**Default screen:** 0 < P/E < 20 · Volume > 2× prior 20 sessions · RSI(14) > 50')
        return
    active_config, members, source = active
    if active_config != config:
        st.warning('Universe or calculation settings changed. Click Scan stocks to apply them. The results below use the previous scan settings.')
    last = st.session_state.get('scan_result')
    refresh = st.button('Refresh market data')
    due = auto and last and (datetime.now(IST) - datetime.fromisoformat(last[2])).total_seconds() >= 60
    if last is None or refresh or due:
        progress = st.progress(0, text='Starting scan…')
        try:
            last = scan(members, active_config[3], active_config[4], lambda n, s: progress.progress(n, text=s))
            st.session_state.scan_result = last
        except Exception as exc:
            st.error(f'Scan failed: {exc}')
            if last is None:
                return
            st.warning('Showing the previous successful scan.')
        finally:
            progress.empty()
    frame, issues, fetched = last
    st.caption(f'{source} · Scan completed {fetched}')
    if source.startswith('WARNING'):
        st.warning(source)
    if frame.empty:
        st.error('No usable market data returned. This is a data failure, not a zero-match screen. Check internet access, wait if Yahoo is throttling requests, and retry with a small custom list.')
        st.dataframe(issues, hide_index=True, use_container_width=True)
        return
    ranked = screen(frame, pe_max, volume_min, rsi_min)
    hits = ranked.loc[ranked['All pass']]
    a, b, c, d = st.columns(4)
    a.metric('Universe', len(members))
    b.metric('Usable price histories', len(frame))
    c.metric('Positive P/E available', int(frame['P/E'].gt(0).sum()))
    d.metric('Pass all three', len(hits))
    bar_date = frame['Bar date'].max()
    st.caption(f'Screening bar: {bar_date} · Price = daily close (₹), or provisional daily price when enabled. P/E = latest provider trailing P/E, fetched separately; not historical P/E.')
    age = (datetime.now(IST).date() - pd.Timestamp(bar_date).date()).days
    if age > 4:
        st.warning(f'Latest bar is {age} calendar days old. Check data freshness before using results.')
    if len(frame) < len(members) or frame['P/E'].isna().any():
        st.warning('Coverage is incomplete. Missing prices or P/E can prevent stocks from appearing in matches; see Data quality below.')
    match_tab, all_tab, quality_tab = st.tabs(['Matches', 'All scanned stocks', 'Data quality'])
    columns = ['Ticker', 'Company', 'Price ₹', 'P/E', 'Volume ratio', 'RSI', 'Score', 'Bar date', 'P/E pass', 'Volume pass', 'RSI pass', 'Volume', '20D avg volume', 'P/E fetched IST']
    formatting = {c: st.column_config.NumberColumn(c, format='%.2f') for c in ['Price ₹', 'P/E', 'Volume ratio', 'RSI', 'Score']}
    with match_tab:
        if hits.empty:
            st.info('No stocks passed all three filters in the available data. This is a valid result; adjust thresholds if needed.')
        st.dataframe(hits[columns], hide_index=True, use_container_width=True, column_config=formatting)
        st.download_button('Export matches CSV', hits[columns].to_csv(index=False).encode('utf-8-sig'), 'nse_matches.csv', 'text/csv')
    with all_tab:
        st.dataframe(ranked[columns], hide_index=True, use_container_width=True, column_config=formatting)
        st.download_button('Export full scan CSV', ranked.to_csv(index=False).encode('utf-8-sig'), 'nse_full_scan.csv', 'text/csv')
    with quality_tab:
        if issues.empty:
            st.success('No download or calculation issues reported in this scan.')
        else:
            st.dataframe(issues, hide_index=True, use_container_width=True)
            st.download_button('Export issues CSV', issues.to_csv(index=False), 'nse_data_issues.csv', 'text/csv')
results()
with st.expander('How the screen and ranking work'):
    st.markdown('''
- **All filters must pass.** Comparisons are strict; values equal to a threshold do not pass. Missing, zero or negative P/E never passes.
- **Volume ratio:** selected session volume ÷ mean volume of the preceding 20 sessions, excluding the selected session.
- **RSI:** Wilder smoothing, seeded with the first period’s average gains/losses, on one year of dividend/split-adjusted daily closes. Flat prices return 50.
- **Daily mode:** today is excluded before 16:00 IST. After 16:00 it is eligible if the provider has returned it. This is a time gate, not proof that a bar is final; special trading sessions are not calendar-validated.
- **Score:** 100 × [0.30 × clip(1 − P/E / P/E limit, 0, 1) + 0.40 × clip(volume ratio / (2 × volume limit), 0, 1) + 0.30 × RSI / 100]. Invalid P/E earns zero valuation points. Scores depend on your thresholds.
- Score is a transparent sorting heuristic, not the unspecified formula in the video, a return forecast, or a buy recommendation. High volume alone does not establish institutional buying.
- Yahoo Finance via yfinance is unofficial; missing data, delays and throttling are possible. No synthetic stock results are substituted. Personal research use only.
''')
