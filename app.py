import streamlit as st
import yfinance as yf
import requests
import json
import os
import pandas as pd

st.set_page_config(page_title="מערכת מסחר רב-משתמשים", layout="wide")

INITIAL_FUNDS = 5000.0
SAVE_FILE_PREFIX = "portfolio_"

def save_data(username, balance, portfolio, buy_prices):
    data = {"balance_ils": balance, "portfolio": portfolio, "buy_prices": buy_prices}
    with open(f"{SAVE_FILE_PREFIX}{username.lower()}.json", "w") as f:
        json.dump(data, f)

def load_data(username):
    filename = f"{SAVE_FILE_PREFIX}{username.lower()}.json"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {"balance_ils": INITIAL_FUNDS, "portfolio": {}, "buy_prices": {}}

@st.cache_data(ttl=60)
def get_market_data():
    try:
        usd_rate = requests.get("https://open.er-api.com/v6/latest/USD").json()['rates']['ILS']
    except:
        usd_rate = 3.65
    tickers = ['NVDA', 'GLD', 'SHLD']
    prices = {t: yf.Ticker(t).history(period="1d")['Close'].iloc[-1] for t in tickers}
    return usd_rate, prices

# --- ממשק משתמש ---
st.sidebar.title("👤 כניסה למערכת")
username = st.sidebar.text_input("הכנס שם משתמש:", value="").strip()

if not username:
    st.title("🚀 מערכת המסחר של יונתן")
    st.info("הכנס שם משתמש בתפריט הצדדי כדי להתחיל.")
else:
    user_data = load_data(username)
    balance = user_data["balance_ils"]
    portfolio = user_data["portfolio"]
    buy_prices = user_data["buy_prices"]
    usd_rate, current_prices = get_market_data()

    st.title(f"שלום, {username} 👋")
    st.sidebar.metric("יתרת מזומן", f"₪{balance:,.0f}")

    if st.sidebar.button("אפס תיק (Reset)"):
        save_data(username, INITIAL_FUNDS, {}, {})
        st.rerun()

    # קניית מניות
    st.subheader("🛒 קניית מניות")
    cols = st.columns(3)
    for i, ticker in enumerate(['NVDA', 'GLD', 'SHLD']):
        with cols[i]:
            p_usd = current_prices[ticker]
            p_ils = p_usd * usd_rate
            st.write(f"**{ticker}**: ₪{p_ils:,.0f}")
            qty_buy = st.number_input(f"כמות לקנייה", min_value=0, step=1, key=f"buy_{ticker}")
            if st.button(f"קנה {ticker}", key=f"btn_buy_{ticker}"):
                if qty_buy > 0:
                    cost = qty_buy * p_ils
                    if cost <= balance:
                        if ticker in portfolio:
                            old_qty = portfolio[ticker]
                            buy_prices[ticker] = ((old_qty * buy_prices[ticker]) + (qty_buy * p_usd)) / (old_qty + qty_buy)
                            portfolio[ticker] += qty_buy
                        else:
                            portfolio[ticker] = qty_buy
                            buy_prices[ticker] = p_usd
                        balance -= cost
                        save_data(username, balance, portfolio, buy_prices)
                        st.success(f"קנית {qty_buy} מניות!")
                        st.rerun()
                    else: st.error("אין מספיק כסף!")

    st.divider()

    # ניהול התיק ומכירה
    st.subheader("📋 התיק שלי")
    if not portfolio:
        st.write("אין מניות כרגע.")
    else:
        total_val_ils = balance
        for t, qty in list(portfolio.items()):
            if qty <= 0: continue
            curr_p, buy_p = current_prices[t], buy_prices[t]
            val_ils = qty * curr_p * usd_rate
            total_val_ils += val_ils
            profit_pct = ((curr_p - buy_p) / buy_p) * 100
            
            with st.expander(f"{t} - {qty} יחידות (₪{val_ils:,.0f})"):
                c1, c2 = st.columns(2)
                c1.write(f"מחיר קנייה: ${buy_p:.2f}")
                c1.write(f"רווח: {profit_pct:.2f}%")
                
                # מנגנון מכירה חלקית
                sell_qty = c2.number_input("כמה למכור?", min_value=1, max_value=int(qty), value=1, key=f"sq_{t}")
                if c2.button(f"מכור {sell_qty} מניות", key=f"sb_{t}"):
                    balance += (sell_qty * curr_p * usd_rate)
                    portfolio[t] -= sell_qty
                    if portfolio[t] <= 0:
                        del portfolio[t]
                        del buy_prices[t]
                    save_data(username, balance, portfolio, buy_prices)
                    st.toast(f"מכרת {sell_qty} מניות!")
                    st.rerun()

        st.divider()
        overall_profit = total_val_ils - INITIAL_FUNDS
        st.metric("שווי תיק כולל", f"₪{total_val_ils:,.0f}", f"{overall_profit:,.0f} ₪")