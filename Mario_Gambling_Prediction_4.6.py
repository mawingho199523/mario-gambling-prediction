import streamlit as st
import requests
from bs4 import BeautifulSoup
import math
from datetime import datetime

st.set_page_config(page_title="Mario Gambling Prediction", layout="wide")

# ====== API Keys ======
THE_ODDS_KEY = "d00b3f188b2a475a2feaf90da0be67a5"
HEADERS_ODDS = {"X-RapidAPI-Key": THE_ODDS_KEY, "X-RapidAPI-Host": "the-odds-api.p.rapidapi.com"}

# ====== Poisson 分布 ======
def poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ====== SofaScore 爬蟲: 近期進球與角球 ======
def scrape_sofascore_stats(team_name):
    url = f"https://www.sofascore.com/team/football/{team_name.replace(' ','-')}"
    r = requests.get(url)
    if r.status_code != 200:
        return None, None
    soup = BeautifulSoup(r.text, 'html.parser')
    # 最近進球
    try:
        recent_goals = [int(td.text.strip()) for td in soup.select(".FormTable td.Goals")]
        avg_goals = sum(recent_goals)/len(recent_goals) if recent_goals else 1.5
    except:
        avg_goals = 1.5
    # 最近角球
    try:
        recent_corners = [int(td.text.strip()) for td in soup.select(".FormTable td.Corners")]
        avg_corners = sum(recent_corners)/len(recent_corners) if recent_corners else 5.0
    except:
        avg_corners = 5.0
    return avg_goals, avg_corners

# ====== The Odds API: 盤口 ======
def get_odds(sport='soccer_epl', regions='uk', markets='totals,spreads,h2h'):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {"apiKey": THE_ODDS_KEY, "regions": regions, "markets": markets}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    # 將比賽依日期排序
    data_sorted = sorted(data, key=lambda x: datetime.fromisoformat(x['commence_time'].replace('Z','')))
    return data_sorted

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
def predict_corners(home_avg_corners, away_avg_corners):
    total = home_avg_corners + away_avg_corners
    over = total>9.5
    return home_avg_corners, away_avg_corners, total, over

# ====== 讓球建議 ======
def handicap_suggestion(home_avg, away_avg, handicap=0.5):
    if home_avg-handicap > away_avg:
        return "🏆 Home team can win the handicap"
    else:
        return "⚠️ Home team might lose the handicap"

# ====== Streamlit 介面 ======
st.title("⚽ Mario Gambling Prediction")

# 選聯賽
leagues = ["English Premier League"]
league_name = st.selectbox("選擇聯賽", leagues)

# 取得排序後比賽
matches = get_odds()
if not matches:
    st.warning("⚠️ 無法抓取 The Odds API 比賽資料")
else:
    st.subheader("📅 未來比賽（依日期排列）")
    for match in matches[:10]:  # 顯示前10場
        home_team = match["home_team"]
        away_team = match["away_team"]
        match_time = datetime.fromisoformat(match['commence_time'].replace('Z',''))
        st.markdown(f"### {match_time.strftime('%Y-%m-%d %H:%M')} - {home_team} 🆚 {away_team}")

        # 使用 SofaScore 抓近期進球與角球
        home_avg, home_avg_corners = scrape_sofascore_stats(home_team)
        away_avg, away_avg_corners = scrape_sofascore_stats(away_team)

        # 若抓不到資料，使用預設值
        if home_avg is None:
            home_avg = 1.5
        if away_avg is None:
            away_avg = 1.2
        if home_avg_corners is None:
            home_avg_corners = 5.5
        if away_avg_corners is None:
            away_avg_corners = 4.2

        # 比分與角球預測
        top_scores, over25, under25 = predict_score(home_avg, away_avg)
        h_c, a_c, total_c, over_c = predict_corners(home_avg_corners, away_avg_corners)

        # 顯示結果
        st.markdown("**🔝 預測前三高機率比分:**")
        for (h,a), p in top_scores:
            st.write(f"⚽ {home_team} {h}-{a} {away_team} ({p*100:.1f}%)")
        st.write(f"📈 Over 2.5: {'🔥' if over25>0.5 else '❌'} {over25*100:.1f}%")
        st.write(f"📉 Under 2.5: {'✅' if under25>0.5 else '❌'} {under25*100:.1f}%")
        st.write(handicap_suggestion(home_avg, away_avg))
        st.write(f"🥅 角球: {home_team} {h_c:.1f} | {away_team} {a_c:.1f} | Total: {total_c:.1f}")
        st.write(f"Over 9.5 角球: {'🔥' if over_c else '❌'}")

        # The Odds API 補充盤口資訊
        if match.get("bookmakers"):
            st.markdown("**🎯 盤口資訊 (The Odds API)**")
            st.json(match["bookmakers"])
        else:
            st.info("⚠️ 無法抓取盤口資料")
