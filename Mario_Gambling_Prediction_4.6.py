import streamlit as st
import requests
from datetime import datetime
import math

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Keys ======
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
THE_ODDS_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ====== Poisson 分布 ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== 聯賽選擇對應 The Odds API sport_key ======
SPORT_KEYS = {
    "英超": "soccer_epl",
    "西甲": "soccer_spain_la_liga",
    "意甲": "soccer_italy_serie_a",
    "德甲": "soccer_germany_bundesliga",
    "法甲": "soccer_france_ligue_one",
    "日職": "soccer_japan_j1",
    "日乙": "soccer_japan_j2",
    "荷甲": "soccer_netherlands_eredivisie",
    "荷乙": "soccer_netherlands_eredivisie_2",
    "英冠": "soccer_england_championship",
    "英甲": "soccer_england_league_one",
    "英乙": "soccer_england_league_two",
    "美職": "soccer_usa_mls",
    "阿甲": "soccer_argentina_superliga",
    "墨超": "soccer_mexico_liga_mx"
}

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

# ====== The Odds API: 抓莊家盤口 ======
def get_odds(sport_key, regions='uk', markets='totals,spreads,h2h'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"apiKey": THE_ODDS_KEY, "regions": regions, "markets": markets}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    return sorted(data, key=lambda x: datetime.fromisoformat(x['commence_time'].replace('Z','')))

# ====== Streamlit 介面 ======
st.title("⚽ Mario Gambling Prediction (自動抓取比賽版)")

# 選聯賽
st.sidebar.header("選擇聯賽")
selected_leagues = st.sidebar.multiselect("聯賽", list(SPORT_KEYS.keys()))

if not selected_leagues:
    st.info("請選擇至少一個聯賽")
else:
    for league_name in selected_leagues:
        sport_key = SPORT_KEYS[league_name]
        st.subheader(league_name)

        # 使用 API-Football 抓 fixtures
        league_id = None
        leagues = get_leagues()
        for k,v in leagues.items():
            if league_name in v:
                league_id = k
                break
        if not league_id:
            st.warning("⚠️ 無法匹配聯賽 ID")
            continue

        teams = get_teams(league_id)
        if not teams:
            st.warning("⚠️ 無法抓取球隊列表")
            continue

        url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.warning("⚠️ 無法抓取比賽")
            continue
        matches = r.json().get("response", [])

        for match in matches:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            match_time = datetime.fromisoformat(match['fixture']['date'].replace('Z',''))
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
            odds = get_odds(sport_key)
            match_odds = [m for m in odds if m['home_team']==home and m['away_team']==away]
            if match_odds:
                st.markdown("**🎯 多家莊家盤口**")
                for bm in match_odds[0].get("bookmakers", []):
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
