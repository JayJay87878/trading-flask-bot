# smc_engine.py
"""
Enhanced Stage 1: Full SMC Engine
Features:
- Liquidity Pools (equal highs/lows, stop-hunt detection)
- Order Blocks (OB) & Breaker Blocks (BB)
- FVG detection with fill thresholds and inverse conversion
- Multi-Timeframe structure & confluence scoring
- Signal objects include detailed confluence for decision-making
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import datetime

# -----------------------------
# Data Structures
# -----------------------------
@dataclass
class Candle:
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class POI:
    poi_type: str            # FVG / OB / BB / Liquidity
    direction: str           # bullish / bearish
    start: float
    end: float
    validated: bool = True
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)

@dataclass
class Signal:
    symbol: str
    direction: str           # long / short
    entry: float
    stop: float
    target: float
    rr: float
    confluence: Dict[str, bool]
    confluence_score: int

# -----------------------------
# Core Engine
# -----------------------------
class SMCEngine:
    def __init__(self, symbol: str, primary_tf='M15', lower_tfs=None, higher_tfs=None, fvg_fill_threshold=0.5):
        self.symbol = symbol
        self.primary_tf = primary_tf
        self.lower_tfs = lower_tfs or ['M1', 'M5']
        self.higher_tfs = higher_tfs or ['H1', 'H4']
        self.candles = {tf: [] for tf in [primary_tf] + self.lower_tfs + self.higher_tfs}
        self.pois: List[POI] = []
        self.fvg_fill_threshold = fvg_fill_threshold

    # -----------------------------
    # Candle Management
    # -----------------------------
    def add_candles(self, tf: str, candle_list: List[Dict]):
        for c in candle_list:
            candle = Candle(
                timestamp=datetime.datetime.fromisoformat(c['time']),
                open=float(c['open']),
                high=float(c['high']),
                low=float(c['low']),
                close=float(c['close']),
                volume=float(c.get('volume', 0))
            )
            self.candles[tf].append(candle)

    # -----------------------------
    # Market Structure Detection
    # -----------------------------
    def detect_structure(self, tf: str) -> Dict[str, str]:
        candles = self.candles[tf]
        if len(candles) < 5:
            return {"direction": "unknown"}

        highs = [c.high for c in candles[-5:]]
        lows = [c.low for c in candles[-5:]]

        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return {"direction": "bullish"}
        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return {"direction": "bearish"}
        else:
            return {"direction": "ranging"}

    # -----------------------------
    # FVG Detection
    # -----------------------------
    def detect_fvgs(self, tf: str):
        candles = self.candles[tf]
        if len(candles) < 3:
            return
        last3 = candles[-3:]

        # Bearish FVG
        if last3[1].low > last3[2].high:
            start, end = last3[2].high, last3[1].low
            poi = POI("FVG", "bearish", start, end)
            self.pois.append(poi)

        # Bullish FVG
        elif last3[1].high < last3[2].low:
            start, end = last3[1].high, last3[2].low
            poi = POI("FVG", "bullish", start, end)
            self.pois.append(poi)

    def validate_fvgs(self):
        for poi in self.pois:
            if poi.poi_type != "FVG" or not poi.validated:
                continue
            # Check if fill exceeds threshold
            tf_candles = self.candles[self.primary_tf]
            for c in tf_candles[-10:]:
                if poi.direction == "bullish" and c.low < poi.start:
                    fill_ratio = (poi.start - c.low) / (poi.end - poi.start)
                    if fill_ratio >= self.fvg_fill_threshold:
                        poi.validated = False
                        # Convert to inverse FVG
                        inverse_poi = POI("FVG", "bearish", poi.start, poi.end)
                        self.pois.append(inverse_poi)
                        break
                elif poi.direction == "bearish" and c.high > poi.end:
                    fill_ratio = (c.high - poi.end) / (poi.end - poi.start)
                    if fill_ratio >= self.fvg_fill_threshold:
                        poi.validated = False
                        inverse_poi = POI("FVG", "bullish", poi.start, poi.end)
                        self.pois.append(inverse_poi)
                        break

    # -----------------------------
    # Liquidity Pool Detection
    # -----------------------------
    def detect_liquidity_pools(self, tf: str):
        candles = self.candles[tf]
        if len(candles) < 3:
            return
        last3 = candles[-3:]
        # Detect equal highs/lows as potential liquidity
        if abs(last3[0].high - last3[2].high) < 0.0003:
            poi = POI("Liquidity", "bearish", last3[0].high, last3[2].high)
            self.pois.append(poi)
        if abs(last3[0].low - last3[2].low) < 0.0003:
            poi = POI("Liquidity", "bullish", last3[0].low, last3[2].low)
            self.pois.append(poi)

    # -----------------------------
    # Order Blocks & Breaker Blocks
    # -----------------------------
    def detect_order_blocks(self, tf: str):
        candles = self.candles[tf]
        if len(candles) < 5:
            return
        last_candle = candles[-2]
        prev_candle = candles[-3]
        # Example: bullish OB
        if prev_candle.close < prev_candle.open and last_candle.close > last_candle.open:
            poi = POI("OB", "bullish", prev_candle.open, prev_candle.close)
            self.pois.append(poi)
        # Example: bearish OB
        elif prev_candle.close > prev_candle.open and last_candle.close < last_candle.open:
            poi = POI("OB", "bearish", prev_candle.close, prev_candle.open)
            self.pois.append(poi)

    # -----------------------------
    # POI Validation
    # -----------------------------
    def validate_pois(self):
        self.validate_fvgs()
        # Additional validation can be implemented here for OB/BB/liquidity

    # -----------------------------
    # Confluence Scoring
    # -----------------------------
    def calculate_confluence_score(self, signal: Signal) -> int:
        score = 0
        for k, v in signal.confluence.items():
            if v:
                score +=1
        return score

    # -----------------------------
    # Signal Generation
    # -----------------------------
    def generate_signal(self) -> Optional[Signal]:
        for poi in self.pois:
            if not poi.validated:
                continue
            if poi.poi_type in ["FVG", "OB", "BB"]:
                entry = poi.start if poi.direction == "bullish" else poi.end
                stop = poi.end if poi.direction == "bullish" else poi.start
                target = entry + (entry - stop) * 1.5 if poi.direction == "bullish" else entry - (stop - entry) * 1.5
                confluence = {
                    "fvg": any(p.poi_type=="FVG" and p.direction==poi.direction for p in self.pois),
                    "order_block": any(p.poi_type=="OB" and p.direction==poi.direction for p in self.pois),
                    "breaker_block": any(p.poi_type=="BB" and p.direction==poi.direction for p in self.pois),
                    "liquidity_sweep": any(p.poi_type=="Liquidity" and p.direction==poi.direction for p in self.pois)
                }
                signal = Signal(
                    symbol=self.symbol,
                    direction="long" if poi.direction=="bullish" else "short",
                    entry=entry,
                    stop=stop,
                    target=target,
                    rr=abs(target-entry)/abs(entry-stop),
                    confluence=confluence,
                    confluence_score=sum(confluence.values())
                )
                # Optional: filter low confluence signals
                if signal.confluence_score >= 2:
                    return signal
        return None
