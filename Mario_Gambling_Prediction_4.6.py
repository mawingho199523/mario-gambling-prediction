import streamlit as st
import requests
import math

# ===========================
# 配置
# ===========================
API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_BASE = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_KEY}

# ===========================
# 取得聯賽列表
# ===========================
@st.cache_data
def get_leagues():
    url = f"{API_BASE}/leagues"
    response = requests.get(url, headers=headers)
    data = response.json().get("response", [])
    leagues = []
    for item in data:
        league = item.get("league", {})
        country = league.get("country", "")
        leagues.append({
            "id": league.get("id"),
            "name": league.get("name"),
            "country": country
        })
    return leagues

# ===========================
# 取得球隊統計
# ===========================
@st.cache_data
def get_team_stats(team_id):
    url = f"{API_BASE}/teams/statistics?season=2025&team={team_id}"
    response = requests.get(url, headers=headers)
    data = response.json()
    stats = data.get('response', {})

    # 防呆處理
    fixtures_stats = stats.get('fixtures', {})
    played_stats = fixtures_stats.get('played', {}) if fixtures_stats else {}
    home_goals = played_stats.get('home', 1.5)
    away_goals = played_stats.get('away', 1.0)

    corners_stats = stats.get('corners', {})
    avg_corners = corners_stats.get('average', {}) if corners_stats else {}
    home_corners = avg_corners.get('home', 4)
    away_corners = avg_corners.get('away', 3)

    return home_goals, home_corners

# ===========================
# Poisson 比分預測
# ===========================
def poisson_goals(home_avg, away_avg):
    max_goals = 5
    result = {}
    for home_score in range(0, max_goals+1):
        for away_score in range(0, max_goals+1):
            prob = (math.exp(-home_avg) * (home_avg ** home_score) / math.factorial(home_score)) * \
                   (math.exp(-away_avg) * (away_avg ** away_score) / math.factorial(away_score))
            result[(home_score, away_score)] = prob
    sorted_result = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return sorted_result[:3]  # 預測前三高概率比分

# ===========================
# 取得比賽
# ===========================
@st.cache_data
def get_fixtures(league_id):
    url = f"{API_BASE}/fixtures?league={league_id}&season=2025&next=10"
    response = requests.get(url, headers=headers)
    data = response.json().get("response", [])
    fixtures = []
    for f in data:
        fixture = f.get('fixture', {})
        teams = f.get('teams', {})
        home_team = teams.get('home', {}).get('name', "")
        away_team = teams.get('away', {}).get('name', "")
        home_id = teams.get('home', {}).get('id', 0)
        away_id = teams.get('away', {}).get('id', 0)
        date = fixture.get('date', "")
        fixtures.append({
            "home": home_team,
            "away": away_team,
            "home_id": home_id,
            "away_id": away_id,
            "date": date
        })
    fixtures.sort(key=lambda x: x['date'])
    return fixtures

# ===========================
# Streamlit 介面
# ===========================
st.title("Mario Gambling Prediction v6.0")

# 聯賽選擇
leagues = get_leagues()
league_options = {f"{l['country']} - {l['name']}": l['id'] for l in leagues}
selected_league_name = st.sidebar.selectbox("Select League", list(league_options.keys()))
selected_league_id = league_options[selected_league_name]

# 顯示比賽
fixtures = get_fixtures(selected_league_id)
for f in fixtures:
    st.subheader(f"{f['home']} 🆚 {f['away']} ({f['date'][:10]})")

    # 球隊歷史統計
    home_avg_goal, home_avg_corner = get_team_stats(f['home_id'])
    away_avg_goal, away_avg_corner = get_team_stats(f['away_id'])

    # 比分預測
    top_scores = poisson_goals(home_avg_goal, away_avg_goal)
    score_predictions = " | ".join([f"{h}-{a}" for (h,a),p in top_scores])
    st.markdown(f"⚽ **Score Prediction:** {score_predictions}")

    # 角球預測
    st.markdown(f"🟠 **Corner Prediction:** Home ~{home_avg_corner}, Away ~{away_avg_corner}")

    # 簡單讓球/獨贏趨勢 emoji
    if home_avg_goal > away_avg_goal:
        trend = "🏆 Home Favored"
    elif home_avg_goal < away_avg_goal:
        trend = "🏆 Away Favored"
    else:
        trend = "🤝 Draw Favored"
    st.markdown(f"📊 **Trend:** {trend}")

st.markdown("---")
st.markdown("Version 6.0 - 完整防呆版")
