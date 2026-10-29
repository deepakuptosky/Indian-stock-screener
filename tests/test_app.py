from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest

def fake_scan(*args, **kwargs):
    frame=pd.DataFrame([{'Ticker':'TEST','Company':'Test fixture (not a real quote)', 'Price ₹':100.,'P/E':10., 'Volume ratio':3., 'RSI':60., 'Bar date':'2026-10-27','Volume':300,'20D avg volume':100,'P/E fetched IST':'2026-10-28T10:00:00+05:30'}])
    return frame,pd.DataFrame(columns=['Ticker','Issue']),'2026-10-28T10:00:00+05:30'

def test_app_controls():
    at=AppTest.from_file('../app.py').run()
    assert not at.exception
    at.selectbox[0].select('Custom symbols').run()
    with patch('data.scan',side_effect=fake_scan):
        at.button[0].click().run()
        assert not at.exception
        assert at.metric[3].value == '1'
        at.number_input[0].set_value(5).run()
        assert at.metric[3].value == '0'
        assert not at.exception

def test_empty_data_is_error():
    at=AppTest.from_file('../app.py').run()
    at.selectbox[0].select('Custom symbols').run()
    with patch('data.scan',return_value=(pd.DataFrame(),pd.DataFrame([{'Ticker':'TCS','Issue':'Unavailable'}]),'2026-10-28T10:00:00+05:30')):
        at.button[0].click().run()
        assert not at.exception
        assert any('data failure' in e.value for e in at.error)
