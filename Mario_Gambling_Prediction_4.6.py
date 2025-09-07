import streamlit as st
import requests
import math
import random
from datetime import datetime

API_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {"x-apisports-key": API_KEY}

# -------------------- 防呆獲取球隊近期統計 --------------------
@st.cache_data
def get_team_stats(team_id):
    url = f"{BASE_URL}/teams/statistics?season=2025&team={team_id}"
    res = requests.get(url, headers=HEADERS)
    try:
        stats = res.json().get('response', {})
    except:
        stats = {}

    home_recent = stats.get('fixtures', {}).get('played', {}).get('home')
    away_recent = stats.get('fixtures', {}).get('played', {}).get('away')

    # 平均進球
    goals_home = [m.get('goals', {}).get('for', {}).get('total', 1.5) for m in home_recent] if home_recent else [1.5]
    goals_away = [m.get('goals', {}).get('for', {}).get('total', 1.5) for m in away_recent] if away_recent else [1.5]
    avg_goal = (sum(goals_home) + sum(goals_away)) / (len(goals_home) + len(goals_away))

    # 平均角球
    corners_home = [m.get('corners', {}).get('for', {}).get('total', 5) for m in home_recent] if home_recent else [5]
    corners_away = [m.get('corners', {}).get('for', {}).get('total', 5) for m in away_recent] if away_recent else [5]
    avg_corner = (sum(corners_home) + sum(corners_away)) / (len(corners_home) + len(corners_away))

    return avg_goal, avg_corner

# -------------------- H2H 近期對賽 --------------------
@st.cache_data
def get_h2h(home_id, away_id):
    url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
    res = requests.get(url, headers=HEADERS)
    try:
        matches = res.json().get('response', [])
    except:
        matches = []

    home_goals = []
    away_goals = []
    for m in matches:
        home_goals.append(m.get('goals', {}).get('home', 1))
        away_goals.append(m.get('goals', {}).get('away', 1))

    if home_goals and away_goals:
        avg_home = sum(home_goals)/len(home_goals)
        avg_away = sum(away_goals)/len(away_goals)
    else:
        avg_home, avg_away = 1.5, 1.5

    return avg_home, avg_away

# -------------------- Poisson 隨機比分 --------------------
def poisson_score(avg_home, avg_away):
    max_goals = 5
    scores = []
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            prob = (math.exp(-avg_home) * (avg_home**i)/math.factorial(i)) * \
                   (math.exp(-avg_away) * (avg_away**j)/math.factorial(j))
            scores.append(((i,j), prob))
    scores.sort(key=lambda x: x[1], reverse=True)
    top_scores = scores[:3]  # 前3高概率
    return random.choice(top_scores)[0]

# -------------------- Over/Under 2.5 --------------------
def over_under(avg_home, avg_away):
    total_avg = avg_home + avg_away
    over_prob = min(0.95, max(0.05, total_avg/3))  # 防呆
    under_prob = 1 - over_prob
    return over_prob, under_prob

# -------------------- 勝負趨勢 emoji --------------------
def trend_emoji(home, away):
    outcome = random.choices(['🏆', '🤝', '💀'], weights=[0.45,0.25,0.3])[0]
    return outcome

# -------------------- 抓取聯賽 --------------------
@st.cache_data
def get_leagues():
    url = f"{BASE_URL}/leagues?season=2025"
    res = requests.get(url, headers=HEADERS)
    try:
        leagues = res.json().get('response', [])
    except:
        leagues = []
    league_list = []
    for item in leagues:
        league = item.get('league', {})
        if league.get('id') and league.get('name'):
            league_list.append({'id': league['id'], 'name': league['name']})
    return league_list

# -------------------- 抓取比賽 --------------------
@st.cache_data
def get_fixtures(league_id):
    url = f"{BASE_URL}/fixtures?season=2025&league={league_id}"
    res = requests.get(url, headers=HEADERS)
    try:
        matches = res.json().get('response', [])
    except:
        matches = []
    fixtures = []
    for f in matches:
        fixture = {
            'home_id': f['teams']['home']['id'],
            'home': f['teams']['home']['name'],
            'away_id': f['teams']['away']['id'],
            'away': f['teams']['away']['name'],
            'date': f['fixture']['date']
        }
        fixtures.append(fixture)
    fixtures.sort(key=lambda x: x['date'])
    return fixtures

# -------------------- Streamlit 顯示 --------------------
st.title("Mario Gambling Prediction Version 6.2")

leagues = get_leagues()
league_names = [l['name'] for l in leagues]

selected_league_name = st.sidebar.selectbox("Select League", league_names)
selected_league = next(l for l in leagues if l['name']==selected_league_name)

fixtures = get_fixtures(selected_league['id'])

for f in fixtures:
    home_avg_goal, home_avg_corner = get_team_stats(f['home_id'])
    away_avg_goal, away_avg_corner = get_team_stats(f['away_id'])
    h2h_home, h2h_away = get_h2h(f['home_id'], f['away_id'])

    avg_home = (home_avg_goal + h2h_home)/2
    avg_away = (away_avg_goal + h2h_away)/2

    # 比分
    score_pred = poisson_score(avg_home, avg_away)

    # 角球
    corner_pred = int((home_avg_corner + away_avg_corner)/2 + random.choice([-1,0,1]))

    # 大小球
    over_prob, under_prob = over_under(avg_home, avg_away)
    ou_emoji = "⚡Over" if over_prob>under_prob else "🛡️Under"

    # 勝負趨勢
    trend = trend_emoji(f['home'], f['away'])

    st.markdown(f"### {f['home']} vs {f['away']} ({f['date'][:10]})")
    st.markdown(f"⚽ Predicted Score: {score_pred[0]} - {score_pred[1]}")
    st.markdown(f"🥅 Predicted Corners: {corner_pred}")
    st.markdown(f"📊 Over/Under 2.5: {ou_emoji}")
    st.markdown(f"🎯 Trend: {trend}")
