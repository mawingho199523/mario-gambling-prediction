# Mario Gambling Prediction v5.0
import streamlit as st
import requests
import numpy as np
import random
from datetime import datetime

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_URL = "https://v3.football.api-sports.io/"

headers = {
    "x-apisports-key": API_KEY
}

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")
st.title("⚽ Mario Gambling Prediction")

# -----------------------------
# 抓取可用聯賽
# -----------------------------
@st.cache_data
def get_leagues():
    url = f"{API_URL}leagues?season=2025"
    res = requests.get(url, headers=headers)
    data = res.json()["response"]
    leagues = []
    for item in data:
        league = item["league"]
        country = league["country"]
        leagues.append({"id": league["id"], "name": league["name"], "country": country})
    return leagues

# -----------------------------
# 抓取比賽
# -----------------------------
@st.cache_data
def get_fixtures(league_id):
    url = f"{API_URL}fixtures?league={league_id}&season=2025&next=10"
    res = requests.get(url, headers=headers)
    return res.json()["response"]

# -----------------------------
# 球隊最近 5 場比賽數據
# -----------------------------
def get_team_recent_stats(team_id):
    url = f"{API_URL}fixtures?team={team_id}&last=5"
    res = requests.get(url, headers=headers)
    data = res.json()["response"]
    goals, corners = [], []
    for f in data:
        home = f["teams"]["home"]["id"]
        away = f["teams"]["away"]["id"]
        if home == team_id:
            goals.append(f["goals"]["home"])
            corners.append(f["score"]["fulltime"].get("home_corners", 5))
        else:
            goals.append(f["goals"]["away"])
            corners.append(f["score"]["fulltime"].get("away_corners", 5))
    avg_goal = np.mean(goals) if goals else 1.5
    avg_corner = np.mean(corners) if corners else 5
    return avg_goal, avg_corner

# -----------------------------
# H2H 對賽數據
# -----------------------------
def get_h2h_stats(home_id, away_id):
    url = f"{API_URL}fixtures?h2h={home_id}-{away_id}&last=5"
    res = requests.get(url, headers=headers)
    data = res.json()["response"]
    h2h_home, h2h_away, h2h_corner_home, h2h_corner_away = [], [], [], []
    for f in data:
        h2h_home.append(f["goals"]["home"])
        h2h_away.append(f["goals"]["away"])
        h2h_corner_home.append(f["score"]["fulltime"].get("home_corners",5))
        h2h_corner_away.append(f["score"]["fulltime"].get("away_corners",5))
    return (np.mean(h2h_home) if h2h_home else 0,
            np.mean(h2h_away) if h2h_away else 0,
            np.mean(h2h_corner_home) if h2h_corner_home else 0,
            np.mean(h2h_corner_away) if h2h_corner_away else 0)

# -----------------------------
# Poisson 改良比分預測
# -----------------------------
def poisson_predict(home_avg, away_avg, h2h_home=0, h2h_away=0):
    home_lambda = max(0.5, 0.6*home_avg + 0.4*h2h_home + random.uniform(-0.5,0.5))
    away_lambda = max(0.5, 0.6*away_avg + 0.4*h2h_away + random.uniform(-0.5,0.5))
    home_goals = min(6, np.random.poisson(home_lambda))
    away_goals = min(6, np.random.poisson(away_lambda))
    total_goals = home_goals + away_goals
    over_under_emoji = "🔴 Over 2.5" if total_goals > 2.5 else "🟢 Under 2.5"
    return home_goals, away_goals, over_under_emoji

# -----------------------------
# 改良角球預測
# -----------------------------
def corner_predict(home_corner, away_corner, h2h_home=0, h2h_away=0):
    home_corners = max(0, int(random.gauss(0.6*home_corner + 0.4*h2h_home, 1.5)))
    away_corners = max(0, int(random.gauss(0.6*away_corner + 0.4*h2h_away, 1.5)))
    return home_corners, away_corners

# -----------------------------
# UI
# -----------------------------
leagues = get_leagues()
leagues_sorted = sorted(leagues, key=lambda x: x["id"])  # 可改為熱門程度
league_list = [f"{l['name']} ({l['country']})" for l in leagues_sorted]
selected_league = st.sidebar.selectbox("Select League", league_list)
league_id = leagues_sorted[league_list.index(selected_league)]["id"]

fixtures = get_fixtures(league_id)
fixtures_sorted = sorted(fixtures, key=lambda x: x["fixture"]["date"])

for f in fixtures_sorted:
    home = f["teams"]["home"]
    away = f["teams"]["away"]
    home_avg, home_corner = get_team_recent_stats(home["id"])
    away_avg, away_corner = get_team_recent_stats(away["id"])
    h2h_home, h2h_away, h2h_corner_home, h2h_corner_away = get_h2h_stats(home["id"], away["id"])
    
    home_goals, away_goals, ou_emoji = poisson_predict(home_avg, away_avg, h2h_home, h2h_away)
    home_corners, away_corners = corner_predict(home_corner, away_corner, h2h_corner_home, h2h_corner_away)
    
    st.markdown(f"### {home['name']} vs {away['name']}  🗓 {f['fixture']['date'][:10]}")
    st.markdown(f"⚽ **Score Prediction:** {home_goals}-{away_goals} {ou_emoji}")
    st.markdown(f"🥅 **Corner Prediction:** {home_corners}-{away_corners}")
    st.markdown("---")
