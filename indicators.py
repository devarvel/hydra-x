"""Technical Indicators Module - EMA, ATR, and other calculations."""

from typing import List, Dict, Optional, Any
import numpy as np
from utils import get_logger

logger = get_logger("indicators")

def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculate Exponential Moving Average for a list of prices."""
    if len(prices) < period:
        return None
    
    prices = np.array(prices, dtype=np.float64)
    multiplier = 2.0 / (period + 1)
    
    ema = np.mean(prices[:period])
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return float(ema)

def calculate_ema_series(prices: List[float], period: int) -> List[Optional[float]]:
    """Calculate EMA for entire price series."""
    if len(prices) < period:
        return [None] * len(prices)
    
    prices = np.array(prices, dtype=np.float64)
    multiplier = 2.0 / (period + 1)
    
    ema_values = [None] * period
    ema = np.mean(prices[:period])
    ema_values.append(ema)
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
        ema_values.append(ema)
    
    return ema_values[-len(prices):]

def calculate_atr(candles: List[Dict[str, float]], period: int = 14) -> Optional[float]:
    """Calculate Average True Range."""
    if len(candles) < period:
        return None
    
    true_ranges = []
    
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_close = candles[i-1]['close']
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return None
    
    return float(np.mean(true_ranges[-period:]))

def calculate_atr_series(candles: List[Dict[str, float]], period: int = 14) -> List[Optional[float]]:
    """Calculate ATR series for all candles."""
    atr_values = []
    
    for i in range(len(candles)):
        if i + 1 < period:
            atr_values.append(None)
        else:
            atr = calculate_atr(candles[:i+1], period)
            atr_values.append(atr)
    
    return atr_values

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate Relative Strength Index."""
    if len(prices) < period:
        return None
    
    prices = np.array(prices, dtype=np.float64)
    deltas = np.diff(prices)
    
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 0.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi)

def detect_engulfing_pattern(candles: List[Dict[str, float]]) -> Optional[str]:
    """Detect bullish or bearish engulfing pattern."""
    if len(candles) < 2:
        return None
    
    prev = candles[-2]
    curr = candles[-1]
    
    prev_body_size = abs(prev['close'] - prev['open'])
    curr_body_size = abs(curr['close'] - curr['open'])
    
    prev_open_min = min(prev['open'], prev['close'])
    prev_open_max = max(prev['open'], prev['close'])
    
    curr_open_min = min(curr['open'], curr['close'])
    curr_open_max = max(curr['open'], curr['close'])
    
    if curr_body_size > prev_body_size * 0.5:
        if curr['close'] > prev_open_max and curr['open'] < prev_open_min:
            return "BULLISH_ENGULFING"
        elif curr['close'] < prev_open_min and curr['open'] > prev_open_max:
            return "BEARISH_ENGULFING"
    
    return None

def detect_pin_bar(candle: Dict[str, float]) -> Optional[str]:
    """Detect pin bar pattern in a candle."""
    body_size = abs(candle['close'] - candle['open'])
    total_range = candle['high'] - candle['low']
    
    if total_range == 0:
        return None
    
    body_ratio = body_size / total_range
    
    if body_ratio > 0.25:
        return None
    
    upper_wick = candle['high'] - max(candle['open'], candle['close'])
    lower_wick = min(candle['open'], candle['close']) - candle['low']
    
    if upper_wick > body_size * 2 and lower_wick < body_size * 0.5:
        return "PIN_BAR_BEARISH"
    elif lower_wick > body_size * 2 and upper_wick < body_size * 0.5:
        return "PIN_BAR_BULLISH"
    
    return None

def calculate_closes(candles: List[Dict[str, float]]) -> List[float]:
    """Extract close prices from candles."""
    return [candle['close'] for candle in candles]

def calculate_highs(candles: List[Dict[str, float]]) -> List[float]:
    """Extract high prices from candles."""
    return [candle['high'] for candle in candles]

def calculate_lows(candles: List[Dict[str, float]]) -> List[float]:
    """Extract low prices from candles."""
    return [candle['low'] for candle in candles]