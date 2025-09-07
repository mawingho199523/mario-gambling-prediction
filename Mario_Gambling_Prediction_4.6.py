import streamlit as st
import requests
import math

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ===== Helper functions =====
def get_leagues():
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = "https://v3.football.api-sports.io/leagues?season=2025"
    r = requests.get(url, headers=headers)
    leagues = {}
    if r.status_code == 200:
        for item in r.json().get("response", []):
            league_info = item.get("league", {})
            league_name = league_info.get("name", "Unknown League")
            league_country = league_info.get("country", "Unknown Country")
            league_id = league_info.get("id", 0)
            leagues[f"{league_name} ({league_country})"] = league_id
    return leagues

def sort_leagues_by_popularity(leagues_dict):
    HOT_KEYWORDS = ["Premier", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
    sorted_leagues = sorted(
        leagues_dict.items(),
        key=lambda x: (0 if any(k in x[0] for k in HOT_KEYWORDS) else 1, x[0])
    )
    return dict(sorted_leagues)

def get_fixtures(league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
    r = requests.get(url, headers=headers)
    fixtures = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            fixture_info = item.get("fixture", {})
            teams = item.get("teams", {})
            fixtures.append({
                "id": fixture_info.get("id", 0),
                "home": teams.get("home", {}).get("name", "Unknown Home"),
                "away": teams.get("away", {}).get("name", "Unknown Away"),
                "home_id": teams.get("home", {}).get("id", 0),
                "away_id": teams.get("away", {}).get("id", 0),
                "date": fixture_info.get("date", "Unknown Date")
            })
    return fixtures

def get_team_stats(team_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&season=2025&last=5"
    r = requests.get(url, headers=headers)
    goals = []
    corners = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            teams = item.get("teams", {})
            home_id = teams.get("home", {}).get("id", 0)
            away_id = teams.get("away", {}).get("id", 0)
            goals_home = item.get("goals", {}).get("home")
            goals_away = item.get("goals", {}).get("away")
            stats = item.get("statistics", [])

            # Goals
            if goals_home is not None and home_id == team_id:
                goals.append(goals_home)
            elif goals_away is not None and away_id == team_id:
                goals.append(goals_away)

            # Corners
            corner_home = next((s.get("value") for s in stats if s.get("type")=="Corner" and s.get("team", {}).get("id")==home_id), None)
            corner_away = next((s.get("value") for s in stats if s.get("type")=="Corner" and s.get("team", {}).get("id")==away_id), None)
            if home_id == team_id and corner_home is not None:
                corners.append(corner_home)
            elif away_id == team_id and corner_away is not None:
                corners.append(corner_away)

    avg_goal = sum(goals)/len(goals) if goals else 1.5
    avg_corner = sum(corners)/len(corners) if corners else 4.5
    return {"avg_goal": avg_goal, "avg_corner": avg_corner}

def poisson_prob(lam, k):
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def predict_score(home_avg_goal, away_avg_goal, max_goals=5):
    table = []
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            prob = poisson_prob(home_avg_goal, h) * poisson_prob(away_avg_goal, a)
            table.append(((h,a), prob))
    table.sort(key=lambda x: x[1], reverse=True)
    return table[:3]

# ===== Streamlit UI =====
st.set_page_config(layout="wide")
st.title("⚽ Mario Gambling Prediction (Vertical Fast View)")

# ===== 左側聯賽選擇 =====
leagues = get_leagues()
if not leagues:
    st.error("⚠️ Unable to fetch leagues from API-Football.")
    st.stop()

leagues_sorted = sort_leagues_by_popularity(leagues)
with st.sidebar:
    league_name = st.selectbox("Select League", list(leagues_sorted.keys()))

league_id = leagues_sorted[league_name]

# ===== 中央比賽快覽表 =====
fixtures = get_fixtures(league_id)
fixtures_sorted = sorted(fixtures, key=lambda x: x["date"])

for f in fixtures_sorted:
    st.markdown(f"### 🏟️ {f['home']} vs {f['away']} ({f['date'][:10]})")
    
    home_stats = get_team_stats(f["home_id"])
    away_stats = get_team_stats(f["away_id"])
    
    # 比分預測
    top_scores = predict_score(home_stats["avg_goal"], away_stats["avg_goal"])
    for (h, a), _ in top_scores:
        st.markdown(f"⚽ Predicted Score: {h}-{a} 🔥")
    
    # 角球預測
    total_corners = home_stats["avg_corner"] + away_stats["avg_corner"]
    st.markdown(f"🥅 Predicted Corners: Home {home_stats['avg_corner']:.1f} + Away {away_stats['avg_corner']:.1f} = {total_corners:.1f} 🔥")
    
    # 總進球 Over/Under
    total_goals = home_stats["avg_goal"] + away_stats["avg_goal"]
    goals_emoji = "🔥 Over 2.5" if total_goals > 2.5 else "❌ Under 2.5"
    st.markdown(f"🔢 Total Goals Prediction: {total_goals:.1f} {goals_emoji}")
    
    st.markdown("---")
