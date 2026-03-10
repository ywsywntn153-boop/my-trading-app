import streamlit as st
import yfinance as yf
import requests
import json
import os
import pandas as pd
from datetime import datetime

# הגדרות עיצוב - נקיות יותר
st.set_page_config(
    page_title="הבורסה של יונתן",
    page_icon="📈", 
    layout="wide"
)

# CSS מתוקן - משאיר את היכולת לנווט ומעצב את הכפתורים
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    footer {visibility: hidden;}
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .block-container {
        padding-top: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- פונקציות ניהול נתונים ---
def get_user_file(username):
    return f"portfolio_{username.lower()}.json"

def save_data(username, balance_ils, initial_funds, portfolio, buy_prices, history):
    data = {"balance_ils": balance_ils, "initial_funds": initial_funds, "portfolio": portfolio, "buy_prices": buy_prices, "history": history}
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
                '1w': calc_change(5), '1m': calc_change(21), '1y': calc_change(252)
            }
    return usd_rate, data

# --- מסך כניסה ראשי ---
if 'user' not in st.session_state:
    st.session_state.user = "בחר משתמש"

if st.session_state.user == "בחר משתמש":
    st.title("📈 הבורסה של יונתן")
    st.subheader("כניסה למערכת")
    user_list = ["בחר משתמש", "יונתן", "אפרת", "נסיון דמה"]
    selected = st.selectbox("מי סוחר היום?", user_list)
    if selected != "בחר משתמש":
        st.session_state.user = selected
        st.rerun()
else:
    username = st.session_state.user
    user_data = load_data(username)
    
    # כפתור התנתקות קטן למעלה
    if st.button(f"👤 מחובר כ: {username} (לחץ להתנתקות)"):
        st.session_state.user = "בחר משתמש"
        st.rerun()

    if user_data is None:
        st.subheader(f"אהלן {username}!")
        start_money = st.number_input("עם כמה שקלים נתחיל?", min_value=100, value=5000)
        if st.button("פתח תיק חדש"):
            save_data(username, float(start_money), float(start_money), {}, {}, [])
            st.rerun()
        st.stop()

    # טעינת נתונים
    balance_ils = user_data["balance_ils"]
    initial_funds = user_data["initial_funds"]
    portfolio = user_data["portfolio"]
    buy_prices = user_data["buy_prices"]
    history = user_data.get("history", [])
    usd_rate, market = get_market_data(['NVDA', 'GLD', 'SHLD'])

    # חישוב שווי כולל
    total_val_ils = balance_ils
    for t, qty in portfolio.items():
        total_val_ils += qty * market[t]['usd'] * usd_rate
    
    overall_profit = total_val_ils - initial_funds
    st.metric("שווי תיק כולל", f"₪{total_val_ils:,.0f}", f"{overall_profit:,.0f} ₪")

    # טאבים
    tab1, tab2, tab3 = st.tabs(["📉 קנייה", "💼 התיק שלי", "📜 היסטוריה"])

    with tab1:
        for t in ['NVDA', 'GLD', 'SHLD']:
            m = market[t]
            with st.expander(f"{t}: ₪{m['ils']:.0f}"):
                st.write(f"מחיר: ${m['usd']:.2f} | שינוי שנתי: {m['1y']:.1f}%")
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
        st.write(f"**מזומן פנוי:** ₪{balance_ils:,.0f}")
        if not portfolio:
            st.info("אין מניות בתיק.")
        else:
            for t, qty in list(portfolio.items()):
                curr_p, buy_p = market[t]['usd'], buy_prices[t]
                val_ils = qty * curr_p * usd_rate
                profit_pct = ((curr_p - buy_p) / buy_p) * 100
                with st.container():
                    st.write(f"**{t}** ({qty} יחידות)")
                    st.write(f"שווי: ₪{val_ils:,.0f} ({profit_pct:.1f}%)")
                    sell_q = st.number_input("כמות למכירה", min_value=1, max_value=int(qty), key=f"s_qty_{t}")
                    if st.button(f"מכור {t}", key=f"s_btn_{t}"):
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
