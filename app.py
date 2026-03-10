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

def save_data(username, balance, initial_funds, portfolio, buy_prices, history):
    data = {
        "balance_ils": balance,
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

# משיכת נתוני שוק מתקדמים
@st.cache_data(ttl=300)
def get_market_data(tickers):
    try:
        usd_rate = requests.get("https://open.er-api.com/v6/latest/USD").json()['rates']['ILS']
    except:
        usd_rate = 3.65
    
    data = {}
    for t in tickers:
        stock = yf.Ticker(t)
        # מושך היסטוריה של 5 שנים לחישובים
        hist = stock.history(period="5y")
        if not hist.empty:
            curr = hist['Close'].iloc[-1]
            
            def calc_change(days=None, ytd=False):
                try:
                    if ytd:
                        year_start = hist[hist.index >= f"{datetime.now().year}-01-01"]
                        start_val = year_start['Close'].iloc[0]
                    else:
                        start_val = hist['Close'].iloc[-days]
                    return ((curr - start_val) / start_val) * 100
                except: return 0.0

            data[t] = {
                'usd': curr,
                'ils': curr * usd_rate,
                '1w': calc_change(5),
                '1m': calc_change(21),
                '6m': calc_change(126),
                'ytd': calc_change(ytd=True),
                '1y': calc_change(252),
                '5y': calc_change(len(hist))
            }
    return usd_rate, data

# --- תפריט צדדי וכניסה ---
st.sidebar.title("👤 כניסה למערכת")
user_list = ["בחר משתמש", "יונתן", "אפרת", "נסיון דמה"]
username = st.sidebar.selectbox("מי סוחר היום?", user_list)

if username == "בחר משתמש":
    st.title("🚀 ברוכים הבאים לאפליקציית המסחר")
    st.info("בחר משתמש מהתפריט הצדדי כדי להתחיל")
else:
    # טעינה או הגדרה ראשונית
    user_data = load_data(username)
    
    if user_data is None:
        st.subheader(f"ברוך הבא, {username}!")
        start_money = st.number_input("עם כמה שקלים תרצה להתחיל את התיק?", min_value=100, value=5000)
        if st.button("פתח תיק חדש"):
            user_data = {"balance_ils": start_money, "initial_funds": start_money, "portfolio": {}, "buy_prices": {}, "history": []}
            save_data(username, **user_data)
            st.rerun()
        st.stop()

    balance = user_data["balance_ils"]
    initial_funds = user_data["initial_funds"]
    portfolio = user_data["portfolio"]
    buy_prices = user_data["buy_prices"]
    history = user_data.get("history", [])

    usd_rate, market = get_market_data(['NVDA', 'GLD', 'SHLD'])

    st.title(f"תיק המסחר של {username}")
    st.sidebar.metric("מזומן פנוי", f"₪{balance:,.0f}")
    
    if st.sidebar.button("אפס תיק (Reset)"):
        os.remove(get_user_file(username))
        st.rerun()

    # --- מניות למסחר ---
    st.subheader("📊 נתוני שוק וביצועים")
    for t in ['NVDA', 'GLD', 'SHLD']:
        if t in market:
            m = market[t]
            with st.expander(f"{t}: ${m['usd']:.2f} (₪{m['ils']:.0f})"):
                # טבלת ביצועים
                stats = {
                    "טווח זמן": ["שבוע", "חודש", "6 חודשים", "YTD (מתחילת שנה)", "שנה", "5 שנים"],
                    "שינוי באחוזים": [f"{m['1w']:.2f}%", f"{m['1m']:.2f}%", f"{m['6m']:.2f}%", f"{m['ytd']:.2f}%", f"{m['1y']:.2f}%", f"{m['5y']:.2f}%"]
                }
                st.table(pd.DataFrame(stats))
                
                # כפתור קנייה
                qty_buy = st.number_input(f"כמות לקנייה", min_value=0, step=1, key=f"b_{t}")
                if st.button(f"קנה {t}", key=f"btn_{t}"):
                    cost = qty_buy * m['ils']
                    if cost <= balance:
                        if t in portfolio:
                            old_qty = portfolio[t]
                            buy_prices[t] = ((old_qty * buy_prices[t]) + (qty_buy * m['usd'])) / (old_qty + qty_buy)
                            portfolio[t] += qty_buy
                        else:
                            portfolio[t] = qty_buy
                            buy_prices[t] = m['usd']
                        balance -= cost
                        history.append({"date": str(datetime.now().strftime("%d/%m/%Y %H:%M")), "type": "קנייה", "ticker": t, "qty": qty_buy, "price": f"${m['usd']:.2f}"})
                        save_data(username, balance, initial_funds, portfolio, buy_prices, history)
                        st.success("הקנייה בוצעה!")
                        st.rerun()
                    else: st.error("אין מספיק מזומן")

    st.divider()

    # --- התיק שלי ---
    st.subheader("💼 המניות שלי")
    total_val_ils = balance
    if not portfolio:
        st.write("אין מניות בתיק.")
    else:
        for t, qty in list(portfolio.items()):
            if qty <= 0: continue
            curr_p, buy_p = market[t]['usd'], buy_prices[t]
            val_ils = qty * curr_p * usd_rate
            total_val_ils += val_ils
            profit_pct = ((curr_p - buy_p) / buy_p) * 100
            profit_ils = (curr_p - buy_p) * qty * usd_rate
            
            with st.container():
                st.write(f"### {t} ({qty} יחידות)")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("מחיר קנייה", f"${buy_p:.2f}", f"₪{buy_p * usd_rate:.0f}")
                c2.metric("מחיר נוכחי", f"${curr_p:.2f}", f"₪{curr_p * usd_rate:.0f}")
                c3.metric("רווח/הפסד %", f"{profit_pct:.2f}%")
                c4.metric("רווח בשקלים", f"₪{profit_ils:,.0f}")
                
                sell_qty = st.number_input("כמות למכירה", min_value=1, max_value=int(qty), key=f"s_qty_{t}")
                if st.button(f"מכור {sell_qty} מתוך {t}", key=f"s_btn_{t}"):
                    balance += (sell_qty * market[t]['ils'])
                    portfolio[t] -= sell_qty
                    history.append({"date": str(datetime.now().strftime("%d/%m/%Y %H:%M")), "type": "מכירה", "ticker": t, "qty": sell_qty, "price": f"${curr_p:.2f}"})
                    if portfolio[t] <= 0:
                        del portfolio[t]
                        del buy_prices[t]
                    save_data(username, balance, initial_funds, portfolio, buy_prices, history)
                    st.rerun()
            st.divider()

    # סיכום ביצועים
    overall_profit = total_val_ils - initial_funds
    overall_pct = (overall_profit / initial_funds) * 100
    st.subheader("💰 סיכום תיק כולל")
    col1, col2, col3 = st.columns(3)
    col1.metric("שווי כולל", f"₪{total_val_ils:,.0f}")
    col2.metric("רווח/הפסד נקי", f"₪{overall_profit:,.0f}")
    col3.metric("תשואה כוללת", f"{overall_pct:.2f}%")

    # היסטוריית עסקאות
    if history:
        with st.expander("📜 היסטוריית עסקאות"):
            st.table(pd.DataFrame(history).sort_index(ascending=False))
