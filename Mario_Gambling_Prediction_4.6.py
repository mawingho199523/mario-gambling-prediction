# Mario_Gambling_Prediction_plus.py
# 完整版：The Odds API + Football-Data.org + Poisson 模型 + Streamlit UI
# 請先在 requirements.txt 放：
# streamlit pandas requests numpy altair

import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
import altair as alt
from datetime import datetime
from statistics import mean

# =========================
#  User-provided API keys
# =========================
ODDS_API_KEY = "d00b3f188b2a475a2feaf90da0be67a5"   # The Odds API
FD_API_KEY   = "f3e294cb8cab4e80ae92c3471d8c2315"   # Football-Data.org

# =========================
#  Config: 聯賽對照（中文顯示 -> The Odds sport_key, Football-Data competition id）
#  如果你要更多聯賽，請在此加入對應
# =========================
LEAGUE_MAP = {
    "英超": {"odds_key": "soccer_epl", "fd_comp": 2021},
    "西甲": {"odds_key": "soccer_spain_la_liga", "fd_comp": 2014},
    "意甲": {"odds_key": "soccer_italy_serie_a", "fd_comp": 2019},
    "德甲": {"odds_key": "soccer_germany_bundesliga", "fd_comp": 2002},
    "法甲": {"odds_key": "soccer_france_ligue_one", "fd_comp": 2015},
    # 可自行擴充...
}

# =========================
# Utility functions
# =========================
def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def implied_prob_from_decimal(odd):
    """decimal odd -> implied probability"""
    try:
        return 1.0 / float(odd)
    except Exception:
        return None

def normalize_probs(probs):
    """移除水位 (vig) 後 normalize 成為總和 1"""
    s = sum(probs)
    if s == 0:
        return probs
    return [p / s for p in probs]

