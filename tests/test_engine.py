from datetime import datetime
import numpy as np
import pandas as pd
import pytest
from engine import IST, wilder_rsi, metrics, eligible_bars, screen
from data import parse_symbols, parse_constituents

@pytest.mark.parametrize('values,expected', [(range(1,40),100), (range(40,1,-1),0), ([12]*40,50)])
def test_rsi_extremes(values, expected):
    assert wilder_rsi(pd.Series(values)).iloc[-1] == expected

def test_wilder_reference():
    prices = [44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28,46.00]
    result = wilder_rsi(pd.Series(prices))
    assert result.iloc[14] == pytest.approx(70.464, abs=.001)
    assert result.iloc[15] == pytest.approx(66.2496, abs=.001)

def bars():
    return pd.DataFrame({'Close':np.arange(1,31), 'Volume':[100]*29+[300]}, index=pd.date_range('2026-09-01', periods=30))

def test_volume_excludes_current():
    m=metrics(bars(), now=datetime(2026,10,1,12,tzinfo=IST))
    assert m['Volume ratio'] == 3
    assert m['20D avg volume'] == 100

def test_session_gate():
    now = datetime(2026,9,30,10,tzinfo=IST)
    assert len(eligible_bars(bars(), now=now)) == 29
    assert len(eligible_bars(bars(), True, now)) == 30
    assert len(eligible_bars(bars(), now=now.replace(hour=16))) == 30

def test_invalid_history():
    b=bars(); b['Volume']=0
    with pytest.raises(ValueError): metrics(b)
    with pytest.raises(ValueError): metrics(bars().iloc[:5])

def test_strict_thresholds_and_missing_pe():
    f=pd.DataFrame({'Ticker':list('ABCDEFG'), 'P/E':[10,20,-3,np.nan,10,10,0], 'Volume ratio':[3,3,3,3,2,3,3], 'RSI':[60,60,60,60,60,50,60]})
    out=screen(f)
    assert out.loc[out['All pass'],'Ticker'].tolist() == ['A']
    assert out['Score'].between(0,100).all()

def test_symbol_validation():
    assert parse_symbols('tcs, TCS.NS; M&M')['Symbol'].tolist()==['TCS','M&M']
    with pytest.raises(ValueError): parse_symbols('../../a')
    with pytest.raises(ValueError): parse_symbols('AAPL.BO')
    with pytest.raises(ValueError): parse_constituents('<html>blocked</html>')
