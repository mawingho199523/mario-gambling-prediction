import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import math
import numpy as np
import altair as alt

# ===============================
# 1. Titan007 抓取比賽資料
# ===============================
def fetch_titan007_matches(limit=50):
    url = "https://www.titan007.com/football/matchlist.htm"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        st.error(f"無法抓取 Titan007 網頁，HTTP 狀態碼: {resp.status_code}")
        return pd.DataFrame()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    data = []

    # 依照最新 Titan007 網頁結構，請修改 id/class
    table = soup.find("table", id="matchlist")
    if not table:
        st.error("找不到比賽表格，Titan007 網頁結構可能已改版")
        return pd.DataFrame()
    
    rows = table.find_all("tr")[1:]  # 跳過表頭
    for r in rows[:limit]:
        cols = r.find_all("td")
        if len(cols) >= 4:
            data.append({
                "日期": cols[0].get_text(strip=True),
                "聯賽": cols[1].get_text(strip=True),
                "主隊": cols[2].get_text(strip=True),
                "客隊": cols[3].get_text(strip=True)
            })
    
    df = pd.DataFrame(data)
    if df.empty:
        st.warning("抓到的比賽資料為空，請檢查 Titan007 網頁結構")
    return df

# ===============================
# 2. Poisson 模型
# ===============================
def poisson(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def predict_matrix(home_avg, away_avg, max_val=5):
    return np.array([[poisson(i, home_avg) * poisson(j, away_avg) for j in range(max_val+1)] for i in range(max_val+1)])

# ===============================
# 3. Streamlit UI
# ===============================
st.set_page_config(page_title="Mario Gambling Prediction 4.7", layout="wide")
st.title("⚽ Mario Gambling Prediction 4.7 ⚽")

# 抓取比賽資料
df_matches = fetch_titan007_matches(limit=50)

# 檢查聯賽欄位
if df_matches.empty or '聯賽' not in df_matches.columns:
    st.stop()

# 側邊欄選擇聯賽與比賽
st.sidebar.header("選擇聯賽 & 比賽")
leagues = df_matches['聯賽'].unique().tolist()
selected_league = st.sidebar.selectbox("選擇聯賽", leagues)

matches_in_league = df_matches[df_matches['聯賽'] == selected_league]
match_options = matches_in_league.apply(lambda x: f"{x['主隊']} vs {x['客隊']} ({x['日期']})", axis=1)
selected_match = st.sidebar.selectbox("選擇比賽", match_options)

# 模擬平均進球與角球
st.subheader("比分預測 ⚽")
home_avg = st.slider("主隊平均進球", 0.0, 5.0, 1.0, 0.1)
away_avg = st.slider("客隊平均進球", 0.0, 5.0, 1.0, 0.1)

st.subheader("角球預測 🟡")
home_corner_avg = st.slider("主隊平均角球", 0.0, 10.0, 4.0, 0.1)
away_corner_avg = st.slider("客隊平均角球", 0.0, 10.0, 4.0, 0.1)

# ===============================
# 4. 計算概率矩陣
# ===============================
score_matrix = predict_matrix(home_avg, away_avg, max_val=5)
corner_matrix = predict_matrix(home_corner_avg, away_corner_avg, max_val=10)

# ===============================
# 5. 顯示 DataFrame
# ===============================
st.write("📊 預測比分機率表")
st.dataframe(pd.DataFrame(score_matrix, index=range(6), columns=range(6)))

st.write("📊 預測角球機率表")
st.dataframe(pd.DataFrame(corner_matrix, index=range(11), columns=range(11)))

# ===============================
# 6. 大小球 & 角球建議
# ===============================
under_25_prob = score_matrix[:3,:3].sum()
over_25_prob = 1 - under_25_prob
under_95_prob = corner_matrix[:5,:5].sum()
over_95_prob = 1 - under_95_prob

col1, col2, col3, col4 = st.columns(4)
col1.metric("⚽ Under 2.5", f"{under_25_prob*100:.1f}%", f"Over: {over_25_prob*100:.1f}%")
col2.metric("🟡 Under 9.5 角球", f"{under_95_prob*100:.1f}%", f"Over: {over_95_prob*100:.1f}%")
col3.metric("主隊平均進球", f"{home_avg:.1f}")
col4.metric("客隊平均進球", f"{away_avg:.1f}")

# ===============================
# 7. 比分彩色條形圖
# ===============================
st.subheader("比分概率可視化 📈")
score_df = pd.DataFrame(score_matrix, index=[f"主{i}" for i in range(6)], columns=[f"客{j}" for j in range(6)])
score_df_long = score_df.reset_index().melt(id_vars="index")
score_df_long.columns = ["主隊進球", "客隊進球", "機率"]

chart_score = alt.Chart(score_df_long).mark_rect().encode(
    x="客隊進球:O",
    y="主隊進球:O",
    color=alt.Color("機率:Q", scale=alt.Scale(scheme='reds')),
    tooltip=["主隊進球", "客隊進球", alt.Tooltip("機率:Q", format=".2%")]
).interactive()
st.altair_chart(chart_score, use_container_width=True)

# ===============================
# 8. 角球彩色條形圖
# ===============================
st.subheader("角球概率可視化 📊")
corner_df = pd.DataFrame(corner_matrix, index=[f"主{i}" for i in range(11)], columns=[f"客{j}" for j in range(11)])
corner_df_long = corner_df.reset_index().melt(id_vars="index")
corner_df_long.columns = ["主隊角球", "客隊角球", "機率"]

chart_corner = alt.Chart(corner_df_long).mark_rect().encode(
    x="客隊角球:O",
    y="主隊角球:O",
    color=alt.Color("機率:Q", scale=alt.Scale(scheme='blues')),
    tooltip=["主隊角球", "客隊角球", alt.Tooltip("機率:Q", format=".2%")]
).interactive()
st.altair_chart(chart_corner, use_container_width=True)
