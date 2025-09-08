# ==========================================
# Mario Gambling Prediction Version 6.7
# ==========================================

import streamlit as st
import requests
import datetime
import random

# -----------------------------
# API Keys
# -----------------------------
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
THE_ODDS_KEY = "d00b3f188b2a475a2feaf90da0be67a5"

# -----------------------------
# Helper functions
# -----------------------------
@st.cache_data(ttl=600)
def get_leagues():
    """抓取可用聯賽"""
    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    res = requests.get(url, headers=headers).json()
    leagues = {}
    for item in res.get("response", []):
        league = item.get("league", {})
        country = league.get("country", "Unknown")
        code = league.get("id")
        name = league.get("name")
        if code and name:
            leagues[name] = {"id": code, "country": country}
    return leagues

@st.cache_data(ttl=600)
def get_fixtures(league_id):
    """抓取未來比賽"""
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    res = requests.get(url, headers=headers).json()
    fixtures = []
    for f in res.get("response", []):
        fixture = f.get("fixture", {})
        teams = f.get("teams", {})
        fixtures.append({
            "date": fixture.get("date"),
            "home": teams.get("home", {}).get("name"),
            "home_id": teams.get("home", {}).get("id"),
            "away": teams.get("away", {}).get("name"),
            "away_id": teams.get("away", {}).get("id"),
        })
    return fixtures

@st.cache_data(ttl=600)
def get_team_stats(team_id):
    """取得球隊近期平均進球"""
    url = f"https://v3.football.api-sports.io/teams/statistics?season=2025&team={team_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        stats = res.get("response", {}).get("fixtures", {}).get("played", {})
        home = stats.get("home", {})
        goals = [m.get("goals", {}).get("for", 0) for m in home.get("all", [])]
        avg_goal = sum(goals)/len(goals) if goals else 1.5
        return avg_goal
    except:
        return 1.5

@st.cache_data(ttl=600)
def get_odds_from_theoddsapi(home, away, sport="soccer_epl", regions="eu"):
    """用 The Odds API 嘗試抓盤口"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "regions": regions,
        "markets": "h2h,spreads,totals",
        "apiKey": THE_ODDS_KEY
    }
    try:
        res = requests.get(url, params=params).json()
        for match in res:
            home_team = match.get("home_team", "").lower()
            away_team = match.get("away_team", "").lower()
            if home.lower() in home_team and away.lower() in away_team:
                return match.get("bookmakers", [])[0].get("markets", [])
        return None
    except:
        return None

def betting_suggestions(home, away, pred_home, pred_away, league_code="soccer_epl"):
    """大小球 & 讓球建議"""
    odds_data = get_odds_from_theoddsapi(home, away, sport=league_code)
    total_goals = pred_home + pred_away
    label = "📖 按歷史建議"

    # default fallback
    ou_suggest = "❄️ 小 2.5" if total_goals <=2 else "🔥 大 2.5"
    handicap = f"🏆 推介: {home} -0.5" if pred_home>pred_away else f"🏆 推介: {away} +0.5" if pred_home<pred_away else "⚖️ 和局 → 避開"

    if odds_data:
        for market in odds_data:
            if market["key"] == "totals":
                line = float(market["outcomes"][0]["point"])
                ou_suggest = f"🔥 大 {line}" if total_goals > line else f"❄️ 小 {line}"
                label = "📊 按盤口建議"
            if market["key"] == "spreads":
                handicap_line = market["outcomes"][0].get("point", -0.5)
                if pred_home>pred_away:
                    handicap = f"🏆 推介: {home} {handicap_line}"
                elif pred_home<pred_away:
                    handicap = f"🏆 推介: {away} {handicap_line}"
                else:
                    handicap = "⚖️ 和局 → 避開"
                label = "📊 按盤口建議"

    return ou_suggest, handicap, label

# -----------------------------
# Streamlit App
# -----------------------------
st.title("Mario Gambling Prediction v6.7 ⚡️")

# 聯賽列表
leagues = get_leagues()
league_name = st.sidebar.selectbox("選擇聯賽", list(leagues.keys()))
league_id = leagues[league_name]["id"]

# 顯示比賽
fixtures = get_fixtures(league_id)
fixtures = sorted(fixtures, key=lambda x: x["date"])

for f in fixtures:
    # 用 API-Football 計算比分預測
    home_avg_goal = get_team_stats(f['home_id'])
    away_avg_goal = get_team_stats(f['away_id'])

    pred_home = round(random.gauss(home_avg_goal, 0.8))
    pred_away = round(random.gauss(away_avg_goal, 0.8))

    ou_suggest, handicap, label = betting_suggestions(f["home"], f["away"], pred_home, pred_away)

    st.markdown(f"### {f['home']} vs {f['away']} ({f['date'][:10]})")
    st.markdown(f"**比分預測**: {pred_home} - {pred_away}")
    st.markdown(f"**大小球建議**: {ou_suggest} ({label})")
    st.markdown(f"**讓球盤建議**: {handicap} ({label})")
    st.markdown("---")
