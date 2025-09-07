# Mario Gambling Prediction Version 6.1
import streamlit as st
import requests
import math
import numpy as np

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

st.title("⚽ Mario Gambling Prediction v6.1")

# -------------------------
# Helper Functions
# -------------------------

@st.cache_data
def get_leagues():
    url = f"{BASE_URL}/leagues"
    res = requests.get(url, headers=HEADERS)
    data = res.json()
    leagues = []
    for item in data.get('response', []):
        league = item.get('league')
        if league:
            leagues.append({
                "id": league["id"],
                "name": league["name"],
                "country": league.get("country", "")
            })
    return leagues

@st.cache_data
def get_fixtures(league_id):
    url = f"{BASE_URL}/fixtures?league={league_id}&season=2025&next=10"
    res = requests.get(url, headers=HEADERS)
    data = res.json()
    fixtures = []
    for f in data.get('response', []):
        fixture = f.get('fixture')
        teams = f.get('teams')
        if fixture and teams:
            fixtures.append({
                "date": fixture.get("date"),
                "home": teams["home"]["name"],
                "home_id": teams["home"]["id"],
                "away": teams["away"]["name"],
                "away_id": teams["away"]["id"]
            })
    fixtures.sort(key=lambda x: x["date"])
    return fixtures

@st.cache_data
def get_team_stats(team_id):
    # 取得近期比賽數據
    url = f"{BASE_URL}/teams/statistics?season=2025&team={team_id}"
    res = requests.get(url, headers=HEADERS)
    stats = res.json().get('response', {})
    
    # 平均進球數
    goals = [m['goals']['for']['total'] for m in stats.get('fixtures', {}).get('played', {}).get('home', [])] if stats.get('fixtures', {}).get('played', {}).get('home') else [1.5]
    avg_goal = sum(goals)/len(goals) if goals else 1.5
    
    # 平均角球數
    corners = [m['corners']['for']['total'] for m in stats.get('fixtures', {}).get('played', {}).get('home', [])] if stats.get('fixtures', {}).get('played', {}).get('home') else [5]
    avg_corner = sum(corners)/len(corners) if corners else 5
    
    return avg_goal, avg_corner

def poisson_score(home_avg, away_avg):
    max_goals = 5
    prob_matrix = np.zeros((max_goals+1, max_goals+1))
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            prob_matrix[i,j] = (math.exp(-home_avg)*home_avg**i/math.factorial(i)) * \
                               (math.exp(-away_avg)*away_avg**j/math.factorial(j))
    i,j = np.unravel_index(prob_matrix.argmax(), prob_matrix.shape)
    return f"{i}-{j}"

def predict_corners(home_avg_corner, away_avg_corner):
    home_corner = np.random.poisson(home_avg_corner)
    away_corner = np.random.poisson(away_avg_corner)
    return f"{home_corner}-{away_corner}"

# -------------------------
# Streamlit Interface
# -------------------------
leagues = get_leagues()
league_names = [l['name'] for l in leagues]

selected_league_name = st.sidebar.selectbox("Select League", league_names)
selected_league = next((l for l in leagues if l['name'] == selected_league_name), None)

if selected_league:
    fixtures = get_fixtures(selected_league['id'])
    
    for f in fixtures:
        st.markdown(f"### 🗓️ {f['date'][:10]}: {f['home']} vs {f['away']}")
        
        home_avg_goal, home_avg_corner = get_team_stats(f['home_id'])
        away_avg_goal, away_avg_corner = get_team_stats(f['away_id'])
        
        # 可加入 H2H 加權
        home_goal = 0.6*home_avg_goal + 0.1
        away_goal = 0.6*away_avg_goal + 0.1
        home_corner = 0.6*home_avg_corner + 1
        away_corner = 0.6*away_avg_corner + 1
        
        score_pred = poisson_score(home_goal, away_goal)
        corner_pred = predict_corners(home_corner, away_corner)
        
        # 顯示 Emoji 趨勢
        emoji_score = "🏆" if int(score_pred.split('-')[0]) > int(score_pred.split('-')[1]) else ("🤝" if score_pred.split('-')[0]==score_pred.split('-')[1] else "💔")
        
        st.markdown(f"⚽ Predicted Score: {score_pred} {emoji_score}")
        st.markdown(f"🥅 Predicted Corners: {corner_pred}")
