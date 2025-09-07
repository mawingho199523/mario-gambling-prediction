import streamlit as st
import requests
from datetime import datetime
import math

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Key ======
THE_ODDS_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ====== Poisson 分布 ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== SofaScore 聯賽列表 ======
def fetch_sofascore_leagues():
    url = "https://api.sofascore.com/api/v1/sport/soccer/unique-tournaments"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            st.warning("⚠️ 無法抓取 SofaScore 聯賽列表")
            return {}
        data = r.json()
        leagues = {}
        for league in data.get("uniqueTournaments", []):
            leagues[league["name"]] = league["id"]
        return leagues
    except Exception as e:
        st.error(f"抓取聯賽列表失敗: {e}")
        return {}

# ====== 抓取聯賽球隊 ======
def fetch_sofascore_league_teams(league_id):
    url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/2025/teams"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            st.warning("⚠️ 無法抓取聯賽球隊列表")
            return {}
        data = r.json()
        team_map = {}
        for t in data.get("teams", []):
            team_map[t["name"]] = t["id"]
        return team_map
    except Exception as e:
        st.error(f"抓取聯賽球隊列表失敗: {e}")
        return {}

# ====== 抓取球隊近 5 場比賽平均進球與角球 ======
def fetch_sofascore_team_stats(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return 1.5, 5.0
        data = r.json()
        goals, corners = [], []
        for event in data.get("events", []):
            try:
                home_team = event["homeTeam"]["name"]
                away_team = event["awayTeam"]["name"]
                home_goals = event["homeScore"]["current"]
                away_goals = event["awayScore"]["current"]
                team_name = event.get("team", {}).get("name", home_team)
                goals.append(home_goals if home_team==team_name else away_goals)
                home_corners = away_corners = 0
                for s in event.get("statistics", []):
                    if s["name"] == "Corners":
                        home_corners = s["home"]
                        away_corners = s["away"]
                corners.append(home_corners if home_team==team_name else away_corners)
            except:
                continue
        avg_goals = sum(goals)/len(goals) if goals else 1.5
        avg_corners = sum(corners)/len(corners) if corners else 5.0
        return avg_goals, avg_corners
    except:
        return 1.5, 5.0

# ====== The Odds API ======
def get_sports():
    url = "https://api.the-odds-api.com/v4/sports/"
    r = requests.get(url, params={"apiKey": THE_ODDS_KEY})
    if r.status_code != 200:
        return {}
    data = r.json()
    return {s['key']: s['title'] for s in data if s['key'].startswith("soccer")}

def get_odds(sport_key, regions='uk', markets='totals,spreads,h2h'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"apiKey": THE_ODDS_KEY, "regions": regions, "markets": markets}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    return sorted(data, key=lambda x: datetime.fromisoformat(x['commence_time'].replace('Z','')))

# ====== 預測比分 ======
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

# ====== Streamlit 介面 ======
st.title("⚽ Mario Gambling Prediction 自動抓取聯賽+球隊+角球版")

# 側邊欄：選擇聯賽
st.sidebar.header("選擇聯賽")
sofa_leagues = fetch_sofascore_leagues()
if sofa_leagues:
    league_name = st.sidebar.selectbox("聯賽", list(sofa_leagues.keys()))
    league_id_input = sofa_leagues[league_name]
    st.sidebar.success(f"選擇聯賽: {league_name} (ID: {league_id_input})")
    TEAM_ID_MAP = fetch_sofascore_league_teams(league_id_input)
    if TEAM_ID_MAP:
        st.sidebar.success(f"成功抓取 {len(TEAM_ID_MAP)} 支球隊")
else:
    st.sidebar.warning("⚠️ 無法抓取聯賽列表，請手動輸入 SofaScore 聯賽 ID")
    TEAM_ID_MAP = {}

def get_team_id(team_name):
    return TEAM_ID_MAP.get(team_name, None)

# 取得聯賽比賽
sports = get_sports()
if not sports:
    st.warning("⚠️ 無法抓取聯賽列表")
else:
    league_key = st.selectbox("The Odds API 聯賽", list(sports.keys()), format_func=lambda x: sports[x])
    matches = get_odds(league_key)
    if not matches:
        st.warning("⚠️ 無法抓取比賽資料")
    else:
        for match in matches[:10]:
            home = match["home_team"]
            away = match["away_team"]
            match_time = datetime.fromisoformat(match['commence_time'].replace('Z',''))
            st.markdown(f"### {match_time.strftime('%Y-%m-%d %H:%M')} - {home} 🆚 {away}")

            home_id = get_team_id(home)
            away_id = get_team_id(away)

            if home_id is None or away_id is None:
                st.warning("⚠️ 無法自動對應球隊 ID，請手動輸入 SofaScore ID")
                home_id = st.text_input(f"{home} SofaScore ID")
                away_id = st.text_input(f"{away} SofaScore ID")

            if home_id and away_id:
                home_avg, home_corners = fetch_sofascore_team_stats(home_id)
                away_avg, away_corners = fetch_sofascore_team_stats(away_id)

                top_scores, over25, under25 = predict_score(home_avg, away_avg)
                st.markdown("**🔝 預測前三比分:**")
                for (h,a), p in top_scores:
                    st.write(f"⚽ {home} {h}-{a} {away} ({p*100:.1f}%)")

                st.write(f"📈 Over 2.5: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
                st.write(f"📉 Under 2.5: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")

                h_c, a_c, total_c, over_c = predict_corners(home_corners, away_corners)
                st.write(f"🥅 角球: {home} {h_c:.1f} | {away} {a_c:.1f} | Total: {total_c:.1f}")
                st.write(f"Over 9.5 角球: {'🔥' if over_c else '❌'}")

                st.write(handicap_suggestion(home_avg, away_avg))

                if match.get("bookmakers"):
                    st.markdown("**🎯 多家莊家盤口**")
                    for bm in match["bookmakers"]:
                        st.markdown(f"🏦 {bm['title']}")
                        for market in bm["markets"]:
                            if market["key"] == "h2h":
                                st.markdown("⚽ 獨贏盤")
                                for outcome in market["outcomes"]:
                                    team_name = outcome["name"]
                                    st.write(f"{team_name}: {outcome['price']} 💰")
                            elif market["key"] == "totals":
                                st.markdown("📈 大小球盤")
                                for o in market["outcomes"]:
                                    emoji = "🔥" if o["name"]=="Over" else "❌"
                                    st.write(f"{o['name']} {o['point']} : {o['price']} {emoji}")
            st.markdown("---")
