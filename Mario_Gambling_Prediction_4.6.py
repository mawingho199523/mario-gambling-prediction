# Mario Gambling Prediction Version 6.0
import streamlit as st
import requests
import pandas as pd
import math

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_BASE = "https://v3.football.api-sports.io"

headers = {"x-apisports-key": API_KEY}

st.set_page_config(page_title="Mario Gambling Prediction v6.0", layout="wide")

# ---------- FUNCTIONS ----------

@st.cache_data
def get_leagues():
    url = f"{API_BASE}/leagues"
    response = requests.get(url, headers=headers)
    data = response.json()
    leagues = {}
    for item in data['response']:
        league_id = item['league']['id']
        league_name = item['league']['name']
        country = item['country']['name']
        leagues[league_id] = f"{league_name} ({country})"
    return leagues

@st.cache_data
def get_fixtures(league_id):
    url = f"{API_BASE}/fixtures?league={league_id}&season=2025&next=10"
    response = requests.get(url, headers=headers)
    data = response.json()
    fixtures = []
    for f in data['response']:
        fixture = f['fixture']
        teams = f['teams']
        fixtures.append({
            "date": fixture['date'],
            "home": teams['home']['name'],
            "home_id": teams['home']['id'],
            "away": teams['away']['name'],
            "away_id": teams['away']['id'],
            "fixture_id": fixture['id']
        })
    return fixtures

@st.cache_data
def get_team_stats(team_id):
    url = f"{API_BASE}/teams/statistics?season=2025&team={team_id}"
    response = requests.get(url, headers=headers)
    data = response.json()
    stats = data.get('response', {})
    goals = stats.get('fixtures', {}).get('played', {}).get('home', 1.5)
    corners = stats.get('corners', {}).get('average', {}).get('home', 4.5)
    return goals, corners

@st.cache_data
def get_h2h(home_id, away_id):
    url = f"{API_BASE}/fixtures/headtohead?h2h={home_id}-{away_id}"
    response = requests.get(url, headers=headers)
    data = response.json()
    home_goals = []
    away_goals = []
    home_corners = []
    away_corners = []
    for match in data.get('response', []):
        score = match['score']['fulltime']
        if score['home'] is not None and score['away'] is not None:
            home_goals.append(score['home'])
            away_goals.append(score['away'])
        corners = match.get('statistics', [])
        if corners:
            home_corners.append(corners[0]['value'])
            away_corners.append(corners[1]['value'])
    return home_goals, away_goals, home_corners, away_corners

def poisson_prob(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def predict_score(home_avg, away_avg):
    probs = {}
    for home_goals in range(5):
        for away_goals in range(5):
            prob = poisson_prob(home_avg, home_goals) * poisson_prob(away_avg, away_goals)
            probs[f"{home_goals}-{away_goals}"] = prob
    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    return sorted_probs[0][0]

def predict_over_under(home_avg, away_avg):
    total_avg = home_avg + away_avg
    over_prob = 1 - poisson_prob(total_avg, 0)  # simplification
    return over_prob

# ---------- STREAMLIT ----------

st.title("Mario Gambling Prediction v6.0 ⚽️📊")

# Sidebar league selection
leagues = get_leagues()
selected_league_id = st.sidebar.selectbox("Select League", options=list(leagues.keys()),
                                          format_func=lambda x: leagues[x])

# Fixtures
fixtures = get_fixtures(selected_league_id)
fixtures.sort(key=lambda x: x['date'])

for f in fixtures:
    st.markdown(f"### {f['home']} 🆚 {f['away']} ({f['date'][:10]})")
    # Get stats
    home_goals_recent, home_corners_recent = get_team_stats(f['home_id'])
    away_goals_recent, away_corners_recent = get_team_stats(f['away_id'])
    # Get H2H
    h2h_home_goals, h2h_away_goals, h2h_home_corners, h2h_away_corners = get_h2h(f['home_id'], f['away_id'])
    # Weighted average
    home_avg_goal = (0.7*home_goals_recent + 0.3* (sum(h2h_home_goals)/len(h2h_home_goals) if h2h_home_goals else 1.5))
    away_avg_goal = (0.7*away_goals_recent + 0.3* (sum(h2h_away_goals)/len(h2h_away_goals) if h2h_away_goals else 1.0))
    home_avg_corner = (0.7*home_corners_recent + 0.3* (sum(h2h_home_corners)/len(h2h_home_corners) if h2h_home_corners else 4))
    away_avg_corner = (0.7*away_corners_recent + 0.3* (sum(h2h_away_corners)/len(h2h_away_corners) if h2h_away_corners else 3))
    # Predict
    score_pred = predict_score(home_avg_goal, away_avg_goal)
    over_prob = predict_over_under(home_avg_goal, away_avg_goal)
    corner_total = home_avg_corner + away_avg_corner
    st.markdown(f"**Score Prediction:** {score_pred} 🏆")
    st.markdown(f"**Over/Under 2.5:** {'Over' if over_prob>0.5 else 'Under'} 📈")
    st.markdown(f"**Corners Prediction:** {int(home_avg_corner)}-{int(away_avg_corner)} ⚽️")
    st.markdown("---")
