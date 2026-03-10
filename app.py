import streamlit as st
import yfinance as yf
import requests
import json
import os
import pandas as pd
from datetime import datetime

# הגדרות עיצוב - הוספנו כאן אייקון וכותרת
st.set_page_config(
    page_title="הבורסה של יונתן",
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# קוד CSS שגורם לאתר להיראות כמו אפליקציה (מסתיר כפתורים מיותרים)
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {
        bottom: 0px;
    }
    /* התאמה לטלפון - פחות רווחים */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- פונקציות ניהול נתונים (ללא שינוי) ---
def get_user_file(username):
    return f"portfolio_{username.lower()}.json"

def save_data(username, balance_ils, initial_funds, portfolio, buy_prices, history):
    data = {
        "balance_ils": balance_ils,
        "initial_funds": initial_funds,
        "portfolio": portfolio,
        "buy_prices": buy_prices,
        "history": history
    }
    with open(get_user_file(username), "w") as f:
        json.dump(data, f)

def load_data(username):
    filename = get_user_file(username)
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return None

@st.cache_data(ttl=300)
def get_market_data(tickers):
    try:
        usd_rate = requests.get("https://open.er-api.com/v6/latest/USD").json()['rates']['ILS']
    except:
        usd_rate = 3.65
    data = {}
    for t in tickers:
        stock = yf.Ticker(t)
        hist = stock.history(period="5y")
        if not hist.empty:
            curr = hist['Close'].iloc[-1]
            def calc_change(days=None, ytd=False):
                try:
                    if ytd:
                        start_val = hist[hist.index >= f"{datetime.now().year}-01-01"]['Close'].iloc[0]
                    else:
                        start_val = hist['Close'].iloc[-days]
                    return ((curr - start_val) / start_val) * 100
                except: return 0.0
            data[t] = {
                'usd': curr, 'ils': curr * usd_rate,
                '1w': calc_change(5), '1m': calc_change(21), '6m': calc_change(126),
                'ytd': calc_change(ytd=True), '1y': calc_change(252), '5y': calc_change(len(hist))
            }
    return usd_rate, data

# --- ממשק משתמש ---
st.sidebar.title("👤 חשבון")
user_list = ["בחר משתמש", "יונתן", "אפרת", "נסיון דמה"]
username = st.sidebar.selectbox("מי סוחר היום?", user_list)

if username == "בחר משתמש":
    st.title("📊 הבורסה של יונתן")
    st.write("ברוך הבא! בחר את השם שלך מהתפריט בצד כדי להתחיל.")
    # הצגת נתוני שוק כלליים גם למי שלא התחבר
    usd_rate, market = get_market_data(['NVDA', 'GLD', 'SHLD'])
    st.subheader("מצב השוק כרגע:")
    c1, c2, c3 = st.columns(3)
    for i, t in enumerate(['NVDA', 'GLD', 'SHLD']):
        with [c1, c2, c3][i]:
            st.metric(t, f"${market[t]['usd']:.2f}", f"{market[t]['1d'] if '1d' in market[t] else market[t]['1w']:.2f}%")
else:
    user_data = load_data(username)
    if user_data is None:
        st.subheader(f"אהלן {username}!")
        start_money = st.number_input("עם כמה שקלים נתחיל?", min_value=100, value=5000)
        if st.button("פתח תיק"):
            new_data = {"balance_ils": float(start_money), "initial_funds": float(start_money), "portfolio": {}, "buy_prices": {}, "history": []}
            save_data(username, **new_data)
            st.rerun()
        st.stop()

    balance_ils = user_data["balance_ils"]
    initial_funds = user_data["initial_funds"]
    portfolio = user_data["portfolio"]
    buy_prices = user_data["buy_prices"]
    history = user_data.get("history", [])

    usd_rate, market = get_market_data(['NVDA', 'GLD', 'SHLD'])

    st.title(f"התיק של {username}")
    
    # סיכום מהיר למעלה
    total_val_ils = balance_ils
    for t, qty in portfolio.items():
        total_val_ils += qty * market[t]['usd'] * usd_rate
    
    overall_profit = total_val_ils - initial_funds
    st.metric("שווי כולל", f"₪{total_val_ils:,.0f}", f"{overall_profit:,.0f} ₪")

    # טאבים לנוחות בטלפון
    tab1, tab2, tab3 = st.tabs(["📉 מסחר", "💼 התיק שלי", "📜 היסטוריה"])

    with tab1:
        for t in ['NVDA', 'GLD', 'SHLD']:
            m = market[t]
            with st.expander(f"{t}: ₪{m['ils']:.0f}"):
                st.write(f"מחיר דולרי: ${m['usd']:.2f}")
                st.write(f"עלייה בשנה: {m['1y']:.1f}%")
                qty_buy = st.number_input(f"כמות", min_value=0, step=1, key=f"b_{t}")
                if st.button(f"קנה {t}", key=f"btn_{t}"):
                    cost = qty_buy * m['ils']
                    if cost <= balance_ils:
                        if t in portfolio:
                            old_q = portfolio[t]
                            buy_prices[t] = ((old_q * buy_prices[t]) + (qty_buy * m['usd'])) / (old_q + qty_buy)
                            portfolio[t] += qty_buy
                        else:
                            portfolio[t], buy_prices[t] = qty_buy, m['usd']
                        balance_ils -= cost
                        history.append({"תאריך": datetime.now().strftime("%d/%m/%Y %H:%M"), "פעולה": "קנייה", "מניה": t, "כמות": qty_buy, "מחיר": f"${m['usd']:.2f}"})
                        save_data(username, balance_ils, initial_funds, portfolio, buy_prices, history)
                        st.rerun()
                    else: st.error("אין מספיק כסף!")

    with tab2:
        if not portfolio:
            st.write("אין מניות כרגע.")
        else:
            for t, qty in list(portfolio.items()):
                curr_p, buy_p = market[t]['usd'], buy_prices[t]
                val_ils = qty * curr_p * usd_rate
                profit_pct = ((curr_p - buy_p) / buy_p) * 100
                st.write(f"**{t}** | {qty} יחידות")
                st.write(f"שווי: ₪{val_ils:,.0f} ({profit_pct:.1f}%)")
                sell_q = st.number_input("כמות למכירה", min_value=1, max_value=int(qty), key=f"s_qty_{t}")
                if st.button(f"מכור", key=f"s_btn_{t}"):
                    balance_ils += (sell_q * market[t]['ils'])
                    portfolio[t] -= sell_q
                    history.append({"תאריך": datetime.now().strftime("%d/%m/%Y %H:%M"), "פעולה": "מכירה", "מניה": t, "כמות": sell_q, "מחיר": f"${curr_p:.2f}"})
                    if portfolio[t] <= 0: del portfolio[t], buy_prices[t]
                    save_data(username, balance_ils, initial_funds, portfolio, buy_prices, history)
                    st.rerun()
                st.divider()

    with tab3:
        if history:
            st.table(pd.DataFrame(history)[::-1])

    if st.sidebar.button("התנתק / איפוס"):
        st.rerun()
