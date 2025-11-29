import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BreakoutEngine:
    """Detects compression boxes and ATR spikes for breakout signals."""

    def __init__(self, compression_candles=(20, 40), atr_threshold=1.5, 
                 min_body_ratio=0.6, max_wick_ratio=0.25):
        self.compression_candles = compression_candles
        self.atr_threshold = atr_threshold
        self.min_body_ratio = min_body_ratio
        self.max_wick_ratio = max_wick_ratio

    def calculate_atr(self, candles, period=14):
        """Calculate Average True Range."""
        if len(candles) < period:
            return None
        
        tr_values = []
        for i in range(len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            close_prev = candles[i-1]['close'] if i > 0 else candles[i]['close']
            
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            tr_values.append(tr)
        
        atr = np.mean(tr_values[-period:])
        return float(atr)

    def detect_compression(self, candles):
        """
        Detect compression box: consecutive candles with decreasing ATR.
        Returns: {'compressed': bool, 'candle_count': int, 'avg_atr': float}
        """
        if len(candles) < self.compression_candles[0]:
            return {'compressed': False, 'candle_count': 0, 'avg_atr': 0}
        
        atr_values = []
        for i in range(len(candles) - 1):
            candle = candles[i]
            close_prev = candles[i-1]['close'] if i > 0 else candle['close']
            
            tr = max(
                candle['high'] - candle['low'],
                abs(candle['high'] - close_prev),
                abs(candle['low'] - close_prev)
            )
            atr_values.append(tr)
        
        if len(atr_values) < self.compression_candles[0]:
            return {'compressed': False, 'candle_count': 0, 'avg_atr': 0}
        
        recent_atr = atr_values[-self.compression_candles[0]:]
        
        is_decreasing = all(
            recent_atr[i] >= recent_atr[i+1] 
            for i in range(len(recent_atr) - 1)
        )
        
        avg_atr = float(np.mean(recent_atr))
        
        return {
            'compressed': is_decreasing,
            'candle_count': self.compression_candles[0],
            'avg_atr': avg_atr
        }

    def detect_atr_spike(self, candles):
        """
        Detect ATR spike: current ATR > historical average * threshold.
        Returns: {'spike': bool, 'current_atr': float, 'avg_atr': float, 'ratio': float}
        """
        if len(candles) < 50:
            return {'spike': False, 'current_atr': 0, 'avg_atr': 0, 'ratio': 0}
        
        current_atr = self.calculate_atr(candles[-20:], period=14)
        historical_atr = self.calculate_atr(candles, period=50)
        
        if historical_atr is None or current_atr is None:
            return {'spike': False, 'current_atr': 0, 'avg_atr': 0, 'ratio': 0}
        
        ratio = current_atr / historical_atr if historical_atr > 0 else 0
        spike = ratio > self.atr_threshold
        
        return {
            'spike': spike,
            'current_atr': float(current_atr),
            'avg_atr': float(historical_atr),
            'ratio': float(ratio)
        }

    def validate_body_wick(self, candle):
        """
        Validate candle body strength and wick weakness.
        Returns: {'valid': bool, 'body_ratio': float, 'wick_ratio': float, 'direction': 'up'|'down'}
        """
        high = candle['high']
        low = candle['low']
        open_price = candle['open']
        close_price = candle['close']
        
        full_range = high - low
        if full_range == 0:
            return {'valid': False, 'body_ratio': 0, 'wick_ratio': 0, 'direction': 'none'}
        
        body_range = abs(close_price - open_price)
        body_ratio = body_range / full_range
        
        if close_price > open_price:
            upper_wick = high - close_price
            lower_wick = open_price - low
            direction = 'up'
            opposite_wick_ratio = lower_wick / full_range
        else:
            upper_wick = high - open_price
            lower_wick = close_price - low
            direction = 'down'
            opposite_wick_ratio = upper_wick / full_range
        
        valid = (body_ratio >= self.min_body_ratio and 
                opposite_wick_ratio <= self.max_wick_ratio)
        
        return {
            'valid': valid,
            'body_ratio': float(body_ratio),
            'wick_ratio': float(opposite_wick_ratio),
            'direction': direction
        }

    def generate_breakout_signal(self, candles):
        """
        Generate breakout signal combining all conditions.
        Returns: {'signal': 'LONG'|'SHORT'|'NONE', 'strength': float, 'details': dict}
        """
        if len(candles) < 20:
            return {'signal': 'NONE', 'strength': 0.0, 'details': {}}
        
        current_candle = candles[-1]
        compression = self.detect_compression(candles)
        atr_spike = self.detect_atr_spike(candles)
        body_wick = self.validate_body_wick(current_candle)
        
        all_valid = (compression['compressed'] and atr_spike['spike'] and body_wick['valid'])
        
        if not all_valid:
            return {'signal': 'NONE', 'strength': 0.0, 'details': {
                'compression': compression,
                'atr_spike': atr_spike,
                'body_wick': body_wick
            }}
        
        signal = 'LONG' if body_wick['direction'] == 'up' else 'SHORT'
        strength = min(1.0, (atr_spike['ratio'] / self.atr_threshold) * body_wick['body_ratio'])
        
        return {
            'signal': signal,
            'strength': float(strength),
            'details': {
                'compression': compression,
                'atr_spike': atr_spike,
                'body_wick': body_wick
            }
        }