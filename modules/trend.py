import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyzes trend using EMA50/200 on M15 and H1 candle body bias."""

    def __init__(self, ema_fast=50, ema_slow=200):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def calculate_ema(self, closes, period):
        """Calculate EMA using standard formula."""
        if len(closes) < period:
            return None
        
        ema = np.zeros(len(closes))
        multiplier = 2.0 / (period + 1)
        
        ema[period - 1] = np.mean(closes[:period])
        
        for i in range(period, len(closes)):
            ema[i] = closes[i] * multiplier + ema[i - 1] * (1 - multiplier)
        
        return ema

    def analyze_trend(self, m15_candles):
        """
        Determine trend bias from M15 EMA50/200.
        Returns: {'trend': 'bullish'|'bearish'|'ranging', 'ema50': float, 'ema200': float}
        """
        if len(m15_candles) < self.ema_slow:
            return {'trend': 'ranging', 'ema50': None, 'ema200': None}
        
        closes = np.array([c['close'] for c in m15_candles])
        
        ema50 = self.calculate_ema(closes, self.ema_fast)
        ema200 = self.calculate_ema(closes, self.ema_slow)
        
        if ema50 is None or ema200 is None:
            return {'trend': 'ranging', 'ema50': None, 'ema200': None}
        
        current_ema50 = ema50[-1]
        current_ema200 = ema200[-1]
        
        tolerance = current_ema200 * 0.005
        
        if current_ema50 > current_ema200 + tolerance:
            trend = 'bullish'
        elif current_ema50 < current_ema200 - tolerance:
            trend = 'bearish'
        else:
            trend = 'ranging'
        
        return {
            'trend': trend,
            'ema50': float(current_ema50),
            'ema200': float(current_ema200),
            'tolerance': float(tolerance)
        }

    def analyze_h1_bias(self, h1_candle):
        """
        Determine H1 candle body bias.
        Returns: {'bias': 'bullish'|'bearish', 'body_position': float (0-1)}
        """
        if not h1_candle:
            return {'bias': 'neutral', 'body_position': 0.5}
        
        open_price = h1_candle['open']
        close_price = h1_candle['close']
        high = h1_candle['high']
        low = h1_candle['low']
        
        candle_range = high - low
        if candle_range == 0:
            return {'bias': 'neutral', 'body_position': 0.5}
        
        mid_point = (open_price + close_price) / 2
        body_position = (mid_point - low) / candle_range
        
        if body_position > 0.5:
            bias = 'bullish'
        elif body_position < 0.5:
            bias = 'bearish'
        else:
            bias = 'neutral'
        
        return {
            'bias': bias,
            'body_position': float(body_position),
            'candle_range': float(candle_range)
        }

    def get_trend_confirmation(self, m15_candles, h1_candle):
        """
        Get combined trend confirmation from M15 EMA and H1 bias.
        Returns: {'m15_trend': str, 'h1_bias': str, 'confirmed': bool, 'details': dict}
        """
        m15_trend = self.analyze_trend(m15_candles)
        h1_bias = self.analyze_h1_bias(h1_candle)
        
        m15_direction = m15_trend['trend']
        h1_direction = h1_bias['bias']
        
        confirmed = False
        if m15_direction == 'bullish' and h1_direction == 'bullish':
            confirmed = True
        elif m15_direction == 'bearish' and h1_direction == 'bearish':
            confirmed = True
        elif m15_direction == 'ranging':
            confirmed = True
        
        return {
            'm15_trend': m15_direction,
            'h1_bias': h1_direction,
            'confirmed': confirmed,
            'ema50': m15_trend.get('ema50'),
            'ema200': m15_trend.get('ema200'),
            'h1_body_position': h1_bias.get('body_position')
        }