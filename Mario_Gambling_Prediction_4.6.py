import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import random

st.set_page_config(page_title="Bet365 Gambling Prediction", layout="wide")
st.title("🎯 Mario Gambling Prediction - Bet365 Edition")

# ------------------- Selenium Setup -------------------
chrome_options = Options()
chrome_options.add_argument("--headless")  # 不開視窗
chrome_options.add_argument("--disable-gpu")
service = Service(r"C:\chromedriver\chromedriver.exe")

# ------------------- 抓取比賽資料 -------------------
@st.cache_data(ttl=600)
def fetch_matches():
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get("https://www.bet365.com/#/AC/B1/")
    time.sleep(10)  # 等待網頁加載
    
    # 抓取聯賽
    league_elements = driver.find_elements(By.CSS_SELECTOR, "div.ipo-GroupButton_Text")
    leagues = [el.text for el in league_elements if el.text]

    match_data = []
    for league_el in league_elements[:3]:  # 範例抓前三個聯賽
        try:
            league_name = league_el.text
            league_el.click()
            time.sleep(3)

            matches = driver.find_elements(By.CSS_SELECTOR, "div.sl-ParticipantFixture")
            for m in matches:
                try:
                    home = m.find_element(By.CSS_SELECTOR, "div.sl-ParticipantHome").text
                    away = m.find_element(By.CSS_SELECTOR, "div.sl-ParticipantAway").text
                    odds = m.find_elements(By.CSS_SELECTOR, "div.gl-Market_Odds")
                    odds_values = [o.text for o in odds]
                    match_data.append({
                        "league": league_name,
                        "home": home,
                        "away": away,
                        "odds": odds_values
                    })
                except:
                    continue
        except:
            continue
    driver.quit()
    return match_data

matches = fetch_matches()

# ------------------- 預測函數 -------------------
def predict_score():
    home_goals = random.choices([0,1,2,3,4], weights=[10,20,40,20,10])[0]
    away_goals = random.choices([0,1,2,3,4], weights=[10,20,40,20,10])[0]
    return home_goals, away_goals

def judge_over_under(total_goals, line=2.5):
    return "⚡大球" if total_goals > line else "💧小球"

def judge_trend(home, away):
    if home > away:
        return "🏆 主勝"
    elif home < away:
        return "💔 客勝"
    else:
        return "🤝 和局"

# ------------------- 左邊選聯賽 -------------------
league_list = list({m['league'] for m in matches})
selected_league = st.sidebar.selectbox("選擇聯賽", league_list)

# ------------------- 顯示比賽預測 -------------------
st.subheader(f"🏟️ {selected_league} 即將比賽")

for match in matches:
    if match['league'] != selected_league:
        continue

    home_goal, away_goal = predict_score()
    total_goals = home_goal + away_goal
    ou = judge_over_under(total_goals)
    trend = judge_trend(home_goal, away_goal)

    st.markdown(f"**{match['home']} vs {match['away']}**")
    st.markdown(f"預測比分: {home_goal}-{away_goal}  {ou}  {trend}")
    st.markdown(f"賠率: {match['odds']}")
    st.markdown("---")
