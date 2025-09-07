import streamlit as st
import requests
import math

# ===== API Key =====
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ===== Helper functions =====
def get_leagues():
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = "https://v3.football.api-sports.io/leagues?season=2025"
    r = requests.get(url, headers=headers)
    leagues = {}
    if r.status_code == 200:
        for item in r.json().get("response", []):
            leagues[item["league"]["name"]] = item["league"]["id"]
    return leagues

def get_fixtures(league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
    r = requests.get(url, headers=headers)
    fixtures = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            fixtures.append({
                "id": item["fixture"]["id"],
                "home": item["teams"]["home"]["name"],
                "away": item["teams"]["away"]["name"],
                "date": item["fixture"]["date"]
            })
    return fixtures

def get_team_id(name, league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/teams?league={league_id}&season=2025"
    r = requests.get(url, headers=headers)
    if r.status_code==200:
        for item in r.json().get("response", []):
            if item["team"]["name"]==name:
                return item["team"]["id"]
    return None

def get_last_matches(team_id, last=5):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last={last}"
    r = requests.get(url, headers=headers)
    return r.json().get("response", []) if r.status_code==200 else []

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

def get_average_corners(team_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=5"
    r = requests.get(url, headers=headers)
    total_corners = 0
    count = 0
    if r.status_code==200:
        for match in r.json().get("response", []):
            stats = match.get("statistics", [])
            for s in stats:
                if s.get("type")=="Corners" and isinstance(s.get("value",0),(int,float)):
                    total_corners += s.get("value",0)
                    count +=1
    avg_corners = total_corners/count if count>0 else 4
    return avg_corners

def predict_corners(home_id, away_id):
    home_avg = get_average_corners(home_id)
    away_avg = get_average_corners(away_id)
    total_avg = home_avg + away_avg
    over_indicator = "🔥" if total_avg > 9.5 else "❌"
    return home_avg, away_avg, total_avg, over_indicator

# ===== Streamlit UI =====
st.set_page_config(layout="wide")
st.title("⚽ Mario Gambling Prediction (API-Football only)")

# ===== 左側聯賽選擇 =====
leagues = get_leagues()
with st.sidebar:
    league_name = st.selectbox("Select League", list(leagues.keys()))
league_id = leagues[league_name]

# ===== 右側比賽卡片 =====
fixtures = get_fixtures(league_id)
fixtures_sorted = sorted(fixtures, key=lambda x: x["date"])

for f in fixtures_sorted:
    home_id = get_team_id(f["home"], league_id)
    away_id = get_team_id(f["away"], league_id)
    
    # 主客隊平均進球
    home_matches = get_last_matches(home_id) if home_id else []
    away_matches = get_last_matches(away_id) if away_id else []
    
    home_goals = [m["goals"]["home"] for m in home_matches if "goals" in m and isinstance(m["goals"]["home"], (int,float))]
    away_goals = [m["goals"]["away"] for m in away_matches if "goals" in m and isinstance(m["goals"]["away"], (int,float))]
    
    home_avg_goal = sum(home_goals)/len(home_goals) if home_goals else 1.5
    away_avg_goal = sum(away_goals)/len(away_goals) if away_goals else 1.2
    
    # 預測比分
    top_scores = predict_score(home_avg_goal, away_avg_goal)
    score_text = " ".join([f"{'🔥' if s[1]>0.15 else '❌'}{s[0][0]}-{s[0][1]}" for s in top_scores])
    
    # 角球預測
    home_avg_c, away_avg_c, total_c, over_ind = predict_corners(home_id, away_id)
    
    # 大小球預測
    total_goals_avg = home_avg_goal + away_avg_goal
    over_under_indicator = "🔥" if total_goals_avg > 2.5 else "❌"
    
    # ===== 卡片顯示 =====
    st.markdown(f"### {f['home']} vs {f['away']} ({f['date'][:10]})")
    st.markdown(f"⚽ Predicted Score: {score_text}")
    st.markdown(f"🥅 Corners: {home_avg_c:.1f}+{away_avg_c:.1f}={total_c:.1f} ({over_ind} Over)")
    st.markdown(f"🔢 Total Goals: {total_goals_avg:.2f} ({over_under_indicator} Over 2.5)")
    st.markdown("---")
