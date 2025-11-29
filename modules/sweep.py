import numpy as np
import logging

logger = logging.getLogger(__name__)


class LiquiditySweepDetector:
    """Detects SMC-style liquidity sweeps at key price levels."""

    def __init__(self, wick_touch_tolerance=0.001, min_closure_ratio=0.5):
        self.wick_touch_tolerance = wick_touch_tolerance
        self.min_closure_ratio = min_closure_ratio

    def detect_wick_touch(self, current_candle, previous_candle, zone_price):
        """
        Detect if current candle wick touches zone price level.
        Returns: {'touched': bool, 'direction': 'up'|'down', 'distance': float}
        """
        high = current_candle['high']
        low = current_candle['low']
        
        tolerance = zone_price * self.wick_touch_tolerance
        
        if high >= zone_price - tolerance and high <= zone_price + tolerance:
            return {
                'touched': True,
                'direction': 'up',
                'distance': float(abs(high - zone_price))
            }
        
        if low >= zone_price - tolerance and low <= zone_price + tolerance:
            return {
                'touched': True,
                'direction': 'down',
                'distance': float(abs(low - zone_price))
            }
        
        return {
            'touched': False,
            'direction': 'none',
            'distance': float(min(abs(high - zone_price), abs(low - zone_price)))
        }

    def validate_closure_inside(self, current_candle, previous_candle):
        """
        Validate that candle closes back inside previous candle range.
        Returns: {'inside': bool, 'closure_ratio': float}
        """
        prev_high = previous_candle['high']
        prev_low = previous_candle['low']
        curr_close = current_candle['close']
        curr_open = current_candle['open']
        
        inside = curr_close >= prev_low and curr_close <= prev_high
        
        if inside:
            prev_range = prev_high - prev_low
            if prev_range == 0:
                closure_ratio = 0.5
            else:
                closure_ratio = (curr_close - prev_low) / prev_range
        else:
            closure_ratio = 0.0
        
        return {
            'inside': inside,
            'closure_ratio': float(closure_ratio)
        }

    def detect_sweep(self, candles, sr_zones):
        """
        Detect liquidity sweep pattern.
        Returns: {'sweep_detected': bool, 'direction': 'up'|'down', 'score': float, 'touched_level': float}
        """
        if len(candles) < 2:
            return {'sweep_detected': False, 'direction': 'none', 'score': 0.0, 'touched_level': None}
        
        current = candles[-1]
        previous = candles[-2]
        
        best_sweep = None
        best_score = 0.0
        
        for zone in sr_zones:
            wick_touch = self.detect_wick_touch(current, previous, zone['price'])
            
            if not wick_touch['touched']:
                continue
            
            closure = self.validate_closure_inside(current, previous)
            
            if not closure['inside']:
                continue
            
            touch_score = 1.0 - min(1.0, wick_touch['distance'] / (zone['price'] * 0.01))
            closure_score = closure['closure_ratio'] if closure['closure_ratio'] > self.min_closure_ratio else 0
            
            final_score = (touch_score + closure_score) / 2.0 * zone.get('strength', 0.5)
            
            if final_score > best_score:
                best_score = final_score
                best_sweep = {
                    'direction': wick_touch['direction'],
                    'touched_level': zone['price'],
                    'zone_strength': zone.get('strength', 0.5)
                }
        
        if best_sweep is None:
            return {'sweep_detected': False, 'direction': 'none', 'score': 0.0, 'touched_level': None}
        
        return {
            'sweep_detected': True,
            'direction': best_sweep['direction'],
            'score': float(min(1.0, best_score)),
            'touched_level': float(best_sweep['touched_level']),
            'zone_strength': float(best_sweep['zone_strength'])
        }

    def validate_confirmation(self, candles):
        """
        Validate confirmation candle after sweep.
        Returns: {'confirmed': bool, 'direction': 'up'|'down'}
        """
        if len(candles) < 2:
            return {'confirmed': False, 'direction': 'none'}
        
        prev_close = candles[-2]['close']
        curr_close = candles[-1]['close']
        
        if curr_close > prev_close:
            return {'confirmed': True, 'direction': 'up'}
        elif curr_close < prev_close:
            return {'confirmed': True, 'direction': 'down'}
        
        return {'confirmed': False, 'direction': 'none'}