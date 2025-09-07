import streamlit as st
import requests
import math

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ===== 熱門聯賽 =====
hot_leagues = ["English Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]

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

def sort_leagues_by_popularity(leagues_dict):
    sorted_leagues = sorted(leagues_dict.items(),
                            key=lambda x: (0 if x[0] in hot_leagues else 1, x[0]))
    return dict(sorted_leagues)

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

def get_team_stats(team_name):
    """使用 API-Football 獲取最近 5 場進球和角球平均數"""
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    # 查詢球隊 ID
    search_url = f"https://v3.football.api-sports.io/teams?search={team_name}"
    r = requests.get(search_url, headers=headers)
    team_id = None
    if r.status_code == 200 and r.json().get("response"):
        team_id = r.json()["response"][0]["team"]["id"]
    else:
        return {"avg_goal": 1.5, "avg_corner": 4.5}  # default
    
    # 獲取最近 5 場比賽
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&season=2025&last=5"
    r = requests.get(url, headers=headers)
    goals = []
    corners = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            if item["teams"]["home"]["id"] == team_id:
                goals.append(item["goals"]["home"])
                corners.append(item.get("statistics", [{}])[0].get("statistics", {}).get("corners", 4))
            else:
                goals.append(item["goals"]["away"])
                corners.append(item.get("statistics", [{}])[0].get("statistics", {}).get("corners", 4))
    avg_goal = sum(goals)/len(goals) if goals else 1.5
    avg_corner = sum(corners)/len(corners) if corners else 4.5
    return {"avg_goal": avg_goal, "avg_corner": avg_corner}

def poisson_prob(lam, k):
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def predict_score(home_avg_goal, away_avg_goal, max_goals=5):
    """計算 Poisson 最可能比分"""
    table = []
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            prob = poisson_prob(home_avg_goal, h) * poisson_prob(away_avg_goal, a)
            table.append(((h,a), prob))
    table.sort(key=lambda x: x[1], reverse=True)
    return table[:3]  # 返回前三高概率比分

# ===== Streamlit UI =====
st.set_page_config(layout="wide")
st.title("⚽ Mario Gambling Prediction (Fast View)")

# ===== 左側聯賽選擇 =====
leagues = get_leagues()
leagues_sorted = sort_leagues_by_popularity(leagues)
with st.sidebar:
    league_name = st.selectbox("Select League", list(leagues_sorted.keys()))
league_id = leagues_sorted[league_name]

# ===== 右側比賽快覽表 =====
fixtures = get_fixtures(league_id)
fixtures_sorted = sorted(fixtures, key=lambda x: x["date"])  # 依日期排序

st.markdown(f"### Upcoming Matches - {league_name}")
st.markdown("🏟️ Match | ⚽ Score | 🥅 Corners | 🔢 Total Goals")
st.markdown("---")

for f in fixtures_sorted:
    # 獲取球隊統計數據
    home_stats = get_team_stats(f["home"])
    away_stats = get_team_stats(f["away"])
    
    # 預測比分
    top_scores = predict_score(home_stats["avg_goal"], away_stats["avg_goal"])
    score_emoji = " / ".join([f"{h}-{a} 🔥" for (h,a), p in top_scores])
    
    # 角球預測
    total_corners = home_stats["avg_corner"] + away_stats["avg_corner"]
    corners_emoji = f"Home {home_stats['avg_corner']:.1f} + Away {away_stats['avg_corner']:.1f} = {total_corners:.1f} 🔥 Over"
    
    # 總進球 Over/Under 2.5
    total_goals = home_stats["avg_goal"] + away_stats["avg_goal"]
    goals_emoji = f"{total_goals:.1f} 🔥 Over 2.5" if total_goals > 2.5 else f"{total_goals:.1f} ❌ Under 2.5"
    
    st.markdown(f"{f['home']} vs {f['away']} ({f['date'][:10]}) | {score_emoji} | {corners_emoji} | {goals_emoji}")
