import streamlit as st
import requests
import math

# ================= 中文聯賽 + 中文球隊 =================
leagues = {
    "英超": {"曼城": 65, "曼聯": 66, "利物浦": 64, "切爾西": 61, "阿森納": 57, "熱刺": 62},
    "西甲": {"皇家馬德里": 86, "巴塞羅那": 81, "馬德里競技": 78, "塞維利亞": 80},
    "日職聯": {"鹿島鹿角": 85, "川崎前鋒": 79, "浦和紅鑽": 84}
    # 可繼續加入其他聯賽
}

API_FOOTBALL_KEY = "085d2ce7d7e11f743f93f6cf6d5ba7e8"

# ================= Poisson 分布 =================
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ================= API-Football 獲取球隊平均進球 & 角球 & H2H =================
def get_team_stats(team_id):
    url = f"https://v3.football.api-sports.io/teams/statistics?team={team_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        home_fixtures = data["response"]["fixtures"]["played"]["home"]
        goals_for = home_fixtures["goals"]["for"]["total"]
        goals_against = home_fixtures["goals"]["against"]["total"]
        corners_for = home_fixtures["corners"]["for"]["total"]
        matches = home_fixtures["total"]
        if matches > 0:
            avg_scored = goals_for / matches
            avg_conceded = goals_against / matches
            avg_corners_for = corners_for / matches
            return avg_scored, avg_conceded, avg_corners_for
    except:
        return None
    return None

def get_h2h_stats(home_id, away_id):
    url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        h2h = data["response"]
        if len(h2h) == 0:
            return None
        home_goals = sum(match["score"]["fulltime"]["home"] for match in h2h)
        away_goals = sum(match["score"]["fulltime"]["away"] for match in h2h)
        matches = len(h2h)
        if matches > 0:
            return home_goals / matches, away_goals / matches
    except:
        return None
    return None

def get_fixture_datetime(home_id, away_id):
    url = f"https://v3.football.api-sports.io/fixtures?team={home_id}&next=5"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    fixtures = data.get("response", [])
    for match in fixtures:
        teams = match["teams"]
        if teams["home"]["id"] == home_id and teams["away"]["id"] == away_id:
            dt = match["fixture"]["date"]
            return dt
    return None

# ================= 比分預測 =================
def predict_match(home_avg, away_avg):
    score_probs = {}
    for h in range(0, 5):
        for a in range(0, 5):
            p = poisson(home_avg, h) * poisson(away_avg, a)
            score_probs[(h, a)] = p
    top_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:3]
    over25 = sum(p for (h, a), p in score_probs.items() if h + a > 2.5)
    under25 = 1 - over25
    return top_scores, over25, under25

def handicap_suggestion(home_avg, away_avg, handicap=0.5):
    home_net = home_avg - handicap
    if home_net > away_avg:
        return "🏆 主隊受讓盤可贏"
    else:
        return "⚠️ 主隊受讓盤可能輸"

def corner_predict(home_corners, away_corners):
    total = home_corners + away_corners
    over = total > 9.5
    return home_corners, away_corners, total, over

# ================= Streamlit App =================
st.title("⚽ Mario Gambling Prediction (全聯賽一覽 + Emoji + 角球 + 日期)")

for league_name, teams in leagues.items():
    st.header(f"🏟️ {league_name}")
    team_list = list(teams.keys())
    for i in range(len(team_list)):
        for j in range(i+1, len(team_list)):
            home_name = team_list[i]
            away_name = team_list[j]
            home_id = leagues[league_name][home_name]
            away_id = leagues[league_name][away_name]

            fixture_dt = get_fixture_datetime(home_id, away_id)
            home_stats = get_team_stats(home_id)
            away_stats = get_team_stats(away_id)
            h2h_stats = get_h2h_stats(home_id, away_id)

            if home_stats and away_stats:
                home_avg, _, home_corners = home_stats
                away_avg, _, away_corners = away_stats
                if h2h_stats:
                    h2h_home, h2h_away = h2h_stats
                    home_avg = home_avg*0.7 + h2h_home*0.3
                    away_avg = away_avg*0.7 + h2h_away*0.3

                scores, over25, under25 = predict_match(home_avg, away_avg)
                h_c, a_c, total_c, over_c = corner_predict(home_corners, away_corners)
                st.subheader(f"{home_name} 🆚 {away_name}")
                if fixture_dt:
                    st.info(f"🗓️ 比賽日期: {fixture_dt}")

                # 比分 Top3 + Emoji
                for (h, a), p in scores:
                    st.write(f"⚽ {home_name} {h} - {a} {away_name} ({p*100:.1f}%)")
                st.write(f"📈 大於2.5球: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
                st.write(f"📉 小於2.5球: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")

                # 讓球盤 + Emoji
                st.write(handicap_suggestion(home_avg, away_avg))

                # 角球 + Emoji
                st.write(f"🥅 角球: {home_name} {h_c:.1f} | {away_name} {a_c:.1f} | 總: {total_c:.1f}")
                st.write(f"大於9.5角球: {'🔥' if over_c else '❌'}")
            else:
                st.warning(f"❌ 無法抓取 {home_name} vs {away_name} 的數據")
