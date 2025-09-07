# Mario_Gambling_Prediction_with_Handicap.py
import streamlit as st
import requests
import pandas as pd
import numpy as np
import math
from datetime import datetime
from statistics import mean

# -------------------------
# CONFIG - put your keys here or use st.secrets
# -------------------------
ODDS_API_KEY = st.secrets.get("ODDS_API_KEY", "d00b3f188b2a475a2feaf90da0be67a5")  # The Odds API
FD_API_KEY   = st.secrets.get("FD_API_KEY", "f3e294cb8cab4e80ae92c3471d8c2315")      # Football-Data.org (optional)
# -------------------------

st.set_page_config(page_title="Mario Gambling Prediction + Handicap", layout="wide")
st.title("⚽ Mario Gambling Prediction — 加入讓球盤 (Handicap) 預測")

# -------------------------
# Utilities: Poisson & helpers
# -------------------------
def poisson_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def build_score_matrix(home_lambda, away_lambda, max_goals=6):
    m = np.zeros((max_goals+1, max_goals+1))
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            m[h,a] = poisson_pmf(h, home_lambda) * poisson_pmf(a, away_lambda)
    return m

def prob_over_under(matrix, line=2.5):
    over = 0.0
    for h in range(matrix.shape[0]):
        for a in range(matrix.shape[1]):
            if h + a > line:
                over += matrix[h,a]
    return over, 1-over

def prob_match_outcomes(matrix):
    # home win = sum of entries where h>a; draw where h==a; away where h<a
    home = matrix[np.triu_indices_from(matrix, k=1)].sum()
    away = matrix[np.tril_indices_from(matrix, k=-1)].sum()
    draw = 1 - home - away
    return home, draw, away

def prob_handicap_cover(matrix, handicap):
    """
    計算「主隊覆蓋 handicap」的機率。
    Interpret: handicap is numeric (e.g. -0.5, -1, -1.5). For typical asian handicap
    - If handicap = -0.5: 主隊需淨勝 >=1 to cover.
    - If handicap = -1.0: 主隊需淨勝 >=2 to cover; 若淨勝=1則 push (半退) -> treat push as 0.5? We'll treat push separately.
    We'll return tuple (p_home_cover, p_home_push, p_away_cover)
    """
    p_home_cover = 0.0
    p_home_push = 0.0
    p_away_cover = 0.0
    for h in range(matrix.shape[0]):
        for a in range(matrix.shape[1]):
            p = matrix[h,a]
            diff = h - a
            # For push detection when handicap is integer (e.g., -1.0)
            if abs(handicap - round(handicap)) < 1e-8:
                int_hand = int(round(handicap))
                # e.g. handicap=-1 -> home needs diff > 1 to win cover; diff==1 => push
                if diff > -int_hand:
                    p_home_cover += p
                elif diff == -int_hand:
                    p_home_push += p
                else:
                    p_away_cover += p
            else:
                # non-integer like -0.5, -1.5: compare diff > -handicap
                if diff > handicap:
                    p_home_cover += p
                else:
                    p_away_cover += p
    return p_home_cover, p_home_push, p_away_cover

# -------------------------
# The Odds API helpers (simple)
# -------------------------
def fetch_matches_from_odds(sport_key="soccer_epl", regions="eu", markets="h2h,totals,spreads"):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": regions, "markets": markets, "oddsFormat":"decimal"}
    try:
        r = requests.get(url, params=params, timeout=20)
    except Exception as e:
        st.error(f"網路或請求錯誤: {e}")
        return []
    if r.status_code != 200:
        st.error(f"The Odds API 回傳 {r.status_code}")
        return []
    return r.json()

