# smc_logic.py
# SMC detection helpers + multi-timeframe trend & confidence table
# Dependencies: pandas, numpy, oandapyV20
# Place this file in your project and import functions:
# from smc_logic import generate_tf_trend_table, detect_all_pois_for_df
#
# Note: This file expects an OANDA API client instance to be passed in (so your main script
# which already builds client = API(access_token=...) will pass it).

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ---------------------------
# Helper/utility functions
# ---------------------------

def pip_size_for_pair(pair: str) -> float:
    return 0.01 if "JPY" in pair else 0.0001

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=1).mean()

def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()

# ---------------------------
# SMC detection heuristics
# ---------------------------

def detect_swing_structure(df: pd.DataFrame, left: int = 3, right: int = 3) -> Tuple[List[pd.Timestamp], List[pd.Timestamp]]:
    """
    Return (swing_highs, swing_lows) timestamps.
    """
    highs = []
    lows = []
    n = len(df)
    for i in range(left, n - right):
        window_high = df['high'].iloc[i - left:i + right + 1]
        window_low = df['low'].iloc[i - left:i + right + 1]
        if df['high'].iloc[i] == window_high.max():
            highs.append(df.index[i])
        if df['low'].iloc[i] == window_low.min():
            lows.append(df.index[i])
    return highs, lows

