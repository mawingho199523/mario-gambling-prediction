import streamlit as st
import requests
from datetime import datetime
import math

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Keys ======
THE_ODDS_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ====== Poisson 分布 ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== API-Football: 聯賽列表 ======
def get_leagues():
    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {}
    data = r.json()
    leagues = {}
    for item in data["response"]:
        if item["league"]["type"] == "League":
            leagues[item["league"]["id"]] = f"{item['country']['name']} - {item['league']['name']}"
    return leagues

# ====== API-Football: 球隊列表 ======
def get_teams(league_id):
    url = f"https://v3.football.api-sports.io/teams?league={league_id}&season=2025"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {}
    data = r.json()
    teams = {}
    for t in data["response"]:
        teams[t["team"]["name"]] = t["team"]["id"]
    return teams

# ====== API-Football: 球隊近期進球與角球 ======
def get_team_stats(team_id, league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&league={league_id}&season=2025&last=5"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return 1.5, 5
    data = r.json()
    goals, corners = [], []
    for match in data.get("response", []):
        is_home = match["teams"]["home"]["id"] == team_id
        goals.append(match["goals"]["home"] if is_home else match["goals"]["away"])
        corners_stat = match.get("statistics", [])
        corner_value = 5
        for s in corners_stat:
            if s.get("type") == "Corner Kicks":
                corner_value = s.get("home" if is_home else "away", 5)
        corners.append(corner_value)
    avg_goals = sum(goals)/len(goals) if goals else 1.5
    avg_corners = sum(corners)/len(corners) if corners else 5
    return avg_goals, avg_corners

# ====== Poisson 預測比分 ======
def predict_score(home_avg, away_avg):
    score_probs = {}
    for h in range(0,5):
        for a in range(0,5):
            score_probs[(h,a)] = poisson(home_avg,h)*poisson(away_avg,a)
    top_scores = sorted(score_probs.items(), key=lambda x:x[1], reverse=True)[:3]
    over25 = sum(p for (h,a),p in score_probs.items() if h+a>2.5)
    under25 = 1-over25
    return top_scores, over25, under25

# ====== 角球預測 ======
def predict_corners(home_corners, away_corners):
    total = home_corners + away_corners
    over_9_5 = total > 9.5
    return home_corners, away_corners, total, over_9_5

# ====== 讓球盤建議 ======
def handicap_suggestion(home_avg, away_avg, handicap=0.5):
    if home_avg - handicap > away_avg:
        return "🏆 主隊可贏讓球盤"
    else:
        return "⚠️ 主隊可能輸讓球盤"

# ====== The Odds API: 比賽與盤口 ======
def get_odds(sport_key, regions='uk', markets='totals,spreads,h2h'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"apiKey": THE_ODDS_KEY, "regions": regions, "markets": markets}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    return sorted(data, key=lambda x: datetime.fromisoformat(x['commence_time'].replace('Z','')))

# ====== Streamlit 介面 ======
st.title("⚽ Mario Gambling Prediction (自動抓取版)")

# 選聯賽
st.sidebar.header("選擇聯賽")
leagues = get_leagues()
league_keys = st.sidebar.multiselect("聯賽", list(leagues.keys()), format_func=lambda x: leagues[x])

if not league_keys:
    st.info("請選擇至少一個聯賽")
else:
    for league_id in league_keys:
        st.subheader(leagues[league_id])
        teams = get_teams(league_id)
        if not teams:
            st.warning("⚠️ 無法抓取球隊列表")
            continue

        # 用 The Odds API 抓取比賽
        matches = get_odds(f"soccer_{league_id}")
        if not matches:
            st.warning("⚠️ 無法抓取比賽")
            continue

        for match in matches[:20]:
            home = match["home_team"]
            away = match["away_team"]
            match_time = datetime.fromisoformat(match['commence_time'].replace('Z',''))
            st.markdown(f"### {match_time.strftime('%Y-%m-%d %H:%M')} - {home} 🆚 {away}")

            # 自動匹配 team_id
            home_team_id = teams.get(home)
            away_team_id = teams.get(away)
            if not home_team_id or not away_team_id:
                st.warning(f"⚠️ 無法匹配 {home} 或 {away} 的 team_id")
                continue

            # 抓近期進球與角球
            home_avg, home_corners = get_team_stats(home_team_id, league_id)
            away_avg, away_corners = get_team_stats(away_team_id, league_id)

            # 預測比分
            top_scores, over25, under25 = predict_score(home_avg, away_avg)
            st.markdown("**🔝 預測前三比分:**")
            for (h,a), p in top_scores:
                st.write(f"⚽ {home} {h}-{a} {away} ({p*100:.1f}%)")

            # 大小球
            st.write(f"📈 Over 2.5: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
            st.write(f"📉 Under 2.5: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")

            # 角球
            h_c, a_c, total_c, over_c = predict_corners(home_corners, away_corners)
            st.write(f"🥅 角球: {home} {h_c:.1f} | {away} {a_c:.1f} | Total: {total_c:.1f}")
            st.write(f"Over 9.5 角球: {'🔥' if over_c else '❌'}")

            # 讓球盤
            st.write(handicap_suggestion(home_avg, away_avg))

            # 多家莊家盤口
            if match.get("bookmakers"):
                st.markdown("**🎯 多家莊家盤口**")
                for bm in match["bookmakers"]:
                    st.markdown(f"🏦 {bm['title']}")
                    for market in bm["markets"]:
                        if market["key"] == "h2h":
                            st.markdown("⚽ 獨贏盤")
                            for outcome in market["outcomes"]:
                                st.write(f"{outcome['name']}: {outcome['price']} 💰")
                        elif market["key"] == "totals":
                            st.markdown("📈 大小球盤")
                            for o in market["outcomes"]:
                                emoji = "🔥" if o["name"]=="Over" else "❌"
                                st.write(f"{o['name']} {o['point']} : {o['price']} {emoji}")
            st.markdown("---")