def extract_match_bookmakers(match_json):
    """Extract a normalized structure for totals/spreads/h2h (avg prices) from match JSON"""
    res = {"totals": None, "spreads": [], "h2h": None}
    bms = match_json.get("bookmakers", []) or []
    # collect totals candidates
    totals_over = []
    totals_under = []
    totals_points = []
    spreads_map = {}
    h2h_home = []
    h2h_draw = []
    h2h_away = []
    for bm in bms:
        for market in bm.get("markets", []):
            key = market.get("key","").lower()
            if key == "totals" or "total" in key:
                for o in market.get("outcomes", []):
                    name = (o.get("name") or "").lower()
                    price = o.get("price")
                    point = o.get("point", None)
                    if "over" in name:
                        totals_over.append((point, price))
                    elif "under" in name:
                        totals_under.append((point, price))
            elif key == "spreads" or "spread" in key:
                for o in market.get("outcomes", []):
                    pt = o.get("point")
                    name = (o.get("name") or "").lower()
                    price = o.get("price")
                    if pt is None:
                        continue
                    # classify home/away by name
                    if pt not in spreads_map:
                        spreads_map[pt] = {"home": [], "away": []}
                    if "home" in name:
                        spreads_map[pt]["home"].append(price)
                    else:
                        spreads_map[pt]["away"].append(price)
            elif key == "h2h" or "moneyline" in key:
                for o in market.get("outcomes", []):
                    n = (o.get("name") or "").lower()
                    price = o.get("price")
                    if "home" in n:
                        h2h_home.append(price)
                    elif "draw" in n:
                        h2h_draw.append(price)
                    elif "away" in n:
                        h2h_away.append(price)
    # process totals - pick nearest to 2.5 if possible
    def pick_totals(over_list, under_list, target=2.5):
        lines = set([p for p,_ in over_list if p is not None]) & set([p for p,_ in under_list if p is not None])
        if not lines:
            # fallback: pick closest points from both lists if exist
            if over_list and under_list:
                ov = min(over_list, key=lambda x: abs((x[0] or target)-target))[0]
                un = min(under_list, key=lambda x: abs((x[0] or target)-target))[0]
                if ov == un:
                    lines = {ov}
        if lines:
            ln = min(lines, key=lambda x: abs(x-target))
            over_prices = [p for pt,p in over_list if pt==ln and p]
            under_prices = [p for pt,p in under_list if pt==ln and p]
            if over_prices and under_prices:
                o_avg = mean(over_prices)
                u_avg = mean(under_prices)
                # implied probs (then normalize)
                po = 1.0/o_avg
                pu = 1.0/u_avg
                s = po + pu
                return {"line": ln, "over_odds":o_avg, "under_odds":u_avg, "over_prob":po/s, "under_prob":pu/s}
        return None
    totals = pick_totals(totals_over, totals_under, target=2.5)
    res["totals"] = totals
    # spreads
    spreads = []
    for pt, sides in spreads_map.items():
        hs = [p for p in sides["home"] if p]
        as_ = [p for p in sides["away"] if p]
        if hs and as_:
            h_avg = mean(hs)
            a_avg = mean(as_)
            ph = 1.0/h_avg
            pa = 1.0/a_avg
            s = ph + pa
            spreads.append({"point":pt, "home_odds":h_avg, "away_odds":a_avg, "home_prob":ph/s, "away_prob":pa/s})
    res["spreads"] = spreads
    # h2h
    if h2h_home and (h2h_away or h2h_draw):
        home_avg = mean(h2h_home) if h2h_home else None
        draw_avg = mean(h2h_draw) if h2h_draw else None
        away_avg = mean(h2h_away) if h2h_away else None
        probs = [1.0/home_avg if home_avg else 0, 1.0/draw_avg if draw_avg else 0, 1.0/away_avg if away_avg else 0]
        # normalize
        s = sum(probs) if sum(probs)>0 else 1
        res["h2h"] = {"home_odds":home_avg, "draw_odds":draw_avg, "away_odds":away_avg, "home_prob":probs[0]/s, "draw_prob":probs[1]/s, "away_prob":probs[2]/s}
    else:
        res["h2h"] = None
    return res

