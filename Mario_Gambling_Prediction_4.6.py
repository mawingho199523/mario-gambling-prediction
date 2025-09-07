import streamlit as st
import requests
import math

# ===== API Keys =====
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
THE_ODDS_KEY = "d00b3f188b2a475a2feaf90da0be67a5"

# ===== Helper functions =====

def get_team_avg_corners(team_id, league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&league={league_id}&season=2025&last=5"
    r = requests.get(url, headers=headers)
    avg_corners = []
    if r.status_code != 200:
        return 5  # fallback

    matches = r.json().get("response", [])
    for match in matches:
        fixture_id = match['fixture']['id']
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
        stats_r = requests.get(stats_url, headers=headers)
        if stats_r.status_code == 200:
            stats_data = stats_r.json().get("response", [])
            for s in stats_data:
                if s["team"]["id"] == team_id:
                    for stat in s["statistics"]:
                        if stat["type"] == "Corner Kicks":
                            avg_corners.append(stat["value"])
    return sum(avg_corners)/len(avg_corners) if avg_corners else 5

def get_corner_odds(home, away):
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={THE_ODDS_KEY}&regions=uk&markets=totals"
    r = requests.get(url)
    if r.status_code != 200:
        return 9.5  # fallback
    data = r.json()
    for match in data:
        if home in match.get("home_team","") and away in match.get("away_team",""):
            for bookmaker in match.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"]=="totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"]=="Over":
                                return float(outcome["point"])
    return 9.5

def poisson_prob(lam, k):
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def predict_score(home_avg_goal, away_avg_goal, max_goals=5):
    table = []
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            prob = poisson_prob(home_avg_goal, h) * poisson_prob(away_avg_goal, a)
            table.append(((h,a), prob))
    table.sort(key=lambda x: x[1], reverse=True)
    return table[:5]  # top 5 most probable scores

def predict_final_corners(home_id, away_id, league_id, home_name, away_name):
    home_avg = get_team_avg_corners(home_id, league_id)
    away_avg = get_team_avg_corners(away_id, league_id)
    total_avg = home_avg + away_avg

    # 莊家角球大小盤
    odds_total = get_corner_odds(home_name, away_name)

    over_indicator = "🔥" if total_avg > odds_total else "❌"
    return home_avg, away_avg, total_avg, odds_total, over_indicator

# ===== Streamlit UI =====

st.title("⚽ Mario Gambling Prediction")
st.markdown("### 比分 + 角球預測 (結合球隊歷史 + 莊家盤)")

# ===== Example selection =====
# 可以改成自動抓聯賽 + 球隊
leagues = {"Premier League":39, "La Liga":140, "Serie A":135}  
league_name = st.selectbox("選擇聯賽", list(leagues.keys()))
league_id = leagues[league_name]

# 假設球隊 ID 與名稱（可用 API-Football 抓取）
teams = {
    "Manchester City":33,
    "Manchester United":34,
    "Arsenal":42,
    "Liverpool":40
}
home_team_name = st.selectbox("主隊", list(teams.keys()))
away_team_name = st.selectbox("客隊", [t for t in teams.keys() if t != home_team_name])
home_id = teams[home_team_name]
away_id = teams[away_team_name]

st.markdown("### ⚽ 比分預測")
home_avg_goal, away_avg_goal = 1.5, 1.2  # 假設值，可抓歷史平均進球
top_scores = predict_score(home_avg_goal, away_avg_goal)

for score, prob in top_scores:
    st.write(f"{home_team_name} {score[0]} - {score[1]} {away_team_name} ({prob*100:.1f}%)")

st.markdown("### 🥅 角球預測")
home_c, away_c, total_c, odds_total, over_ind = predict_final_corners(
    home_id, away_id, league_id, home_team_name, away_team_name
)
st.write(f"主隊角球: {home_c:.1f} | 客隊角球: {away_c:.1f} | 總計: {total_c:.1f}")
st.write(f"莊家盤: {odds_total} | Over 9.5 角球: {over_ind}")
