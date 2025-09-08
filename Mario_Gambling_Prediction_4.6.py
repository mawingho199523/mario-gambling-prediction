import streamlit as st
import requests
from datetime import datetime

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# =============================
# 取得聯賽清單
# =============================
@st.cache_data
def get_leagues():
    url = f"{BASE_URL}/leagues"
    res = requests.get(url, headers=HEADERS).json()
    leagues = res.get("response", [])
    available = []
    for l in leagues:
        try:
            league_id = l["league"]["id"]
            name = l["league"]["name"]
            country = l["country"]["name"]
            available.append({
                "id": league_id,
                "name": f"{name} ({country})"
            })
        except:
            continue
    return available

# =============================
# 取得即將比賽
# =============================
@st.cache_data
def get_upcoming_fixtures(league_id, season=2025, next_n=20):
    url = f"{BASE_URL}/fixtures?league={league_id}&season={season}&next={next_n}"
    res = requests.get(url, headers=HEADERS).json()
    fixtures = res.get("response", [])
    matches = []
    for f in fixtures:
        try:
            matches.append({
                "fixture_id": f["fixture"]["id"],
                "date": f["fixture"]["date"],
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "home_id": f["teams"]["home"]["id"],
                "away_id": f["teams"]["away"]["id"],
                "league_id": f["league"]["id"]
            })
        except:
            continue
    return matches

# =============================
# 改良版 get_team_stats
# =============================
@st.cache_data
def get_team_stats(team_id, league_id, season=2025):
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season={season}&team={team_id}"
    res = requests.get(url, headers=HEADERS).json()
    stats = res.get("response", {})
    if stats:
        goals = stats.get("goals", {}).get("for", {}).get("average", {}).get("total", "1.5")
        return float(goals) if goals else 1.5
    return 1.5  # fallback

# =============================
# 取得 H2H
# =============================
@st.cache_data
def get_h2h(home_id, away_id, last=5):
    url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}&last={last}"
    res = requests.get(url, headers=HEADERS).json()
    fixtures = res.get("response", [])
    results = []
    for f in fixtures:
        try:
            results.append(f"{f['teams']['home']['name']} {f['goals']['home']} - {f['goals']['away']} {f['teams']['away']['name']}")
        except:
            continue
    return results

# =============================
# 信心指數
# =============================
def get_confidence(pred_home, pred_away):
    diff = abs(pred_home - pred_away)
    if diff >= 2:
        return "⭐⭐⭐⭐⭐"
    elif diff == 1:
        return "⭐⭐⭐"
    else:
        return "⭐⭐"

# =============================
# Streamlit 介面
# =============================
st.title("⚽ Mario Gambling Prediction Version 6.6")

# 聯賽選擇
leagues = get_leagues()
league_map = {l["name"]: l["id"] for l in leagues}
selected_league = st.sidebar.selectbox("選擇聯賽", list(league_map.keys()))
league_id = league_map[selected_league]

# 抓比賽
fixtures = get_upcoming_fixtures(league_id)
fixtures = sorted(fixtures, key=lambda x: x["date"])

# 顯示比賽
for f in fixtures:
    st.markdown(f"### {f['home']} 🆚 {f['away']}")
    st.markdown(f"📅 {datetime.fromisoformat(f['date']).strftime('%Y-%m-%d %H:%M')}")

    # 球隊數據
    home_avg_goal = get_team_stats(f["home_id"], league_id)
    away_avg_goal = get_team_stats(f["away_id"], league_id)

    # 預測比分
    pred_home = round(home_avg_goal)
    pred_away = round(away_avg_goal)
    total_goals = pred_home + pred_away

    # 大小球建議
    if total_goals >= 3:
        ou_suggest = "🔥 大 2.5"
    else:
        ou_suggest = "❄️ 細 2.5"

    # 讓球盤建議
    if pred_home > pred_away:
        handicap = f"🏆 推介: {f['home']} -0.5"
    elif pred_home < pred_away:
        handicap = f"🏆 推介: {f['away']} +0.5"
    else:
        handicap = "⚖️ 和局 → 建議避開或買受讓方 +0.5"

    # 信心指數
    confidence = get_confidence(pred_home, pred_away)

    # 顯示
    st.markdown(f"**比分預測**: {f['home']} {pred_home} - {pred_away} {f['away']}")
    st.markdown(f"**大小球建議**: {ou_suggest}")
    st.markdown(f"**讓球盤建議**: {handicap}")
    st.markdown(f"**信心指數**: {confidence}")

    # H2H
    h2h_results = get_h2h(f["home_id"], f["away_id"])
    if h2h_results:
        st.markdown("**歷史對賽 (近5場)**")
        for r in h2h_results:
            st.markdown(f"- {r}")

    st.divider()
