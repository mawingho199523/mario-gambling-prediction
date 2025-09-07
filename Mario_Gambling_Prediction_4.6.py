import streamlit as st
import requests
import random
import math

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
BASE_URL = "https://v3.football.api-sports.io"

headers = {"x-apisports-key": API_KEY}

# ---------------- Helper Functions ---------------- #
def poisson(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def weighted_avg(data, weights=None):
    if not data:
        return 0
    if not weights or len(weights) != len(data):
        weights = [1]*len(data)
    return sum(d*w for d,w in zip(data, weights))/sum(weights)

def get_leagues():
    res = requests.get(f"{BASE_URL}/leagues", headers=headers)
    leagues = []
    if res.status_code == 200:
        data = res.json()["response"]
        for item in data:
            leagues.append({
                "id": item["league"]["id"],
                "name": item["league"]["name"],
                "country": item["country"]["name"],
                "season": item["seasons"][-1]["year"] if item["seasons"] else 2025
            })
    return leagues

def get_fixtures(league_id, season):
    res = requests.get(f"{BASE_URL}/fixtures?league={league_id}&season={season}&status=NS", headers=headers)
    fixtures = []
    if res.status_code == 200:
        data = res.json()["response"]
        for f in data:
            fixtures.append({
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "date": f["fixture"]["date"][:10]
            })
    return fixtures

def get_team_recent_fixtures(team_name, last_n=5):
    res = requests.get(f"{BASE_URL}/fixtures?team={team_name}&last={last_n}", headers=headers)
    goals = []
    corners = []
    if res.status_code == 200:
        data = res.json()["response"]
        for f in data:
            goals.append(f["goals"]["home"] if f["teams"]["home"]["name"]==team_name else f["goals"]["away"])
            # 假設角球數據可從 statistics 拿
            corners_list = f.get("statistics", [])
            team_corner = 5
            for stat in corners_list:
                if stat["type"]=="Corner" and stat["team"]["name"]==team_name:
                    team_corner = stat["value"]
            corners.append(team_corner)
    return goals, corners

def predict_match(home, away):
    home_goals_list, home_corners_list = get_team_recent_fixtures(home)
    away_goals_list, away_corners_list = get_team_recent_fixtures(away)

    n = len(home_goals_list)
    weights = list(range(1, n+1))
    home_avg = weighted_avg(home_goals_list, weights) if home_goals_list else 1.5
    away_avg = weighted_avg(away_goals_list, weights) if away_goals_list else 1.0
    home_corners_avg = weighted_avg(home_corners_list, weights) if home_corners_list else 5
    away_corners_avg = weighted_avg(away_corners_list, weights) if away_corners_list else 4

    home_avg += random.uniform(-0.3,0.3)
    away_avg += random.uniform(-0.3,0.3)
    home_corners_avg += random.randint(-1,1)
    away_corners_avg += random.randint(-1,1)

    pred_home = max(round(home_avg),0)
    pred_away = max(round(away_avg),0)
    pred_home_corners = max(round(home_corners_avg),0)
    pred_away_corners = max(round(away_corners_avg),0)

    total_goals = home_avg + away_avg
    over_prob = sum([poisson(k, total_goals) for k in range(3,10)])

    return {
        "home_goals": pred_home,
        "away_goals": pred_away,
        "home_corners": pred_home_corners,
        "away_corners": pred_away_corners,
        "over_prob": over_prob
    }

# ---------------- Streamlit UI ---------------- #
st.title("⚽ Mario Gambling Prediction")

leagues = get_leagues()
league_options = [f"{l['name']} ({l['country']})" for l in leagues]
league_choice = st.sidebar.selectbox("Select League", league_options)

selected_league = leagues[league_options.index(league_choice)]
fixtures = get_fixtures(selected_league["id"], selected_league["season"])

for f in sorted(fixtures, key=lambda x: x["date"]):
    pred = predict_match(f["home"], f["away"])
    st.markdown(f"### {f['home']} 🆚 {f['away']} ({f['date']})")
    st.markdown(
        f"比分預測: {pred['home_goals']} - {pred['away_goals']} | "
        f"角球: {pred['home_corners']} - {pred['away_corners']} | "
        f"Over 2.5: {round(pred['over_prob']*100)}% "
        f"{'🟢' if pred['over_prob']>0.5 else '🔴'}"
    )
    st.markdown("---")
