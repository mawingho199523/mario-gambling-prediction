import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import math

# ---------- Poisson 模型 ----------
def poisson_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def predict_score(avg_home, avg_away, max_goals=10):
    dist = {(h,a): poisson_pmf(h, avg_home)*poisson_pmf(a, avg_away)
            for h in range(max_goals+1) for a in range(max_goals+1)}
    sorted_scores = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    return sorted_scores[0][0], dist

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

# ---------- Titan007 資料 ----------
def fetch_titan007_matches():
    url = "https://www.titan007.com/football/matchlist.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    data = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = soup.find_all("tr")
        for m in matches[1:50]:
            cells = m.find_all("td")
            if len(cells) >= 4:
                data.append({
                    "日期": cells[0].text.strip(),
                    "聯賽": cells[1].text.strip(),
                    "主隊": cells[2].text.strip(),
                    "客隊": cells[3].text.strip()
                })
    return pd.DataFrame(data)

def fetch_team_recent_matches(team_name, num_matches=5):
    """
    取得球隊近期平均進球
    """
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
                score_text = cells[4].text.strip()  # 假設比分在第5欄 "2:1"
                try:
                    h, a = map(int, score_text.split(":"))
                    if team_name in cells[2].text:
                        goals.append(h)
                    else:
                        goals.append(a)
                except:
                    continue
    return sum(goals)/len(goals) if goals else 1.0

def fetch_h2h(team_home, team_away, num_matches=5):
    """
    取得兩隊 H2H 平均進球
    """
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

# ---------- Streamlit 介面 ----------
st.set_page_config(page_title="Mario Gambling Prediction 3.0", layout="wide")
st.title("⚽🎯 Mario Gambling Prediction 3.0 (Titan007 + 歷史數據)")

df_matches = fetch_titan007_matches()
st.subheader("📌 Titan007 比賽資料")
st.dataframe(df_matches)

# 選擇聯賽
leagues = df_matches['聯賽'].unique().tolist()
selected_league = st.selectbox("選擇聯賽", leagues)
league_matches = df_matches[df_matches['聯賽']==selected_league]

if not league_matches.empty:
    st.subheader("📊 比賽預測（多場）")
    predictions = []
    for idx, row in league_matches.iterrows():
        # 歷史數據計算平均進球
        recent_home = fetch_team_recent_matches(row['主隊'])
        recent_away = fetch_team_recent_matches(row['客隊'])
        h2h_home, h2h_away = fetch_h2h(row['主隊'], row['客隊'])
        avg_home = (recent_home + h2h_home)/2
        avg_away = (recent_away + h2h_away)/2

        # 預測比分
        pred_home, pred_away, dist = predict_score(avg_home, avg_away)
        over_prob, under_prob = prob_over_under(dist)
        advice = handicap_suggestion(pred_home, pred_away)

        predictions.append({
            "日期": row['日期'],
            "主隊": row['主隊'],
            "客隊": row['客隊'],
            "預測比分": f"{pred_home}-{pred_away}",
            "Over 2.5": f"{over_prob:.1%}",
            "Under 2.5": f"{under_prob:.1%}",
            "讓球盤建議": advice
        })
    df_pred = pd.DataFrame(predictions)
    st.dataframe(df_pred)
