# Mario Gambling Prediction Version 6.6.1 中文 + Emoji + 動態盤口
import streamlit as st
import requests
import random

# ---------------------------
# 配置 API
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

# ---------------------------
# 抓取聯賽
@st.cache_data
def get_leagues():
    url = f"{API_FOOTBALL_URL}/leagues"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()
    leagues = []
    for item in data.get("response", []):
        league_info = item.get("league", {})
        leagues.append({
            "id": league_info.get("id"),
            "name": league_info.get("name"),
            "country": league_info.get("country", "未知")
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
        fixtures.append({
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
            "date": fixture.get("date")
        })
    return fixtures

# ---------------------------
# 模擬比分
def predict_score(avg_home, avg_away):
    home_goals = max(0, int(random.gauss(avg_home, 1)))
    away_goals = max(0, int(random.gauss(avg_away, 1)))
    return home_goals, away_goals

# ---------------------------
# 動態大小球盤口
def over_under_prediction(home, away):
    total = home + away
    # 隨機盤口 2.5 ~ 4.0
    line = random.choice([2.5, 3, 3.5, 4])
    if total > line:
        return f"大球 ⚽⚽ (盤口 {line})"
    elif total < line:
        return f"小球 ⚽ (盤口 {line})"
    else:
        return f"平局球 ⚽🤝 (盤口 {line})"

# ---------------------------
# 動態讓球盤口
def handicap_suggestion(home, away):
    diff = home - away
    # 隨機讓球盤口
    line = random.choice([-1, -0.5, 0, 0.5, 1])
    if diff > line:
        return f"主勝 🏆 (讓球 {line})"
    elif diff < line:
        return f"客勝 🏆 (讓球 {line})"
    else:
        return f"平局 🤝 (讓球 {line})"

# ---------------------------
# Streamlit UI
st.title("Mario 賭波預測 Version 6.6.1 中文 + Emoji + 動態盤口")

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
    
    ou = over_under_prediction(home_goals, away_goals)
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
