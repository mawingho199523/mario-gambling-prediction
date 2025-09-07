import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import math
import requests

# ---------------- Poisson 模型 ----------------
def poisson_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def predict_score(avg_home, avg_away, max_goals=10):
    dist = {(h,a): poisson_pmf(h, avg_home)*poisson_pmf(a, avg_away)
            for h in range(max_goals+1) for a in range(max_goals+1)}
    sorted_scores = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    return sorted_scores[0][0], sorted_scores[0][0], dist

def prob_over_under(dist, line=2.5):
    over = sum(p for (h,a), p in dist.items() if h+a > line)
    under = sum(p for (h,a), p in dist.items() if h+a <= line)
    return over, under

def handicap_suggestion(home_goals, away_goals, handicap=0):
    diff = home_goals - away_goals
    if diff + handicap > 0:
        return "主隊受讓 ✅"
    elif diff + handicap < 0:
        return "客隊受讓 ✅"
    else:
        return "平手/不建議下注 ⚠️"

# ---------------- 角球預測 ----------------
def predict_corner(avg_home_corner, avg_away_corner, max_corners=15):
    dist = {(h,a): poisson_pmf(h, avg_home_corner)*poisson_pmf(a, avg_away_corner)
            for h in range(max_corners+1) for a in range(max_corners+1)}
    sorted_scores = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    return sorted_scores[0][0], sorted_scores[0][0], dist

def prob_corner_over_under(dist, line=9.5):
    over = sum(p for (h,a), p in dist.items() if h+a > line)
    under = sum(p for (h,a), p in dist.items() if h+a <= line)
    return over, under

# ---------------- Titan007 爬蟲 ----------------
def fetch_titan007_matches(limit=50):
    url = "https://www.titan007.com/football/matchlist.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    data = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = soup.find_all("tr")
        for idx, m in enumerate(matches[1:limit+1]):
            cells = m.find_all("td")
            if len(cells) >= 4:
                data.append({
                    "比賽ID": idx,
                    "日期": cells[0].text.strip(),
                    "聯賽": cells[1].text.strip(),
                    "主隊": cells[2].text.strip(),
                    "客隊": cells[3].text.strip()
                })
    return pd.DataFrame(data)

def fetch_team_recent_matches(team_name, num_matches=5):
    url = f"https://www.titan007.com/football/team/{team_name}.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    goals = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = soup.find_all("tr")
        for m in matches[1:num_matches+1]:
            cells = m.find_all("td")
            if len(cells) >= 5:
                score_text = cells[4].text.strip()
                try:
                    h, a = map(int, score_text.split(":"))
                    if team_name in cells[2].text:
                        goals.append(h)
                    else:
                        goals.append(a)
                except:
                    continue
    return sum(goals)/len(goals) if goals else 1.0

def fetch_team_recent_corners(team_name, num_matches=5):
    url = f"https://www.titan007.com/football/team/{team_name}.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    corners = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = soup.find_all("tr")
        for m in matches[1:num_matches+1]:
            cells = m.find_all("td")
            if len(cells) >= 7:  # 假設角球在第6、7列
                try:
                    h, a = map(int, cells[5].text.strip().split(":"))
                    corners.append((h, a))
                except:
                    continue
    avg_home_corner = sum(h for h,_ in corners)/len(corners) if corners else 4
    avg_away_corner = sum(a for _,a in corners)/len(corners) if corners else 4
    return avg_home_corner, avg_away_corner

def fetch_h2h(team_home, team_away, num_matches=5):
    url = f"https://www.titan007.com/football/h2h/{team_home}_vs_{team_away}.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    home_goals, away_goals = [], []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = soup.find_all("tr")
        for m in matches[1:num_matches+1]:
            cells = m.find_all("td")
            if len(cells) >= 5:
                score_text = cells[4].text.strip()
                try:
                    h, a = map(int, score_text.split(":"))
                    home_goals.append(h)
                    away_goals.append(a)
                except:
                    continue
    avg_home = sum(home_goals)/len(home_goals) if home_goals else 1.0
    avg_away = sum(away_goals)/len(away_goals) if away_goals else 1.0
    return avg_home, avg_away

