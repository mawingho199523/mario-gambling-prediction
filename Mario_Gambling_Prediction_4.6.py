import streamlit as st
import requests
import math
from datetime import datetime

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# -------------------- Helper Functions --------------------

def get_leagues():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    leagues = []
    for item in data["response"]:
        league = item["league"]
        country = league.get("country", "")
        leagues.append({
            "id": league["id"],
            "name": league["name"],
            "country": country
        })
    return leagues

def get_fixtures(league_id):
    today = datetime.today().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?league={league_id}&season=2025&from={today}&to={today}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    fixtures = []
    for f in data["response"]:
        fixtures.append({
            "fixture_id": f["fixture"]["id"],
            "date": f["fixture"]["date"],
            "home": f["teams"]["home"]["name"],
            "away": f["teams"]["away"]["name"]
        })
    return fixtures

def get_team_stats(team_name):
    # 取最近5場主客場比賽
    url = f"{BASE_URL}/teams/statistics?season=2025&team={team_name}&league=0"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    goals = []
    corners = []
    try:
        fixtures = data["response"]["fixtures"]["last"]
        for f in fixtures[-5:]:
            goals.append(f["goals"]["for"]["total"] or 0)
            corners.append(f.get("corners", {}).get("for", 0))
    except:
        goals = [1.5]*5
        corners = [5]*5
    avg_goal = sum(goals)/len(goals) if goals else 1.5
    avg_corner = sum(corners)/len(corners) if corners else 5
    return avg_goal, avg_corner

def poisson_probability(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def predict_score(home_avg, away_avg):
    max_goals = 5
    probabilities = {}
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            prob = poisson_probability(home_avg, h) * poisson_probability(away_avg, a)
            probabilities[(h,a)] = prob
    score = max(probabilities, key=probabilities.get)
    return score

def calc_over_under(home_avg, away_avg, line=2.5):
    max_goals = 5
    over_prob = 0
    under_prob = 0
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            total = h+a
            prob = poisson_probability(home_avg, h) * poisson_probability(away_avg, a)
            if total > line:
                over_prob += prob
            else:
                under_prob += prob
    return over_prob, under_prob

# -------------------- Streamlit Layout --------------------

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")
st.title("⚽ Mario Gambling Prediction")

# 左側聯賽選擇
leagues = get_leagues()
league_options = {f"{l['name']} ({l['country']})": l['id'] for l in leagues}
selected_league_name = st.sidebar.selectbox("Select League", list(league_options.keys()))
selected_league_id = league_options[selected_league_name]

# 中間比賽列表
fixtures = get_fixtures(selected_league_id)
fixtures = sorted(fixtures, key=lambda x: x["date"])

for f in fixtures:
    home_avg_goal, home_avg_corner = get_team_stats(f["home"])
    away_avg_goal, away_avg_corner = get_team_stats(f["away"])
    predicted_score = predict_score(home_avg_goal, away_avg_goal)
    over_prob, under_prob = calc_over_under(home_avg_goal, away_avg_goal)
    
    # 顯示結果
    st.markdown(f"### {f['home']} vs {f['away']} - {f['date'][:10]}")
    st.markdown(f"**Predicted Score:** {predicted_score[0]} - {predicted_score[1]}")
    st.markdown(f"**Corners Prediction:** {int(home_avg_corner)} - {int(away_avg_corner)}")
    st.markdown(f"**Over/Under 2.5:** Over: {over_prob*100:.1f}% ⚡ Under: {under_prob*100:.1f}%")
    
    # 勝負趨勢 emoji
    if predicted_score[0] > predicted_score[1]:
        trend = f"🏆 {f['home']} likely win"
    elif predicted_score[0] < predicted_score[1]:
        trend = f"🏆 {f['away']} likely win"
    else:
        trend = "🤝 Draw"
    st.markdown(f"**Trend:** {trend}")
    st.markdown("---")
