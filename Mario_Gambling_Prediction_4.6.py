# Mario Gambling Prediction Version 6.6 Improved
# 功能: 使用 API-Football 資料生成比分預測、大小球、讓球盤建議，避免單一比分

import streamlit as st
import requests
import random

# ---------------------------
# 配置 API
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

# ---------------------------
# 幫助函數: 抓取聯賽
@st.cache_data
def get_leagues():
    url = f"{API_FOOTBALL_URL}/leagues"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()
    leagues = []
    for item in data.get("response", []):
        league_info = item.get("league", {})
        country_info = league_info.get("country", "Unknown")
        leagues.append({
            "id": league_info.get("id"),
            "name": league_info.get("name"),
            "country": country_info,
            "season": item.get("seasons", [{}])[0].get("year")
        })
    return leagues

# ---------------------------
# 抓取即將比賽
@st.cache_data
def get_fixtures(league_id):
    url = f"{API_FOOTBALL_URL}/fixtures?league={league_id}&season=2025&next=10"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()
    fixtures = []
    for f in data.get("response", []):
        fixture = f.get("fixture", {})
        teams = f.get("teams", {})
        home_team = teams.get("home", {}).get("name")
        away_team = teams.get("away", {}).get("name")
        fixtures.append({
            "home": home_team,
            "away": away_team,
            "date": fixture.get("date")
        })
    return fixtures

# ---------------------------
# 隨機化比分函數
def predict_score(avg_home, avg_away):
    # 基於平均進球 + 隨機微調
    home_goals = max(0, int(random.gauss(avg_home, 1)))
    away_goals = max(0, int(random.gauss(avg_away, 1)))
    return home_goals, away_goals

# ---------------------------
# 大小球建議
def over_under_prediction(home, away, line=2.5):
    total = home + away
    return "Over" if total > line else "Under"

# ---------------------------
# 讓球盤建議
def handicap_suggestion(home, away):
    diff = home - away
    if diff > 1:
        return "-1"
    elif diff < -1:
        return "+1"
    elif diff > 0:
        return "-0.5"
    elif diff < 0:
        return "+0.5"
    else:
        return "0"

# ---------------------------
# Streamlit UI
st.title("Mario Gambling Prediction Version 6.6 Improved")

leagues = get_leagues()
league_names = [f"{l['name']} ({l['country']})" for l in leagues]
selected_league_idx = st.sidebar.selectbox("Select League", range(len(league_names)), format_func=lambda x: league_names[x])
selected_league = leagues[selected_league_idx]

fixtures = get_fixtures(selected_league["id"])

st.header(f"{selected_league['name']} - Upcoming Fixtures")

for f in fixtures:
    # 模擬平均進球數，暫時使用隨機值
    avg_home_goal = random.uniform(0.8, 2.0)
    avg_away_goal = random.uniform(0.5, 1.8)
    
    home_goals, away_goals = predict_score(avg_home_goal, avg_away_goal)
    ou = over_under_prediction(home_goals, away_goals, line=2.5)
    handicap = handicap_suggestion(home_goals, away_goals)
    
    st.markdown(f"### {f['home']} vs {f['away']} - {f['date'][:10]}")
    st.markdown(f"**Predicted Score:** {home_goals} - {away_goals}")
    st.markdown(f"**Over/Under 2.5:** {ou} ⚽")
    st.markdown(f"**Handicap Suggestion:** {handicap} 🎯")
    st.markdown("---")
