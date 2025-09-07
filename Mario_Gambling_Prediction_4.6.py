import streamlit as st
import requests
from datetime import datetime
import math

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Keys ======
API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"
THE_ODDS_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ====== Poisson function ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== League Mapping (league_id for API-Football) ======
LEAGUE_MAPPING = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "J1 League": 1020,
    "J2 League": 1021,
    "Eredivisie": 88,
    "Eerste Divisie": 89,
    "Championship": 40,
    "League One": 41,
    "League Two": 42,
    "MLS": 253,
    "Argentine Primera": 128,
    "Liga MX": 262
}

# ====== Fetch teams for a league ======
def get_teams(league_id):
    url = f"https://v3.football.api-sports.io/teams?league={league_id}&season=2025"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {}
    data = r.json()
    teams = {t["team"]["name"]: t["team"]["id"] for t in data.get("response", [])}
    return teams

# ====== Fetch last 5 matches stats ======
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
        corners.append(5)  # fallback, can parse statistics if available
    avg_goals = sum(goals)/len(goals) if goals else 1.5
    avg_corners = sum(corners)/len(corners) if corners else 5
    return avg_goals, avg_corners

# ====== Score prediction ======
def predict_score(home_avg, away_avg):
    score_probs = {}
    for h in range(0,5):
        for a in range(0,5):
            score_probs[(h,a)] = poisson(home_avg,h)*poisson(away_avg,a)
    top_scores = sorted(score_probs.items(), key=lambda x:x[1], reverse=True)[:3]
    over25 = sum(p for (h,a),p in score_probs.items() if h+a>2.5)
    under25 = 1-over25
    return top_scores, over25, under25

# ====== Corner prediction ======
def predict_corners(home_corners, away_corners):
    total = home_corners + away_corners
    over_9_5 = total > 9.5
    return home_corners, away_corners, total, over_9_5

# ====== Handicap suggestion ======
def handicap_suggestion(home_avg, away_avg, handicap=0.5):
    if home_avg - handicap > away_avg:
        return "🏆 Home can win handicap"
    else:
        return "⚠️ Home might lose handicap"

# ====== Streamlit UI ======
st.title("⚽ Mario Gambling Prediction (English Version)")

selected_leagues = st.sidebar.multiselect("Select Leagues", list(LEAGUE_MAPPING.keys()))

if not selected_leagues:
    st.info("Please select at least one league")
else:
    for league_name in selected_leagues:
        league_id = LEAGUE_MAPPING.get(league_name)
        if not league_id:
            st.warning(f"⚠️ Cannot find league ID for {league_name}")
            continue

        st.subheader(league_name)
        teams = get_teams(league_id)
        if not teams:
            st.warning("⚠️ Cannot fetch team list")
            continue

        # Fetch next 10 fixtures
        url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        r = requests.get(url, headers=headers)
        matches = r.json().get("response", [])
        if not matches:
            st.warning("⚠️ Cannot fetch fixtures")
            continue

        for match in matches:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            match_time = datetime.fromisoformat(match['fixture']['date'].replace('Z',''))
            st.markdown(f"### {match_time.strftime('%Y-%m-%d %H:%M')} - {home} 🆚 {away}")

            home_id = teams.get(home)
            away_id = teams.get(away)
            if not home_id or not away_id:
                st.warning(f"⚠️ Cannot find team ID for {home} or {away}")
                continue

            home_avg, home_corners = get_team_stats(home_id, league_id)
            away_avg, away_corners = get_team_stats(away_id, league_id)

            top_scores, over25, under25 = predict_score(home_avg, away_avg)
            st.markdown("**🔝 Top 3 score predictions:**")
            for (h,a), p in top_scores:
                st.write(f"⚽ {home} {h}-{a} {away} ({p*100:.1f}%)")

            st.write(f"📈 Over 2.5: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
            st.write(f"📉 Under 2.5: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")

            h_c, a_c, total_c, over_c = predict_corners(home_corners, away_corners)
            st.write(f"🥅 Corners: {home} {h_c:.1f} | {away} {a_c:.1f} | Total: {total_c:.1f}")
            st.write(f"Over 9.5 Corners: {'🔥' if over_c else '❌'}")

            st.write(handicap_suggestion(home_avg, away_avg))
            st.markdown("---")