# -------------------------
# Simple Sofascore corner crawler (best-effort)
# -------------------------
def get_team_corners_sofascore(team_id, limit=5):
    """Use Sofascore public API endpoints (best-effort). Returns tuple (avg_home_corners, avg_away_corners) as floats or None."""
    headers = {"User-Agent":"Mozilla/5.0"}
    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/0"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json().get("events", [])[:limit]
        home_corners = []
        away_corners = []
        for e in data:
            mid = e.get("id")
            try:
                stats_url = f"https://api.sofascore.com/api/v1/event/{mid}/statistics"
                rs = requests.get(stats_url, headers=headers, timeout=15)
                if rs.status_code != 200:
                    continue
                stats = rs.json().get("statistics", [])
                for grp in stats:
                    for itm in grp.get("statisticsItems", []):
                        if itm.get("name") == "Corner kicks":
                            hc = itm.get("home", 0) or 0
                            ac = itm.get("away", 0) or 0
                            home_corners.append(hc)
                            away_corners.append(ac)
            except:
                continue
        if home_corners and away_corners:
            return float(np.mean(home_corners)), float(np.mean(away_corners))
    except Exception:
        return None
    return None

# -------------------------
# APP UI
# -------------------------
st.markdown("### 1) 抓取比賽 (The Odds API)")
sport_key = st.selectbox("選擇 sport_key (The Odds API)", ["soccer_epl","soccer_spain_la_liga","soccer_italy_serie_a","soccer_germany_bundesliga"])
with st.spinner("抓取中..."):
    matches = fetch_matches_from_odds(sport_key)
if not matches:
    st.stop()

# show matches table
rows = []
for m in matches:
    ct = m.get("commence_time")
    try:
        dt = datetime.fromisoformat(ct.replace("Z","+00:00"))
        dtstr = dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        dtstr = ct or ""
    rows.append({"home":m.get("home_team"), "away":m.get("away_team"), "time":dtstr, "raw":m})
df = pd.DataFrame(rows)
st.dataframe(df[["time","home","away"]].reset_index())

idx = st.number_input("選擇比賽 index", min_value=0, max_value=max(0,len(df)-1), value=0, step=1)
selected = df.iloc[idx]

st.markdown(f"## 選擇：**{selected['home']}** vs **{selected['away']}** ({selected['time']})")

# extract bookmaker aggregated info
odds_info = extract_match_bookmakers(selected["raw"])
st.subheader("莊家盤口（若有則顯示）")
st.write(odds_info)

# -------------------------
# get or input recent attack/defense means
# -------------------------
st.subheader("球隊近況 (進球/失球) - 若可用則自動填，否則手動")
# attempt to auto-fill from Football-Data if available (light attempt skipped for brevity)
# fallback manual sliders
home_attack = st.slider(f"{selected['home']} 近期平均進球 (攻)", 0.0, 3.5, 1.2, 0.05)
home_defense = st.slider(f"{selected['home']} 近期平均失球 (防)", 0.0, 3.5, 1.1, 0.05)
away_attack = st.slider(f"{selected['away']} 近期平均進球 (攻)", 0.0, 3.5, 1.0, 0.05)
away_defense = st.slider(f"{selected['away']} 近期平均失球 (防)", 0.0, 3.5, 1.3, 0.05)
# optional odds influence factor
odds_influence = st.slider("賠率調整強度 (1 = 中性，>1 提升主隊預期)", 0.8, 1.4, 1.0, 0.05)

# compute expected lambdas
home_lambda = (home_attack + away_defense) / 2 * odds_influence
away_lambda = (away_attack + home_defense) / 2 * (2 - odds_influence)

# build matrix
max_g = st.slider("最大模擬進球數 (矩陣大小)", 4, 8, 6, 1)
matrix = build_score_matrix(home_lambda, away_lambda, max_goals=max_g)

st.subheader("Poisson 預測比分矩陣 (0..{})".format(max_g))
st.dataframe(pd.DataFrame(matrix, index=[f"H{h}" for h in range(max_g+1)], columns=[f"A{a}" for a in range(max_g+1)]))

# Match outcome & O/U
p_home, p_draw, p_away = prob_match_outcomes(matrix)
st.metric("Poisson 獨贏 (主 / 和 / 客)", f"{p_home*100:.1f}% / {p_draw*100:.1f}% / {p_away*100:.1f}%")
po_over, po_under = prob_over_under(matrix, line=2.5)
st.metric("Poisson Over2.5 / Under2.5", f"{po_over*100:.1f}% / {po_under*100:.1f}%")