# =========================
#  The Odds API: 抓比賽和盤口
# =========================
def fetch_odds_matches(sport_key, regions="eu", markets="h2h,totals,spreads", oddsFormat="decimal"):
    """
    抓取 The Odds API 的比賽與盤口
    返回 list of match dict，包含:
      - id, commence_time, home_team, away_team, bookmakers (原始)
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": oddsFormat,
    }
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        st.error(f"The Odds API 比賽請求失敗: {resp.status_code}")
        return []
    data = safe_json(resp)
    if not data:
        return []
    return data

def extract_average_market_odds(match_json):
    """
    從一場 match 的 JSON 抽取三種盤口平均賠率：
      - totals: 找到 Over/Under 2.5 的平均賠率 (over/under)
      - spreads: 讓球盤（bookmakers -> markets -> outcomes 有 point / price）
      - h2h: 獨贏賠率（home/draw/away）
    回傳 dict:
      {
        'totals': {'line': 2.5, 'over_odds': X, 'under_odds': Y, 'over_prob': P, 'under_prob': Q},
        'spreads': [{'point': -1.5, 'home_odds':a, 'away_odds':b, 'home_prob':p, 'away_prob':q}, ...],
        'h2h': {'home_odds':h_odd, 'draw_odds':d_odd, 'away_odds':a_odd, 'home_prob':p, 'draw_prob':q, 'away_prob':r}
      }
    注意：The Odds API 各 bookmaker 回傳格式可能不同，這個函式會盡量以常見 pattern 抽取。
    """
    result = {"totals": None, "spreads": [], "h2h": None}
    bookmakers = match_json.get("bookmakers", []) or []
    # collect lists per market
    totals_over_odds = []
    totals_under_odds = []
    totals_lines = []
    spreads_by_point = {}  # point -> list of (home_odds, away_odds)
    h2h_home = []
    h2h_draw = []
    h2h_away = []

    for bm in bookmakers:
        for market in bm.get("markets", []):
            mkey = market.get("key") or market.get("market_key") or market.get("name","").lower()
            outcomes = market.get("outcomes") or []
            # totals (大小球)
            if "total" in (mkey or "") or "totals" in (mkey or "") or (market.get("key")=="totals"):
                # outcomes usually contain 'Over X' and 'Under X' or names 'over','under' with 'point'
                for o in outcomes:
                    name = (o.get("name") or "").lower()
                    price = o.get("price")
                    point = o.get("point", None) or o.get("total", None)
                    try:
                        point = float(point) if point is not None else None
                    except:
                        point = None
                    if "over" in name:
                        if price: totals_over_odds.append((point, price))
                    elif "under" in name:
                        if price: totals_under_odds.append((point, price))
                    else:
                        # sometimes outcomes are like {'label':'Over/Under 2.5', ...}
                        pass
            # spreads (讓球)
            elif "spreads" in (mkey or "") or market.get("key")=="spreads":
                for o in outcomes:
                    point = o.get("point", None)
                    price = o.get("price", None)
                    # outcome name could indicate home/away
                    # Some APIs include 'side' or 'name' as "Home" / "Away"
                    side = (o.get("name") or "").lower()
                    if point is None:
                        try:
                            point = float(o.get("handicap", None))
                        except:
                            point = None
                    if point is None:
                        continue
                    if point not in spreads_by_point:
                        spreads_by_point[point] = {"home": [], "away": []}
                    if "home" in side or "home" in o.get("side","").lower():
                        spreads_by_point[point]["home"].append(price)
                    else:
                        spreads_by_point[point]["away"].append(price)
            # h2h (獨贏)
            elif "h2h" in (mkey or "") or market.get("key")=="h2h":
                # outcomes often: [{"name": "Home", "price": 1.5}, {"name":"Draw","price":3.2}, {"name":"Away","price":6.0}]
                for o in outcomes:
                    name = (o.get("name") or "").lower()
                    price = o.get("price", None)
                    if "home" in name:
                        if price: h2h_home.append(price)
                    elif "draw" in name:
                        if price: h2h_draw.append(price)
                    elif "away" in name:
                        if price: h2h_away.append(price)

    # process totals: pick lines that both over & under share (use point closests to 2.5 if multiple)
    def pick_totals(over_list, under_list, target_line=2.5):
        # over_list: [(point, price), ...]
        # find entries with same point in both lists
        lines = set(p for p,_ in over_list if p is not None) & set(p for p,_ in under_list if p is not None)
        if not lines:
            # fallback: pick entries closest to target_line by absolute diff
            if over_list and under_list:
                over_point = min(over_list, key=lambda x: abs((x[0] or target_line)-target_line))[0]
                under_point = min(under_list, key=lambda x: abs((x[0] or target_line)-target_line))[0]
                if over_point==under_point:
                    lines = {over_point}
        if lines:
            # pick line closest to target_line
            ln = min(lines, key=lambda x: abs(x - target_line))
            over_prices = [p for pt,p in over_list if pt==ln and p]
            under_prices = [p for pt,p in under_list if pt==ln and p]
            if over_prices and under_prices:
                avg_over = mean(over_prices)
                avg_under = mean(under_prices)
                return {"line": float(ln), "over_odds": avg_over, "under_odds": avg_under,
                        "over_prob": implied_prob_from_decimal(avg_over), "under_prob": implied_prob_from_decimal(avg_under)}
        return None

    totals = pick_totals(totals_over_odds, totals_under_odds, target_line=2.5)
    result['totals'] = totals

    # process spreads
    spreads = []
    for point, sides in spreads_by_point.items():
        home_prices = [p for p in sides.get("home",[]) if p]
        away_prices = [p for p in sides.get("away",[]) if p]
        if home_prices and away_prices:
            h_avg = mean(home_prices)
            a_avg = mean(away_prices)
            spreads.append({
                "point": float(point),
                "home_odds": h_avg,
                "away_odds": a_avg,
                "home_prob": implied_prob_from_decimal(h_avg),
                "away_prob": implied_prob_from_decimal(a_avg)
            })
    result['spreads'] = spreads

    # process h2h
    h2h = None
    if h2h_home and h2h_away:
        # draw may be empty in some markets
        home_avg = mean(h2h_home) if h2h_home else None
        draw_avg = mean(h2h_draw) if h2h_draw else None
        away_avg = mean(h2h_away) if h2h_away else None
        probs = []
        for p in (home_avg, draw_avg, away_avg):
            probs.append(implied_prob_from_decimal(p) if p else 0)
        # normalize to remove vig
        normalized = normalize_probs(probs)
        h2h = {
            "home_odds": home_avg,
            "draw_odds": draw_avg,
            "away_odds": away_avg,
            "home_prob": normalized[0],
            "draw_prob": normalized[1],
            "away_prob": normalized[2],
        }
    result['h2h'] = h2h

    return result

# =========================
#  Football-Data.org helper: find team id by name & get recent matches
# =========================
def find_fd_team_id_by_name(team_name):
    """
    嘗試使用 football-data.org 的 /teams endpoint 找 team id。
    注意：此 endpoint 有時候受限，且隊名需精確或接近。
    如果找不到，回傳 None（此時 UI 會要求用戶手動輸入或用滑桿）。
    """
    # 試著查詢 competitions 的 teams: /v4/teams?name={name} 這在官方文件上不保證存在，
    # 我們嘗試用 /v4/teams 搜索，若不支援會回傳 None。
    try:
        url = "https://api.football-data.org/v4/teams"
        headers = {"X-Auth-Token": FD_API_KEY}
        # NOTE: football-data.org 可能不支援 name query param; 改為拉熱門 teams（風險較高）
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None
        data = safe_json(resp)
        teams = data.get("teams") if isinstance(data, dict) else None
        if teams:
            # try exact or case-insensitive match
            for t in teams:
                if t.get("name","").strip().lower() == team_name.strip().lower():
                    return t.get("id")
            # try partial match
            for t in teams:
                if team_name.strip().lower() in t.get("name","").strip().lower():
                    return t.get("id")
        # fallback: try competitions teams? (more complicated)
        return None
    except Exception:
        return None

def fetch_team_recent_matches_by_id(team_id, limit=5):
    """使用 /teams/{id}/matches?status=FINISHED&limit=n 來獲取最近比賽並計算平均進失球"""
    try:
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit={limit}"
        headers = {"X-Auth-Token": FD_API_KEY}
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None
        js = safe_json(resp)
        matches = js.get("matches", []) if js else []
        if not matches:
            return None
        gf = 0
        ga = 0
        n = 0
        for m in matches:
            # fullTime dict
            ft = m.get("score", {}).get("fullTime", {})
            home = m.get("homeTeam", {}).get("id")
            away = m.get("awayTeam", {}).get("id")
            if home == team_id:
                gf += ft.get("home", 0) or 0
                ga += ft.get("away", 0) or 0
            else:
                gf += ft.get("away", 0) or 0
                ga += ft.get("home", 0) or 0
            n += 1
        if n == 0:
            return None
        return gf / n, ga / n
    except Exception:
        return None

# =========================
# Poisson model helpers
# =========================
def poisson_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def score_probability_matrix(home_lambda, away_lambda, max_goals=6):
    matrix = np.zeros((max_goals+1, max_goals+1))
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            matrix[h,a] = poisson_pmf(h, home_lambda) * poisson_pmf(a, away_lambda)
    return matrix

def prob_over_under_from_matrix(matrix, line=2.5):
    over = 0.0
    under = 0.0
    max_idx = matrix.shape[0]-1
    for h in range(matrix.shape[0]):
        for a in range(matrix.shape[1]):
            total = h + a
            if total > line:
                over += matrix[h,a]
            else:
                under += matrix[h,a]
    return over, under

def prob_handicap_from_matrix(matrix, handicap):
    """
    計算主隊 vs 客隊在給定 handicap 下的勝率
    例如 handicap = -1.5 意味著主隊需淨勝 >=2 才算贏盤：
       we compute probability( (home - away) + handicap > 0 ) equivalently home - away > -handicap
    但常用邏輯為：如果 handicap = -1.5 (主隊受讓-1.5)，主隊需要淨勝 >=2
    We'll compute:
      P_home_cover = sum matrix entries where (home - away) > handicap
      P_away_cover = sum entries where (away - home) >= -handicap? (mirror)
    """
    p_home = 0.0
    p_away = 0.0
    for h in range(matrix.shape[0]):
        for a in range(matrix.shape[1]):
            diff = h - a
            if diff > handicap:
                p_home += matrix[h,a]
            elif -diff > handicap:
                p_away += matrix[h,a]
    # Note: tie cases depending on handicap (e.g., handicap = -1.0) can be push; we treat push as neither cover
    return p_home, p_away

# =========================
# Streamlit App
# =========================
st.set_page_config(page_title="Mario Gambling Prediction Plus", layout="wide")
st.title("⚽ Mario Gambling Prediction Plus (The Odds + Football-Data) ⚽")

# sidebar: 選聯賽
league_cn = st.sidebar.selectbox("選擇聯賽", list(LEAGUE_MAP.keys()))
league_info = LEAGUE_MAP[league_cn]
sport_key = league_info["odds_key"]

# 1) 取得 The Odds API 的 match list
with st.spinner("抓取比賽與盤口（The Odds API）..."):
    matches_raw = fetch_odds_matches(sport_key)

if not matches_raw:
    st.error("未取得 The Odds API 比賽資料，請檢查 API key 與網路。")
    st.stop()

# Build a simple DataFrame for display
match_rows = []
for m in matches_raw:
    commence = m.get("commence_time")
    try:
        dt = datetime.fromisoformat(commence.replace("Z","+00:00")) if commence else ""
        dtstr = dt.strftime("%Y-%m-%d %H:%M UTC") if dt else ""
    except:
        dtstr = str(commence or "")
    match_rows.append({
        "match_key": m.get("id") or m.get("key") or "",
        "commence_time": dtstr,
        "home_team": m.get("home_team"),
        "away_team": m.get("away_team"),
        "raw": m
    })
df_matches = pd.DataFrame(match_rows)

st.subheader("比賽清單（The Odds API）")
st.dataframe(df_matches[["commence_time","home_team","away_team"]])

# 選場比賽
sel_idx = st.sidebar.number_input("選擇比賽編號（DataFrame index）", min_value=0, max_value=max(len(df_matches)-1,0), value=0, step=1)
selected_match = df_matches.iloc[sel_idx]
st.markdown(f"### 選擇比賽：{selected_match['home_team']} vs {selected_match['away_team']} ({selected_match['commence_time']})")

# 2) 解析該場賠率
odds_info = extract_average_market_odds(selected_match['raw'])

st.write("🏷️ 莊家盤口（平均抽取）")
st.write(odds_info)

# 3) 嘗試使用 Football-Data 抓球隊最近比賽平均進失球
home_name = selected_match['home_team']
away_name = selected_match['away_team']

st.info("嘗試以 Football-Data.org 查找球隊並抓取近 5 場進球資料（若找不到，請使用下方滑桿手動設定）")

home_team_id = find_fd_team_id_by_name(home_name)
away_team_id = find_fd_team_id_by_name(away_name)

home_stats = None
away_stats = None
if home_team_id:
    home_stats = fetch_team_recent_matches_by_id(home_team_id, limit=5)
if away_team_id:
    away_stats = fetch_team_recent_matches_by_id(away_team_id, limit=5)

# fallback UI: 若找不到 FD 資料，讓使用者手動微調
if home_stats and away_stats:
    home_for, home_against = home_stats
    away_for, away_against = away_stats
    st.success(f"已自動抓取：{home_name} 最近平均進球 {home_for:.2f}, 平均失球 {home_against:.2f}")
    st.success(f"已自動抓取：{away_name} 最近平均進球 {away_for:.2f}, 平均失球 {away_against:.2f}")
else:
    st.warning("找不到部分或全部球隊的 Football-Data 歷史資料，請手動輸入或使用滑桿。")
    # default guesses
    home_for = st.slider(f"{home_name} 近期平均進球 (手動)", 0.0, 4.0, 1.2, 0.05)
    home_against = st.slider(f"{home_name} 近期平均失球 (手動)", 0.0, 4.0, 1.1, 0.05)
    away_for = st.slider(f"{away_name} 近期平均進球 (手動)", 0.0, 4.0, 1.0, 0.05)
    away_against = st.slider(f"{away_name} 近期平均失球 (手動)", 0.0, 4.0, 1.2, 0.05)

# 4) 從近況計算期望進球（簡單方法：home_expected = (home_for + away_against)/2）
home_expected = (home_for + away_against) / 2
away_expected = (away_for + home_against) / 2

st.metric(f"{home_name} 預期進球 (λ)", f"{home_expected:.2f}")
st.metric(f"{away_name} 預期進球 (λ)", f"{away_expected:.2f}")

# 5) Poisson 比分矩陣與大小球 / 讓球 機率
max_goals = 6
matrix = score_probability_matrix(home_expected, away_expected, max_goals=max_goals)

st.subheader("Poisson 預測比分矩陣 (0..6)")
st.dataframe(pd.DataFrame(matrix, index=[f"H{h}" for h in range(max_goals+1)], columns=[f"A{a}" for a in range(max_goals+1)]))

po_over, po_under = prob_over_under_from_matrix(matrix, line=2.5)
st.metric("Poisson Over 2.5 機率", f"{po_over*100:.1f}%", f"Under: {po_under*100:.1f}%")

# compute H2H model probabilities from matrix
p_home_win = matrix[np.triu_indices_from(matrix, k=1)].sum()  # sum of h>a entries
p_away_win = matrix[np.tril_indices_from(matrix, k=-1)].sum() # sum of h<a entries
p_draw = 1 - p_home_win - p_away_win

st.metric("Poisson 獨贏 (主/和/客)", f"{p_home_win*100:.1f}% / {p_draw*100:.1f}% / {p_away_win*100:.1f}%")

# 6) 與莊家盤口比對
st.subheader("模型 vs 莊家 對比")

# totals
if odds_info.get("totals"):
    totals = odds_info["totals"]
    over_odds = totals["over_odds"]
    under_odds = totals["under_odds"]
    # convert to implied probs and normalize
    probs = [implied_prob_from_decimal(over_odds), implied_prob_from_decimal(under_odds)]
    probs_norm = normalize_probs([p for p in probs])
    odd_over_prob = probs_norm[0]
    odd_under_prob = probs_norm[1]
    st.write(f"莊家 Over{totals['line']} 賠率 (avg) : over={over_odds:.3f}, under={under_odds:.3f}")
    st.metric("莊家 Over 2.5 機率", f"{odd_over_prob*100:.1f}%", f"Model: {po_over*100:.1f}%")
    diff_ou = po_over - odd_over_prob
    if diff_ou > 0.10:
        st.warning(f"差異 (模型 - 莊家) = {diff_ou*100:.1f}% → 模型偏向 Over（可能有價值）")
    elif diff_ou < -0.10:
        st.warning(f"差異 (模型 - 莊家) = {diff_ou*100:.1f}% → 模型偏向 Under（可能有價值）")
    else:
        st.info(f"差異 (模型 - 莊家) = {diff_ou*100:.1f}% → 無明顯差異")
else:
    st.info("此場比賽 The Odds API 無提供 totals 資訊。")

# spreads (讓球)
if odds_info.get("spreads"):
    st.write("莊家 讓球盤 (point / home_odds / away_odds / implied probs)")
    for s in odds_info["spreads"]:
        point = s["point"]
        home_prob = implied_prob_from_decimal(s["home_odds"])
        away_prob = implied_prob_from_decimal(s["away_odds"])
        # normalize two outcomes (home/away)
        norm = normalize_probs([home_prob, away_prob])
        st.write(f"point {point}: home_odds={s['home_odds']:.3f} ({norm[0]*100:.1f}%), away_odds={s['away_odds']:.3f} ({norm[1]*100:.1f}%)")
        # model probability to cover for home given this point:
        # cover condition: home - away > point  (if point negative like -1.5)
        # we'll compute p_home_cover (prob home covers) using matrix
        p_home_cover, p_away_cover = prob_handicap_from_matrix(matrix, handicap=point)
        st.write(f"Poisson model 主隊覆蓋 {point} 機率: {p_home_cover*100:.1f}%, 客隊覆蓋: {p_away_cover*100:.1f}%")
        diff_hc = p_home_cover - norm[0]
        if diff_hc > 0.10:
            st.warning(f"差異 (model - bookmaker) = {diff_hc*100:.1f}% → 模型偏向主隊覆蓋")
        elif diff_hc < -0.10:
            st.warning(f"差異 (model - bookmaker) = {diff_hc*100:.1f}% → 模型偏向客隊覆蓋")
else:
    st.info("此場比賽 The Odds API 無提供 spreads 資訊。")

# h2h compare
if odds_info.get("h2h"):
    book = odds_info["h2h"]
    st.write(f"莊家 獨贏賠率 (avg): home={book['home_odds']}, draw={book['draw_odds']}, away={book['away_odds']}")
    st.metric("莊家 獨贏機率 (home/draw/away)", f"{book['home_prob']*100:.1f}% / {book['draw_prob']*100:.1f}% / {book['away_prob']*100:.1f}%")
    st.metric("Poisson 獨贏 (home/draw/away)", f"{p_home_win*100:.1f}% / {p_draw*100:.1f}% / {p_away_win*100:.1f}%")
    diff_home = p_home_win - book['home_prob']
    if diff_home > 0.10:
        st.warning(f"模型比莊家高 {diff_home*100:.1f}% → 模型偏向主勝")
    elif diff_home < -0.10:
        st.warning(f"模型比莊家低 {abs(diff_home)*100:.1f}% → 莊家偏向主勝")
else:
    st.info("此場比賽 The Odds API 無提供 h2h 資訊。")

st.markdown("---")
st.caption("說明：模型為 Poisson 預測推算，如需更準確可加入更多因素（主客場攻防權重、近期輪換、傷停、對賽風格等）。程式已盡量加入 Football-Data 歷史數據，但若找不到 team id，請以滑桿手動微調平均進球。")
