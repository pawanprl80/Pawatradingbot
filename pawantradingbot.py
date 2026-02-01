import streamlit as st
import pandas as pd
import numpy as np
import datetime, time, threading, requests
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh
from urllib.parse import urlencode, unquote_plus
from cryptography.hazmat.primitives.asymmetric import ed25519

# --- 1. SETTINGS & AUTH ---
st.set_page_config(page_title="TITAN V5 PRO | LIGHT MODE", layout="wide")
st_autorefresh(interval=5000, key="v5_light_pulse")

API_KEY = "d4a0b5668e86d5256ca1b8387dbea87fc64a1c2e82e405d41c256c459c8f338d"
API_SECRET = "a5576f4da0ae455b616755a8340aef2b0eff4d05a775f82bc00352f079303511"
BASE_URL = "https://dma.coinswitch.co"

# --- 2. CUSTOM LIGHT NAVY/WHITE THEME ---
st.markdown("""
<style>
    /* Background: Light Navy Blue tint (Almost White) */
    .stApp { 
        background-color: #f0f4f8; 
        color: #1e293b; 
    }
    
    /* Card Styles */
    .metric-container {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        margin-bottom: 20px;
    }

    /* LTP Logic Colors */
    .ltp-green { color: #16a34a; font-size: 28px; font-weight: 800; }
    .ltp-red { color: #dc2626; font-size: 28px; font-weight: 800; }
    
    /* Pair Name Color */
    .pair-title { color: #1e3a8a; font-size: 24px; font-weight: 900; }
    
    .status-pink { color: #db2777; font-weight: bold; padding: 5px 10px; background: #fdf2f8; border-radius: 5px; border: 1px solid #f9a8d4; }
    .status-shield { color: #475569; font-weight: bold; }
    
    .validator-box {
        background: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #1e3a8a;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
def generate_headers(method, endpoint, params=None):
    epoch = str(int(time.time()))
    path = endpoint
    if method == "GET" and params:
        path = unquote_plus(f"{endpoint}?{urlencode(params)}")
    msg = method + path + epoch
    pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(API_SECRET))
    sig = pk.sign(msg.encode()).hex()
    return {'X-AUTH-SIGNATURE': sig, 'X-AUTH-APIKEY': API_KEY, 'X-AUTH-EPOCH': epoch, 'Content-Type': 'application/json'}

if "master_cache" not in st.session_state:
    st.session_state.master_cache = {"data": [], "sync": "Never"}

def run_engine():
    endpoint = "/v5/market/kline"
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]
    while True:
        results = []
        for s in symbols:
            try:
                params = {"symbol": s, "interval": "5", "limit": "100", "category": "linear"}
                res = requests.get(f"{BASE_URL}{endpoint}", headers=generate_headers("GET", endpoint, params), params=params).json()
                df = pd.DataFrame(res['result']['list'], columns=['t', 'o', 'h', 'l', 'c', 'v', 'to'])
                df[['o','h','l','c']] = df[['o','h','l','c']].apply(pd.to_numeric)
                df = df.iloc[::-1].reset_index(drop=True)
                
                # Indicators
                st_df = ta.supertrend(df['h'], df['l'], df['c'], 10, 3)
                bb = ta.bbands(df['c'], 20, 2)
                macd = ta.macd(df['c'])
                rsi = ta.rsi(df['c'], 14)
                df = pd.concat([df, st_df, bb, macd, rsi], axis=1)
                
                last, prev = df.iloc[-1], df.iloc[-2]
                
                # Ghost Resistance Logic
                red_seg = df[df['SUPERTd_10_3.0'] == -1]
                ghost_high = red_seg['h'].max() if not red_seg.empty else 0
                
                # 7-POINT TITAN RULES
                p1 = last['SUPERTd_10_3.0'] == 1
                p2 = last['MACDh_12_26_9'] > prev['MACDh_12_26_9']
                p3 = last['MACD_12_26_9'] > 0
                p4 = last['SUPERT_10_3.0'] > last['BBM_20_2.0'] # CROSS MIDBAND CHECK
                p5 = last['BBU_20_2.0'] > prev['BBU_20_2.0']
                p6 = last['SUPERT_10_3.0'] > ghost_high if p1 else False
                p7 = last['RSI_14'] >= 70
                
                is_shield = last['SUPERT_10_3.0'] < last['BBL_20_2.0']
                is_pink = (p1 and p2 and p3 and p4 and p5 and p6 and p7) and not is_shield
                
                # Trend for LTP Color
                ltp_color = "ltp-green" if last['c'] >= prev['c'] else "ltp-red"
                
                results.append({
                    "Symbol": s, "LTP": last['c'], "ST": last['SUPERT_10_3.0'],
                    "Ghost": ghost_high, "Pink": is_pink, "Shield": is_shield,
                    "Points": [p1, p2, p3, p4, p5, p6, p7], "Mid": last['BBM_20_2.0'],
                    "RSI": last['RSI_14'], "ltp_class": ltp_color, "df": df
                })
            except: continue
        st.session_state.master_cache["data"] = results
        st.session_state.master_cache["sync"] = datetime.datetime.now().strftime("%H:%M:%S")
        time.sleep(5)

if "bg_loop" not in st.session_state:
    threading.Thread(target=run_engine, daemon=True).start()
    st.session_state.bg_loop = True

# --- 4. UI DISPLAY ---
st.title("🛡️ TITAN V5 PRO | VALIDATOR")
st.write(f"Last Sync: {st.session_state.master_cache['sync']}")

data = st.session_state.master_cache["data"]

if data:
    for d in data:
        with st.container():
            # Main Row
            col1, col2, col3, col4 = st.columns([2, 2, 3, 2])
            
            with col1:
                st.markdown(f"<div class='pair-title'>{d['Symbol']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='{d['ltp_class']}'>{d['LTP']:.2f}</div>", unsafe_allow_html=True)
            
            with col2:
                st.write("**Indicator Values**")
                st.write(f"ST Value: `{d['ST']:.2f}`")
                st.write(f"Midband: `{d['Mid']:.2f}`")
            
            with col3:
                st.write("**Signal Validator**")
                pts = d['Points']
                st.markdown(f"""
                <div class="validator-box">
                    {'✅' if pts[0] else '❌'} Supertrend Green<br>
                    {'✅' if pts[3] else '❌'} <b>Cross Midband:</b> {d['ST']:.2f} > {d['Mid']:.2f}<br>
                    {'✅' if pts[5] else '❌'} Ghost Breakout (> {d['Ghost']:.2f})<br>
                    {'✅' if pts[6] else '❌'} RSI Strength ({d['RSI']:.1f})
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                status_html = ""
                if d['Pink']: status_html = "<span class='status-pink'>💎 PINK ALERT</span>"
                elif d['Shield']: status_html = "<span class='status-shield'>🛡️ CALL SHIELD</span>"
                else: status_html = "<span>⌛ SCANNING</span>"
                st.markdown(f"<div style='margin-top:20px'>{status_html}</div>", unsafe_allow_html=True)
            
            st.divider()

else:
    st.info("Initializing Engine... Please wait 5 seconds.")

# --- 5. MINI CHART MODAL (Optional) ---
with st.sidebar:
    st.header("Visual Settings")
    show_charts = st.checkbox("Show Visual Charts", value=True)
    if show_charts and data:
        st.subheader("Quick Chart")
        sel = st.selectbox("Select Pair", [x['Symbol'] for x in data])
        target = next(x for x in data if x['Symbol'] == sel)
        df = target['df']
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['o'], high=df['h'], low=df['l'], close=df['c'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['SUPERT_10_3.0'], line=dict(color='#2563eb')))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
