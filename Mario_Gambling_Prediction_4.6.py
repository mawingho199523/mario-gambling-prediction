import streamlit as st
import requests
from math import exp, factorial

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")
st.title("⚽ Mario Gambling Prediction")

# =========================
# Poisson function
# =========================
def poisson(k, lam):
    return (lam**k * exp(-lam)) / factorial(k)

# =========================
# 抓取可用聯賽列表 (防呆 & 排序)
# =========================
@st.cache_data
def get_leagues():
    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    leagues = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            league = item.get("league", {})
            country = league.get("country", "Unknown")  # 防呆
            name = league.get("name", "Unknown League")
            seasons = item.get("seasons", [])
            season = seasons[-1].get("year") if seasons else None
            if season:
                leagues.append({
                    "id": league.get("id"),
                    "name": name,
                    "country": country,
                    "season": season
                })
    # 排序：熱門聯賽靠前 (可自行調整)
    popular_leagues = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
    leagues.sort(key=lambda x: (0 if x["name"] in popular_leagues else 1, x["name"]))
    return leagues

# =========================
# 抓取聯賽比賽
# =========================
@st.cache_data
def get_fixtures(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    fixtures = []
    if r.status_code == 200:
        for f in r.json().get("response", []):
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            date = f["fixture"]["date"]
            fixtures.append({"home": home, "away": away, "date": date})
    return fixtures

# =========================
# 取得球隊近期比賽（進球與角球）
# =========================
def get_team_recent_fixtures(team_name, last_n=5):
    url = f"https://v3.football.api-sports.io/fixtures?team={team_name}&last={last_n}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    goals = []
    corners = []
    if r.status_code == 200:
        for item in r.json().get("response", []):
            score = item.get("score", {}).get("fulltime", {})
            goals_home = score.get("home") or 0
            goals_away = score.get("away") or 0
            fixture_teams = item.get("teams", {})
            if fixture_teams.get("home", {}).get("name") == team_name:
                goals.append(goals_home)
            else:
                goals.append(goals_away)
            # 角球數據（若缺省設 5）
            statistics = item.get("statistics", [])
            corner_value = 5
            for stat in statistics:
                if stat.get("type") == "Corner Kicks":
                    if fixture_teams.get("home", {}).get("name") == team_name:
                        corner_value = stat.get("home") or 5
                    else:
                        corner_value = stat.get("away") or 5
            corners.append(corner_value)
    return goals, corners

# =========================
# 預測比賽
# =========================
def predict_match(home, away):
    home_goals_list, home_corners_list = get_team_recent_fixtures(home)
    away_goals_list, away_corners_list = get_team_recent_fixtures(away)

    home_avg = sum(home_goals_list)/len(home_goals_list) if home_goals_list else 1.5
    away_avg = sum(away_goals_list)/len(away_goals_list) if away_goals_list else 1.0

    home_corners_avg = sum(home_corners_list)/len(home_corners_list) if home_corners_list else 5
    away_corners_avg = sum(away_corners_list)/len(away_corners_list) if away_corners_list else 4

    pred_home = round(home_avg)
    pred_away = round(away_avg)
    pred_home_corners = round(home_corners_avg)
    pred_away_corners = round(away_corners_avg)

    total_goals = home_avg + away_avg
    over_prob = sum([poisson(k, total_goals) for k in range(3, 10)])

    return {
        "home_goals": pred_home,
        "away_goals": pred_away,
        "home_corners": pred_home_corners,
        "away_corners": pred_away_corners,
        "over_prob": over_prob
    }

# =========================
# 左邊聯賽選擇
# =========================
leagues = get_leagues()
league_names = [f"{l['country']} - {l['name']}" for l in leagues]
st.sidebar.header("Select League")
selected_league = st.sidebar.selectbox("Leagues", league_names)
league_id = leagues[league_names.index(selected_league)]["id"]

# =========================
# 顯示比賽列表
# =========================
fixtures = get_fixtures(league_id)
fixtures = sorted(fixtures, key=lambda x: x["date"])  # 按日期排列

for f in fixtures:
    pred = predict_match(f["home"], f["away"])
    st.markdown(f"### {f['home']} 🆚 {f['away']} ({f['date'][:10]})")
    st.markdown(
        f"比分預測: {pred['home_goals']} - {pred['away_goals']} | "
        f"角球: {pred['home_corners']} - {pred['away_corners']} | "
        f"Over 2.5: {round(pred['over_prob']*100)}% "
        f"{'🟢' if pred['over_prob']>0.5 else '🔴'}"
    )
    st.markdown("---")
