# Mario Gambling Prediction Version 6.6 Improved (中文 + Emoji)
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
        country_info = league_info.get("country", "未知")
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
    home_goals = max(0, int(random.gauss(avg_home, 1)))
    away_goals = max(0, int(random.gauss(avg_away, 1)))
    return home_goals, away_goals

# ---------------------------
# 大小球建議
def over_under_prediction(home, away, line=2.5):
    total = home + away
    if total > line:
        return "大球 ⚽⚽"
    elif total < line:
        return "小球 ⚽"
    else:
        return "平局球 ⚽🤝"

# ---------------------------
# 讓球盤建議
def handicap_suggestion(home, away):
    diff = home - away
    if diff > 1:
        return "主勝 -1 🏆"
    elif diff < -1:
        return "客勝 +1 🏆"
    elif diff > 0:
        return "主勝 -0.5 ⚡"
    elif diff < 0:
        return "客勝 +0.5 ⚡"
    else:
        return "平局 0 🤝"

# ---------------------------
# Streamlit UI
st.title("Mario 賭波預測 Version 6.6 中文 + Emoji")

leagues = get_leagues()
league_names = [f"{l['name']} ({l['country']})" for l in leagues]
selected_league_idx = st.sidebar.selectbox("選擇聯賽", range(len(league_names)), format_func=lambda x: league_names[x])
selected_league = leagues[selected_league_idx]

fixtures = get_fixtures(selected_league["id"])

st.header(f"{selected_league['name']} - 即將比賽")

for f in fixtures:
    # 模擬平均進球數
    avg_home_goal = random.uniform(0.8, 2.0)
    avg_away_goal = random.uniform(0.5, 1.8)
    
    home_goals, away_goals = predict_score(avg_home_goal, avg_away_goal)
    ou = over_under_prediction(home_goals, away_goals, line=2.5)
    handicap = handicap_suggestion(home_goals, away_goals)

    # 勝平負 Emoji
    if home_goals > away_goals:
        result_emoji = "🏠 主勝"
    elif home_goals < away_goals:
        result_emoji = "🛫 客勝"
    else:
        result_emoji = "🤝 平局"

    st.markdown(f"### {f['home']} vs {f['away']} - {f['date'][:10]}")
    st.markdown(f"**預測比分:** {home_goals} - {away_goals} {result_emoji}")
    st.markdown(f"**大小球:** {ou}")
    st.markdown(f"**讓球盤建議:** {handicap}")
    st.markdown("---")