# -------------------------
# Handicap calculations (multiple typical lines)
# -------------------------
st.subheader("讓球 (Handicap) 預測 & 與莊家比較")
handicap_lines = [-0.5, -1.0, -1.5]
for h in handicap_lines:
    ph_cover, ph_push, pa_cover = prob_handicap_cover(matrix, handicap=h)
    display = f"主隊覆蓋 {ph_cover*100:.1f}%"
    if ph_push>0:
        display += f", push {ph_push*100:.1f}%"
    display += f"; 客隊覆蓋 {pa_cover*100:.1f}%"
    st.write(f"Handicap {h}: {display}")

# compare with bookmaker spreads if exist
if odds_info and odds_info.get("spreads"):
    st.write("莊家讓球盤 (平均) 與模型比較：")
    for s in odds_info["spreads"]:
        pt = s["point"]
        b_home_prob = s.get("home_prob")
        b_away_prob = s.get("away_prob")
        m_home_cover, m_push, m_away_cover = prob_handicap_cover(matrix, handicap=pt)
        st.write(f"莊家 point {pt}: book home_prob {b_home_prob:.2%}, away_prob {b_away_prob:.2%}")
        st.write(f"模型 cover 主 {m_home_cover:.2%}, push {m_push:.2%}, 客 cover {m_away_cover:.2%}")
        diff = m_home_cover - b_home_prob
        if diff > 0.10:
            st.warning(f"模型比莊家高 {diff*100:.1f}% → 模型偏向主隊覆蓋（下注提醒）")
        elif diff < -0.10:
            st.warning(f"模型比莊家低 {abs(diff)*100:.1f}% → 莊家偏向主隊覆蓋")
        else:
            st.info(f"模型與莊家差異 {diff*100:.1f}% (無明顯套利)")

else:
    st.info("此場賽事未提供 bookmaker spreads 資訊 (或未被抓到)。")

# -------------------------
# Corner integration (Sofascore best-effort)
# -------------------------
st.subheader("角球預測（Sofascore 或手動 fallback）")
use_sofa = st.checkbox("使用 Sofascore 自動抓角球 (需輸入 team id)", value=False)
home_corners_mean = None
away_corners_mean = None
if use_sofa:
    h_id = st.text_input(f"{selected['home']} Sofascore team id (例如 17)")
    a_id = st.text_input(f"{selected['away']} Sofascore team id")
    if h_id and a_id:
        try:
            hc = get_team_corners_sofascore(int(h_id))
            ac = get_team_corners_sofascore(int(a_id))
            if hc:
                home_corners_mean = hc[0]
            if ac:
                away_corners_mean = ac[1]
            st.write("Sofascore results:", hc, ac)
        except Exception as e:
            st.warning("抓取 Sofascore 失敗，請確認 team id 或網路。")
if home_corners_mean is None:
    home_corners_mean = st.slider(f"{selected['home']} 角球平均 (若無 API 則手動)", 2.0, 10.0, 5.0, 0.1)
if away_corners_mean is None:
    away_corners_mean = st.slider(f"{selected['away']} 角球平均 (若無 API 則手動)", 2.0, 10.0, 4.5, 0.1)

corner_matrix = build_score_matrix(home_corners_mean, away_corners_mean, max_goals=12)
# Poisson over/under 9.5
over_c, under_c = 0.0, 0.0
for i in range(corner_matrix.shape[0]):
    for j in range(corner_matrix.shape[1]):
        if i + j > 9.5:
            over_c += corner_matrix[i,j]
        else:
            under_c += corner_matrix[i,j]
st.metric("角球 Over 9.5", f"{over_c*100:.1f}%", f"Under: {under_c*100:.1f}%")

st.markdown("---")
st.caption("說明：本模型為簡化 Poisson 實作，讓球 push 邏輯以簡化方式處理。若要更精細請加上主客場係數、近期表現權重、受傷與輪換等。")
