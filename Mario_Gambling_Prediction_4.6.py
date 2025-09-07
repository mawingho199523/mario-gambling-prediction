import streamlit as st
import requests
import math

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_BASE = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_KEY}

# ====== 防呆函數 ======
@st.cache_data
def get_team_stats(team_id):
    url = f"{API_BASE}/teams/statistics?season=2025&team={team_id}"
    response = requests.get(url, headers=headers)
    data = response.json()

    stats = data.get('response')
    if not stats or not isinstance(stats, dict):
        return 1.5, 4  # 預設進球/角球

    fixtures_stats = stats.get('fixtures')
    if not fixtures_stats or not isinstance(fixtures_stats, dict):
        home_goals = 1.5
        away_goals = 1.0
    else:
        played_stats = fixtures_stats.get('played', {})
        home_goals = played_stats.get('home', 1.5)
        away_goals = played_stats.get('away', 1.0)

    corners_stats = stats.get('corners', {})
    avg_corners = corners_stats.get('average', {})
    home_corners = avg_corners.get('home', 4)
    away_corners = avg_corners.get('away', 3)

    return home_goals, home_corners

# ====== 獲取聯賽 ======
@st.cache_data
def get_leagues():
    url = f"{API_BASE}/leagues?season=2025"
    response = requests.get(url, headers=headers)
    data = response.json()
    leagues = data.get('response', [])
    result = []
    for item in leagues:
        league_info = item.get('league')
        if league_info:
            result.append({
                "id": league_info.get('id'),
                "name": league_info.get('name'),
                "country": league_info.get('country')
            })
    return result

# ====== 獲取比賽 ======
@st.cache_data
def get_fixtures(league_id):
    url = f"{API_BASE}/fixtures?season=2025&league={league_id}&next=10"
    response = requests.get(url, headers=headers)
    data = response.json()
    fixtures = data.get('response', [])
    matches = []
    for f in fixtures:
        fixture = f.get('fixture')
        teams = f.get('teams')
        if fixture and teams:
            matches.append({
                "date": fixture.get('date'),
                "home": teams.get('home', {}).get('name'),
                "home_id": teams.get('home', {}).get('id'),
                "away": teams.get('away', {}).get('name'),
                "away_id": teams.get('away', {}).get('id')
            })
    return matches

# ====== Poisson 預測 ======
def poisson_predict(home_avg, away_avg, max_goals=5):
    prob_matrix = []
    for i in range(max_goals+1):
        row = []
        for j in range(max_goals+1):
            p = (math.exp(-home_avg) * home_avg**i / math.factorial(i)) * \
                (math.exp(-away_avg) * away_avg**j / math.factorial(j))
            row.append(p)
        prob_matrix.append(row)
    return prob_matrix

# ====== Streamlit UI ======
st.title("Mario Gambling Prediction Version 6.0.1 ⚽️")

leagues = get_leagues()
league_names = [l['name'] for l in leagues]
selected_league = st.sidebar.selectbox("Select League", league_names)

# 找到選擇聯賽的 ID
league_id = next((l['id'] for l in leagues if l['name']==selected_league), None)

if league_id:
    matches = get_fixtures(league_id)
    for f in matches:
        home_avg_goal, home_avg_corner = get_team_stats(f['home_id'])
        away_avg_goal, away_avg_corner = get_team_stats(f['away_id'])
        prob_matrix = poisson_predict(home_avg_goal, away_avg_goal)

        # 簡化顯示：找最大機率比分
        max_prob = 0
        pred_score = "1-1"
        for i,row in enumerate(prob_matrix):
            for j,p in enumerate(row):
                if p>max_prob:
                    max_prob = p
                    pred_score = f"{i}-{j}"

        # 角球簡單預測
        avg_corners = (home_avg_corner + away_avg_corner)/2
        corner_pred = f"{round(avg_corners)} ⚽️"

        st.subheader(f"{f['home']} vs {f['away']} ({f['date'][:10]})")
        st.markdown(f"**Score Prediction:** {pred_score} | **Corners:** {corner_pred}")
        st.markdown("---")
else:
    st.warning("League ID not found.")
