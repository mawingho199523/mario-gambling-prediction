import streamlit as st
import requests
from datetime import datetime
import numpy as np

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# -----------------------------
# 取得聯賽列表
@st.cache_data
def get_leagues():
    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    res = requests.get(url, headers=headers).json()
    leagues = []
    for item in res.get("response", []):
        league = item.get("league")
        country = league.get("country")
        if league and country:
            leagues.append({"id": league["id"], "name": league["name"], "country": country})
    return leagues

# -----------------------------
# 取得比賽
@st.cache_data
def get_fixtures(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    res = requests.get(url, headers=headers).json()
    fixtures = []
    for f in res.get("response", []):
        fixture = f.get("fixture")
        teams = f.get("teams")
        if fixture and teams:
            fixtures.append({
                "home": teams["home"]["name"],
                "away": teams["away"]["name"],
                "home_id": teams["home"]["id"],
                "away_id": teams["away"]["id"],
                "date": fixture["date"]
            })
    return fixtures

# -----------------------------
# 取得球隊近期進球/失球平均
@st.cache_data
def get_team_stats(team_id):
    url = f"https://v3.football.api-sports.io/teams/statistics?season=2025&team={team_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    res = requests.get(url, headers=headers).json()
    stats = res.get("response", {})
    home_fixtures = stats.get('fixtures', {}).get('played', {}).get('home', [])
    away_fixtures = stats.get('fixtures', {}).get('played', {}).get('away', [])

    home_goals = [m['goals']['for']['total'] for m in home_fixtures if m['goals']['for']['total'] is not None]
    home_conceded = [m['goals']['against']['total'] for m in home_fixtures if m['goals']['against']['total'] is not None]
    away_goals = [m['goals']['for']['total'] for m in away_fixtures if m['goals']['for']['total'] is not None]
    away_conceded = [m['goals']['against']['total'] for m in away_fixtures if m['goals']['against']['total'] is not None]

    home_avg_goal = np.mean(home_goals) if home_goals else 1.5
    home_avg_conceded = np.mean(home_conceded) if home_conceded else 1.0
    away_avg_goal = np.mean(away_goals) if away_goals else 1.2
    away_avg_conceded = np.mean(away_conceded) if away_conceded else 1.1

    return home_avg_goal, home_avg_conceded, away_avg_goal, away_avg_conceded

# -----------------------------
# 預測比分
def predict_score(home_avg_goal, home_avg_conceded, away_avg_goal, away_avg_conceded):
    # 簡單公式：主隊進球 = 主隊平均進球 * 客隊平均失球 / 2
    home_expected = (home_avg_goal + away_avg_conceded)/2
    away_expected = (away_avg_goal + home_avg_conceded)/2
    # Poisson 模擬
    home_score = int(round(np.random.poisson(home_expected)))
    away_score = int(round(np.random.poisson(away_expected)))
    return f"{home_score}-{away_score}", "🔵" if (home_score + away_score) > 2.5 else "🔴", "🏆" if home_score>away_score else "🏁" if away_score>home_score else "🤝"

# -----------------------------
# 主程式
st.title("Mario Gambling Prediction Version 6.6.2")

leagues = get_leagues()

available_leagues = []
for league in leagues:
    fixtures = get_fixtures(league["id"])
    if fixtures:
        available_leagues.append(league)

if not available_leagues:
    st.warning("⚠️ 目前沒有任何聯賽有即將比賽資料")
else:
    league_names = [f"{l['name']} ({l['country']})" for l in available_leagues]
    selected_idx = st.sidebar.selectbox("選擇聯賽", range(len(league_names)), format_func=lambda x: league_names[x])
    selected_league = available_leagues[selected_idx]

    fixtures = get_fixtures(selected_league["id"])
    if not fixtures:
        st.warning(f"⚠️ {selected_league['name']} 暫無即將比賽資料")
    else:
        fixtures.sort(key=lambda x: x['date'])
        for f in fixtures:
            try:
                home_avg_goal, home_avg_conceded, away_avg_goal, away_avg_conceded = get_team_stats(f['home_id'])
                score, over_emoji, trend_emoji = predict_score(home_avg_goal, home_avg_conceded, away_avg_goal, away_avg_conceded)
            except:
                score, over_emoji, trend_emoji = "1-1", "🔴", "🤝"  # 預設值

            st.markdown(f"### {f['home']} 🆚 {f['away']} ({datetime.fromisoformat(f['date']).strftime('%Y-%m-%d %H:%M')})")
            st.markdown(f"比分預測: ⚽️ {score}")
            st.markdown(f"大小球: {over_emoji}")
            st.markdown(f"勝負趨勢: {trend_emoji}")
            st.markdown("---")