# ---------------- 異步抓取 Titan007 即時盤 ----------------
async def fetch_odds_async(session, match_id):
    url = f"https://www.titan007.com/football/odds/{match_id}.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            soup = BeautifulSoup(text, "html.parser")
            over_under = float(soup.select_one(".over-under").text or 2.5)
            ou_home = float(soup.select_one(".ou-home").text or 1)
            ou_away = float(soup.select_one(".ou-away").text or 1)
            handicap_home = float(soup.select_one(".handicap-home").text or 0)
            handicap_away = float(soup.select_one(".handicap-away").text or 0)
            return match_id, {"over_under": over_under, "ou_home": ou_home, "ou_away": ou_away,
                              "handicap_home": handicap_home, "handicap_away": handicap_away}
    except:
        return match_id, {"over_under":2.5,"ou_home":1,"ou_away":1,"handicap_home":0,"handicap_away":0}

async def fetch_all_odds(match_ids):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_odds_async(session, mid) for mid in match_ids]
        results = await asyncio.gather(*tasks)
        return dict(results)

# ---------------- Streamlit 介面 ----------------
st.set_page_config(page_title="Mario 赌博预测 4.6", layout="wide")
st.title("⚽🎯 Mario 赌博预测 4.6（全中文 + Titan007 異步即時盤 + 角球預測）")

# 1️⃣ 比賽列表
df_matches = fetch_titan007_matches()
st.subheader("📌 Titan007 比賽列表")
st.dataframe(df_matches)

# 2️⃣ 聯賽選擇
leagues = df_matches['聯賽'].unique().tolist()
selected_league = st.selectbox("選擇聯賽", leagues)
league_matches = df_matches[df_matches['聯賽']==selected_league]

# 3️⃣ 批量比分與角球預測
if not league_matches.empty:
    st.subheader("📊 比賽預測（多場）")
    predictions = []

    # 異步抓取即時盤
    match_ids = league_matches['比賽ID'].tolist()
    odds_data = asyncio.run(fetch_all_odds(match_ids))

    for idx, row in league_matches.iterrows():
        recent_home = fetch_team_recent_matches(row['主隊'])
        recent_away = fetch_team_recent_matches(row['客隊'])
        avg_home_corner, avg_away_corner = fetch_team_recent_corners(row['主隊']), fetch_team_recent_corners(row['客隊'])
        h2h_home, h2h_away = fetch_h2h(row['主隊'], row['客隊'])
        avg_home = (recent_home + h2h_home)/2
        avg_away = (recent_away + h2h_away)/2

        # 比分
        pred_home, pred_away, dist = predict_score(avg_home, avg_away)
        over_prob, under_prob = prob_over_under(dist)

        # 角球
        corner_pred_home, corner_pred_away, corner_dist = predict_corner(avg_home_corner, avg_away_corner)
        corner_over_prob, corner_under_prob = prob_corner_over_under(corner_dist)

        odds = odds_data.get(row['比賽ID'], {})
        advice = handicap_suggestion(pred_home, pred_away, handicap=0)

        # Emoji 標記
        score_emoji = "⚡"
        over_emoji = "📈" if over_prob > 0.6 else ""
        under_emoji = "📉" if under_prob > 0.6 else ""
        corner_over_emoji = "📈" if corner_over_prob > 0.6 else ""
        corner_under_emoji = "📉" if corner_under_prob > 0.6 else ""
        advice_emoji = "🏆" if "✅" in advice else ""

        predictions.append({
            "日期": row['日期'],
            "主隊": row['主隊'],
            "客隊": row['客隊'],
            "預測比分": f"{pred_home}-{pred_away} {score_emoji}",
            "大於 2.5 機率": f"{over_prob:.1%} {over_emoji}",
            "小於 2.5 機率": f"{under_prob:.1%} {under_emoji}",
            "讓球盤建議": f"{advice} {advice_emoji}",
            "大小球即時盤": f"{odds.get('ou_home', '-')}/{odds.get('ou_away', '-')}",
            "讓球盤即時盤": f"{odds.get('handicap_home', '-')}/{odds.get('handicap_away', '-')}",
            "預測角球比分": f"{corner_pred_home}-{corner_pred_away}",
            "角球大於 9.5 機率": f"{corner_over_prob:.1%} {corner_over_emoji}",
            "角球小於 9.5 機率": f"{corner_under_prob:.1%} {corner_under_emoji}"
        })

    df_pred = pd.DataFrame(predictions)
    st.dataframe(df_pred)