def detect_fvg_and_invalidate(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
    """
    Detect FVGs (3-bar heuristic) and convert invalidated FVGs to inverse FVGs.
    Returns: (valid_fvgs, inverse_fvgs)
    Each FVG is a dict:
      {"start_idx": Timestamp, "type": "bullish"/"bearish", "top": float, "bottom": float, "valid": bool}
    Invalidation rule: if price fully closes inside the gap (close crosses inside), convert to inverse FVG.
    """
    fvgs = []
    inv_fvgs = []
    n = len(df)
    for i in range(n - 2):
        b1 = df.iloc[i]
        b2 = df.iloc[i + 1]
        b3 = df.iloc[i + 2]
        # bullish FVG: b1.low > b3.high  (imbalance above price -> gap between b3.high and b1.low)
        if b1['low'] > b3['high']:
            top = b1['low']
            bottom = b3['high']
            fvgs.append({"start_idx": df.index[i], "type": "bullish", "top": top, "bottom": bottom, "valid": True})
        # bearish FVG
        if b1['high'] < b3['low']:
            top = b3['low']
            bottom = b1['high']
            fvgs.append({"start_idx": df.index[i], "type": "bearish", "top": top, "bottom": bottom, "valid": True})

    # now check for invalidations: if any later candle (after FVG start) has close inside [bottom,top] fully -> invalidated
    for f in fvgs:
        start_pos = df.index.get_loc(f['start_idx'])
        invalidated = False
        for j in range(start_pos + 3, len(df)):
            c = df['close'].iloc[j]
            # if close enters the gap
            if c >= f['bottom'] and c <= f['top']:
                # full fill (invalidation)
                invalidated = True
                break
        if invalidated:
            # convert to inverse FVG (iFVG) - flip direction and mark not valid as original
            f['valid'] = False
            # iFVG coordinates: same band but now treat as opposite type
            inv_type = 'bearish' if f['type'] == 'bullish' else 'bullish'
            inv_fvgs.append({"orig_start": f['start_idx'], "type": inv_type, "top": f['top'], "bottom": f['bottom'], "converted_from": f['type']})
    # keep only still valid fvgs
    valid_fvgs = [f for f in fvgs if f.get('valid', True)]
    return valid_fvgs, inv_fvgs

def detect_order_blocks(df: pd.DataFrame) -> List[Dict]:
    """
    Simple OB detection: consider candle prior to strong directional move.
    Returns list of dicts: {"idx": Timestamp, "type":"bullish"/"bearish", "high":float, "low":float}
    Heuristic: if a bearish candle is followed by at least one strong bullish candle (close>open and close>prev.open),
    then previous candle may be a bullish OB. The implementation is intentionally conservative.
    """
    obs = []
    for i in range(1, len(df) - 1):
        prev = df.iloc[i - 1]
        nxt = df.iloc[i + 1]
        # bullish OB candidate
        if prev['close'] < prev['open'] and nxt['close'] > nxt['open'] and nxt['close'] > prev['open']:
            obs.append({"idx": df.index[i - 1], "type": "bullish", "high": float(prev['high']), "low": float(prev['low'])})
        # bearish OB candidate
        if prev['close'] > prev['open'] and nxt['close'] < nxt['open'] and nxt['close'] < prev['open']:
            obs.append({"idx": df.index[i - 1], "type": "bearish", "high": float(prev['high']), "low": float(prev['low'])})
    return obs

def detect_breaker_blocks(df: pd.DataFrame, obs: List[Dict], retest_bars:int=10) -> List[Dict]:
    """
    For each OB, look forward for a Break of Structure (BOS) past the OB high/low and then for a retest into the OB zone.
    If both occur within a reasonable window, call it a breaker block.
    """
    breakers = []
    idx_map = {t: pos for pos, t in enumerate(df.index)}
    for ob in obs:
        try:
            pos = idx_map[ob['idx']]
        except KeyError:
            continue
        hh = ob['high']; ll = ob['low']; typ = ob['type']
        # search for BOS: for bullish OB we expect price to break above hh; for bearish OB break below ll
        for j in range(pos+1, min(len(df), pos+1+200)):
            if typ == 'bullish' and df['high'].iloc[j] > hh:
                # found break; now look for retest within retest_bars
                for k in range(j+1, min(len(df), j+1+retest_bars)):
                    if df['low'].iloc[k] >= ll and df['high'].iloc[k] <= hh:
                        # retest inside OB zone -> breaker bullish
                        breakers.append({"ob_idx": ob['idx'], "type": "breaker_bullish", "hh":hh, "ll":ll, "retest_idx": df.index[k]})
                        break
                break
            if typ == 'bearish' and df['low'].iloc[j] < ll:
                for k in range(j+1, min(len(df), j+1+retest_bars)):
                    if df['low'].iloc[k] >= ll and df['high'].iloc[k] <= hh:
                        breakers.append({"ob_idx": ob['idx'], "type": "breaker_bearish", "hh":hh, "ll":ll, "retest_idx": df.index[k]})
                        break
                break
    return breakers

def detect_liquidity_pools(df: pd.DataFrame, window:int=50, tolerance:float=1e-5) -> List[Dict]:
    """
    Detect horizontal clusters of highs or lows (equal-highs/equal-lows) within a window.
    Return list of liquidity pools: {"level":float, "type":"high"/"low", "count":int}
    """
    pools = []
    highs = df['high'].rolling(window).max().dropna()
    lows = df['low'].rolling(window).min().dropna()
    # simple approach: find repeated highs/lows using rounding
    rounded_highs = (df['high'].round(4)).value_counts()
    rounded_lows = (df['low'].round(4)).value_counts()
    # choose values with more than one occurrence
    for val, cnt in rounded_highs.items():
        if cnt >= 2:
            pools.append({"level": float(val), "type": "high", "count": int(cnt)})
    for val, cnt in rounded_lows.items():
        if cnt >= 2:
            pools.append({"level": float(val), "type": "low", "count": int(cnt)})
    return pools

# ---------------------------
# Multi-timeframe trend & confidence
# ---------------------------

def evaluate_single_tf(df: pd.DataFrame, instrument: str, lookback: int = 50) -> Dict:
    """
    Evaluate trend & confidence for a single timeframe DataFrame.
    Returns dict: {"trend": "Bull"/"Bear"/"Sideways", "confidence": int(0-100), "reasons": [str,...], "details": {...}}
    """
    out = {"trend":"Sideways", "confidence":0, "reasons":[], "details":{}}
    if df.empty or len(df) < 10:
        out['reasons'].append("Insufficient data")
        return out
    df2 = df.copy().tail(lookback)
    closes = df2['close']
    highs = df2['high']; lows = df2['low']; opens = df2['open']
    # signals weights (tweakable)
    weights = {
        "ma_slope": 25,
        "ma_crossover": 20,
        "price_vs_ma": 15,
        "bull_pct": 10,
        "swing_structure": 15,
        "poi_support": 15
    }
    score = 0
    reasons = []
    details = {}

    # MA slope: ema(34) slope sign
    ma_short = ema(closes, 8).iloc[-1]
    ma_long = ema(closes, 34).iloc[-1]
    # slope approx: slope = (ma_short - ma_long) / ma_long
    slope = (ma_short - ma_long) / ma_long
    if slope > 0.0005:  # small threshold
        score += weights['ma_slope']
        reasons.append("MA slope bullish")
    elif slope < -0.0005:
        score -= weights['ma_slope']
        reasons.append("MA slope bearish")
    details['ma_short'] = float(ma_short); details['ma_long'] = float(ma_long); details['slope'] = float(slope)

    # crossover within lookback
    cross = False; cross_dir = None
    ema_short_series = ema(closes, 8)
    ema_long_series = ema(closes, 34)
    # detect most recent crossover (last 10 bars)
    recent = min(len(closes), 10)
    for i in range(-recent, -1):
        if ema_short_series.iloc[i] > ema_long_series.iloc[i] and ema_short_series.iloc[i-1] <= ema_long_series.iloc[i-1]:
            cross=True; cross_dir='bull'
            break
        if ema_short_series.iloc[i] < ema_long_series.iloc[i] and ema_short_series.iloc[i-1] >= ema_long_series.iloc[i-1]:
            cross=True; cross_dir='bear'
            break
    if cross and cross_dir == 'bull':
        score += weights['ma_crossover']; reasons.append("Recent MA crossover bullish")
    elif cross and cross_dir == 'bear':
        score -= weights['ma_crossover']; reasons.append("Recent MA crossover bearish")

    # price vs long MA
    current_close = closes.iloc[-1]
    if current_close > ma_long:
        score += weights['price_vs_ma']; reasons.append("Price above long MA")
    else:
        score -= weights['price_vs_ma']; reasons.append("Price below long MA")
    details['current_close'] = float(current_close)

    # percent bullish candles
    bull_pct = (closes.diff() > 0).sum() / max(1, len(closes)) * 100
    details['bull_pct'] = float(bull_pct)
    if bull_pct > 60:
        score += weights['bull_pct']; reasons.append("Strong bullish candles ratio")
    elif bull_pct < 40:
        score -= weights['bull_pct']; reasons.append("Strong bearish candles ratio")

    # swing structure: check last few swings for HH/HL or LH/LL
    highs_idx = detect_swing_structure(df2, left=2, right=2)[0]
    lows_idx = detect_swing_structure(df2, left=2, right=2)[1]
    # simple MSS: last two swing points compare
    mss_signal = None
    try:
        if len(highs_idx) >= 2:
            last_high = df2.loc[highs_idx[-1]]['high']
            prev_high = df2.loc[highs_idx[-2]]['high']
            if last_high > prev_high:
                mss_signal = 'bull'
        if len(lows_idx) >= 2:
            last_low = df2.loc[lows_idx[-1]]['low']
            prev_low = df2.loc[lows_idx[-2]]['low']
            if last_low > prev_low and mss_signal is None:
                mss_signal = 'bull'
    except Exception:
        pass
    if mss_signal == 'bull':
        score += weights['swing_structure']; reasons.append("Market structure bullish (HH/HL)")
    elif mss_signal == 'bear':
        score -= weights['swing_structure']; reasons.append("Market structure bearish (LH/LL)")

    # POI support: naive check using detect_fvg and detect_order_blocks (small lookback)
    fvgs, ifvgs = detect_fvg_and_invalidate(df2)
    obs = detect_order_blocks(df2)
    # supportive POIs
    poi_support = 0
    # if there is a bull FVG near price -> bullish support
    for f in fvgs:
        if f['type'] == 'bullish' and f['bottom'] <= current_close <= f['top']:
            poi_support += 1
    for ob in obs:
        if ob['type'] == 'bullish' and ob['low'] <= current_close <= ob['high']:
            poi_support += 1
    if poi_support > 0:
        score += weights['poi_support']; reasons.append(f"POI support count={poi_support}")

    # normalize score range to -sum(weights) .. +sum(weights)
    max_score = sum(weights.values())
    norm = (score + max_score) / (2 * max_score)  # 0..1
    confidence = int(round(norm * 100))
    # decide trend
    if confidence >= 60 and score > 0:
        trend = "Bull"
    elif confidence >= 60 and score < 0:
        trend = "Bear"
    else:
        trend = "Sideways"

    out = {"trend": trend, "confidence": confidence, "reasons": reasons, "details": details}
    return out

# ---------------------------
# Multi-timeframe trend table
# ---------------------------

# map timeframe keywords to OANDA granularity strings
TF_TO_OANDA = {
    "M1": "M1",
    "M3": "M3",
    "M5": "M5",
    "M15": "M15",
    "H1": "H1",
    "H4": "H4",
    "D1": "D"
}

def fetch_candles_from_oanda_client(oanda_client, instrument: str, granularity: str, count: int = 500) -> pd.DataFrame:
    """Helper wrapper to fetch candles using an oandapyV20 API client instance."""
    from oandapyV20 import API as _API  # local import for type clarity
    import oandapyV20.endpoints.instruments as instruments
    params = {"count": count, "granularity": granularity}
    req = instruments.InstrumentsCandles(instrument=instrument, params=params)
    resp = oanda_client.request(req)
    rows = []
    for c in resp.get('candles', []):
        if not c.get('complete', False):
            continue
        mid = c.get('mid', {})
        rows.append({
            "time": pd.to_datetime(c['time']),
            "open": float(mid['o']),
            "high": float(mid['h']),
            "low": float(mid['l']),
            "close": float(mid['c']),
            "volume": int(c.get('volume', 0))
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index('time')
    return df

def generate_tf_trend_table(oanda_client, instrument: str, timeframes: Optional[List[str]] = None, count_per_tf:int = 500) -> pd.DataFrame:
    """
    Generate a table for multiple timeframes with trend and confidence.
    Returns pandas DataFrame with columns: timeframe, trend, confidence, reasons (joined string).
    Usage:
      from smc_logic import generate_tf_trend_table
      table = generate_tf_trend_table(client, "EUR_USD")
    """
    if timeframes is None:
        timeframes = ["M1","M3","M5","M15","H1","H4","D1"]
    rows = []
    for tf in timeframes:
        gran = TF_TO_OANDA.get(tf, tf)
        try:
            df = fetch_candles_from_oanda_client(oanda_client, instrument, granularity=gran, count=count_per_tf)
        except Exception as e:
            # if fetch failed, populate empty row
            rows.append({"timeframe": tf, "trend": "NA", "confidence": 0, "reasons": f"fetch_error:{e}"})
            continue
        eval_res = evaluate_single_tf(df, instrument, lookback= min(200, len(df)))
        reasons_joined = "; ".join(eval_res['reasons'][:5])
        rows.append({"timeframe": tf, "trend": eval_res['trend'], "confidence": eval_res['confidence'], "reasons": reasons_joined})
    table = pd.DataFrame(rows).set_index('timeframe')
    return table

# ---------------------------
# Detect all POIs for a dataframe
# ---------------------------
def detect_all_pois_for_df(df: pd.DataFrame) -> Dict:
    """
    Given a DataFrame of OHLC indexed by datetime, detect POIs and return structured dict:
      {"fvg": [...], "i_fvg": [...], "order_blocks":[...], "breaker_blocks":[...], "liquidity_pools":[...], "swings": {...}}
    Each list contains dicts with coordinates and metadata.
    """
    swings_h, swings_l = detect_swing_structure(df)
    fvg_list, inv_fvgs = detect_fvg_and_invalidate(df)
    obs = detect_order_blocks(df)
    breakers = detect_breaker_blocks(df, obs)
    pools = detect_liquidity_pools(df)
    return {
        "fvg": fvg_list,
        "i_fvg": inv_fvgs,
        "order_blocks": obs,
        "breaker_blocks": breakers,
        "liquidity_pools": pools,
        "swings": {"highs": swings_h, "lows": swings_l}
    }

# ---------------------------
# End of module
# ---------------------------
