import streamlit as st
import yfinance as yf
import requests
import json
import os
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="מערכת המסחר של יונתן", layout="wide")

# פונקציות ניהול נתונים
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

# משיכת נתוני שוק
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

# --- תפריט צדדי ---
st.sidebar.title("👤 כניסה למערכת")
user_list = ["בחר משתמש", "יונתן", "אפרת", "נסיון דמה"]
username = st.sidebar.selectbox("מי סוחר היום?", user_list)

if username == "בחר משתמש":
    st.title("🚀 ברוכים הבאים לאפליקציית המסחר")
    st.info("אנא בחר משתמש מהתפריט הצדדי")
else:
    user_data = load_data(username)
    if user_data is None:
        st.subheader(f"ברוך הבא, {username}!")
        start_money = st.number_input("עם כמה שקלים תרצה להתחיל?", min_value=100, value=5000)
        if st.button("פתח תיק חדש"):
            new_data = {"balance_ils": float(start_money), "initial_funds": float(start_money), "portfolio": {}, "buy_prices": {}, "history": []}
            save_data(username, **new_data)
            st.rerun()
        st.stop()

    # טעינת משתנים
    balance_ils = user_data["balance_ils"]
    initial_funds = user_data["initial_funds"]
    portfolio = user_data["portfolio"]
    buy_prices = user_data["buy_prices"]
    history = user_data.get("history", [])

    usd_rate, market = get_market_data(['NVDA', 'GLD', 'SHLD'])

    st.title(f"תיק המסחר של {username}")
    st.sidebar.metric("מזומן פנוי", f"₪{balance_ils:,.0f}")
    
    if st.sidebar.button("אפס תיק (Reset)"):
        os.remove(get_user_file(username))
        st.rerun()

    # --- מניות למסחר ---
    st.subheader("📊 מניות וביצועי שוק")
    for t in ['NVDA', 'GLD', 'SHLD']:
        m = market[t]
        with st.expander(f"{t}: ${m['usd']:.2f} (₪{m['ils']:.0f})"):
            stats_df = pd.DataFrame({
                "טווח": ["שבוע", "חודש", "6 חודשים", "YTD", "שנה", "5 שנים"],
                "שינוי %": [f"{m['1w']:.2f}%", f"{m['1m']:.2f}%", f"{m['6m']:.2f}%", f"{m['ytd']:.2f}%", f"{m['1y']:.2f}%", f"{m['5y']:.2f}%"]
            })
            st.table(stats_df)
            
            qty_buy = st.number_input(f"כמה יחידות לקנות?", min_value=0, step=1, key=f"buy_{t}")
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

    st.divider()

    # --- התיק שלי ---
    st.subheader("💼 המניות שלי")
    total_val_ils = balance_ils
    if not portfolio:
        st.write("אין מניות כרגע.")
    else:
        for t, qty in list(portfolio.items()):
            curr_p, buy_p = market[t]['usd'], buy_prices[t]
            val_ils = qty * curr_p * usd_rate
            total_val_ils += val_ils
            profit_pct = ((curr_p - buy_p) / buy_p) * 100
            
            with st.container():
                st.write(f"### {t} ({qty} יחידות)")
                c1, c2, c3 = st.columns(3)
                c1.write(f"**מחיר קנייה:** ${buy_p:.2f} (₪{buy_p*usd_rate:.0f})")
                c2.write(f"**מחיר עכשיו:** ${curr_p:.2f} (₪{curr_p*usd_rate:.0f})")
                c3.metric("רווח/הפסד %", f"{profit_pct:.2f}%")
                
                sell_q = st.number_input("כמות למכירה", min_value=1, max_value=int(qty), key=f"sell_q_{t}")
                if st.button(f"מכור {sell_q} מתוך {t}", key=f"sell_btn_{t}"):
                    balance_ils += (sell_q * market[t]['ils'])
                    portfolio[t] -= sell_q
                    history.append({"תאריך": datetime.now().strftime("%d/%m/%Y %H:%M"), "פעולה": "מכירה", "מניה": t, "כמות": sell_q, "מחיר": f"${curr_p:.2f}"})
                    if portfolio[t] <= 0:
                        del portfolio[t], buy_prices[t]
                    save_data(username, balance_ils, initial_funds, portfolio, buy_prices, history)
                    st.rerun()
            st.divider()

    # סיכום
    overall_profit = total_val_ils - initial_funds
    overall_pct = (overall_profit / initial_funds) * 100
    st.subheader("💰 סיכום כולל")
    col1, col2, col3 = st.columns(3)
    col1.metric("שווי תיק", f"₪{total_val_ils:,.0f}")
    col2.metric("רווח/הפסד נקי", f"₪{overall_profit:,.0f}")
    col3.metric("תשואה", f"{overall_pct:.2f}%")

    if history:
        with st.expander("📜 היסטוריית עסקאות"):
            st.table(pd.DataFrame(history)[::-1])

