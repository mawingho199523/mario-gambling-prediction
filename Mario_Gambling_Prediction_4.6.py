import streamlit as st
import requests
from bs4 import BeautifulSoup
import math

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Keys ======
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
THE_ODDS_KEY = "d00b3f188b2a475a2feaf90da0be67a5"

HEADERS_FOOTBALL = {"x-apisports-key": API_FOOTBALL_KEY}
HEADERS_ODDS = {"X-RapidAPI-Key": THE_ODDS_KEY, "X-RapidAPI-Host": "the-odds-api.p.rapidapi.com"}

# ====== Poisson 分布 ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== API-Football: 可用聯賽 ======
@st.cache_data
def get_available_leagues():
    url = "https://v3.football.api-sports.io/leagues"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    leagues = {}
    if r.status_code == 200:
        data = r.json()
        for item in data["response"]:
            leagues[item["league"]["name"]] = item["league"]["id"]
    return leagues

# ====== API-Football: 聯賽球隊 ======
@st.cache_data
def get_teams_by_league(league_id, season=2025):
    url = f"https://v3.football.api-sports.io/teams?league={league_id}&season={season}"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    teams = {}
    if r.status_code == 200:
        data = r.json()
        for item in data["response"]:
            name = item["team"]["name"]
            teams[name] = item["team"]["id"]
    return teams

# ====== API-Football: 球隊統計 ======
@st.cache_data
def get_team_stats(team_id):
    url = f"https://v3.football.api-sports.io/teams/statistics?team={team_id}"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        home = data["response"]["fixtures"]["played"]["home"]
        goals_for = home["goals"]["for"]["total"]
        goals_against = home["goals"]["against"]["total"]
        corners_for = home["corners"]["for"]["total"]
        matches = home["total"]
        if matches > 0:
            return goals_for/matches, goals_against/matches, corners_for/matches
    except:
        return None

# ====== The Odds API: 盤口 ======
def get_odds(home_team, away_team, sport='soccer_epl'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {"apiKey": THE_ODDS_KEY, "regions": "uk", "markets": "h2h,spreads,totals"}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return None
    data = r.json()
    for match in data:
        if home_team in match["home_team"] and away_team in match["away_team"]:
            return match
    return None

# ====== SofaScore 爬蟲補充近期狀態 ======
def scrape_sofascore(team_name):
    url = f"https://www.sofascore.com/team/football/{team_name.replace(' ','-')}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    try:
        form = soup.select_one(".FormTable")
        recent_scores = [int(td.text.strip()) for td in form.select("td.Goals")]
        return recent_scores
    except:
        return None

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
    over = total>9.5
    return home_corners, away_corners, total, over

# ====== 讓球建議 ======
def handicap_suggestion(home_avg, away_avg, handicap=0.5):
    if home_avg-handicap > away_avg:
        return "🏆 Home team can win the handicap"
    else:
        return "⚠️ Home team might lose the handicap"

# ====== Streamlit 介面 ======
st.title("⚽ Mario Gambling Prediction")

# 選聯賽
leagues = get_available_leagues()
league_name = st.selectbox("選擇聯賽", list(leagues.keys()))
league_id = leagues[league_name]

# 選球隊
teams = get_teams_by_league(league_id)
home_team = st.selectbox("主隊", list(teams.keys()))
away_team = st.selectbox("客隊", list(teams.keys()))

if st.button("預測比賽結果"):
    home_id = teams[home_team]
    away_id = teams[away_team]

    home_stats = get_team_stats(home_id)
    away_stats = get_team_stats(away_id)

    if home_stats and away_stats:
        home_avg, _, home_corners = home_stats
        away_avg, _, away_corners = away_stats

        # 比分預測
        top_scores, over25, under25 = predict_score(home_avg, away_avg)
        # 角球預測
        h_c, a_c, total_c, over_c = predict_corners(home_corners, away_corners)

        st.subheader(f"{home_team} 🆚 {away_team}")
        st.markdown("**🔝 預測前三高機率比分:**")
        for (h,a), p in top_scores:
            st.write(f"⚽ {home_team} {h}-{a} {away_team} ({p*100:.1f}%)")
        st.write(f"📈 Over 2.5: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
        st.write(f"📉 Under 2.5: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")
        st.write(handicap_suggestion(home_avg, away_avg))
        st.write(f"🥅 角球: {home_team} {h_c:.1f} | {away_team} {a_c:.1f} | Total: {total_c:.1f}")
        st.write(f"Over 9.5 角球: {'🔥' if over_c else '❌'}")
    else:
        st.error("❌ 無法抓取球隊統計資料，請檢查 API Key 或球隊名稱")
