import numpy as np
import logging

logger = logging.getLogger(__name__)


class PriceActionAnalyzer:
    """Detects 8 price action patterns and calculates confirmation score."""

    def __init__(self, min_confirmations=2):
        self.min_confirmations = min_confirmations

    def detect_engulfing(self, candles):
        """Bullish: current candle body > previous candle body."""
        if len(candles) < 2:
            return {'detected': False, 'confidence': 0.0}
        
        prev = candles[-2]
        curr = candles[-1]
        
        prev_body = abs(prev['close'] - prev['open'])
        curr_body = abs(curr['close'] - curr['open'])
        prev_range = prev['high'] - prev['low']
        
        if prev_range == 0:
            return {'detected': False, 'confidence': 0.0}
        
        engulfs = (curr['high'] > prev['high'] and curr['low'] < prev['low'] and
                  curr_body > prev_body)
        
        if engulfs:
            confidence = min(1.0, curr_body / prev_range)
            return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_pinbar(self, candles):
        """Long wick on one side, small body on opposite."""
        if len(candles) < 1:
            return {'detected': False, 'confidence': 0.0}
        
        candle = candles[-1]
        body = abs(candle['close'] - candle['open'])
        full_range = candle['high'] - candle['low']
        
        if full_range == 0:
            return {'detected': False, 'confidence': 0.0}
        
        body_ratio = body / full_range
        
        if body_ratio < 0.3:
            if candle['close'] > candle['open']:
                upper_wick = candle['high'] - candle['close']
                lower_wick = candle['open'] - candle['low']
                long_wick_ratio = upper_wick / full_range
            else:
                upper_wick = candle['high'] - candle['open']
                lower_wick = candle['close'] - candle['low']
                long_wick_ratio = lower_wick / full_range
            
            if long_wick_ratio > 0.4:
                confidence = min(1.0, long_wick_ratio) * (1 - body_ratio)
                return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_morning_star(self, candles):
        """Downtrend reversal: down, small body, up."""
        if len(candles) < 3:
            return {'detected': False, 'confidence': 0.0}
        
        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]
        
        c1_down = c1['close'] < c1['open']
        c2_small = abs(c2['close'] - c2['open']) < (c1['high'] - c1['low']) * 0.5
        c3_up = c3['close'] > c3['open']
        
        if c1_down and c2_small and c3_up:
            confidence = min(1.0, (c3['close'] - c1['open']) / (c1['high'] - c1['low']))
            return {'detected': True, 'confidence': float(max(0.5, confidence))}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_evening_star(self, candles):
        """Uptrend reversal: up, small body, down."""
        if len(candles) < 3:
            return {'detected': False, 'confidence': 0.0}
        
        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]
        
        c1_up = c1['close'] > c1['open']
        c2_small = abs(c2['close'] - c2['open']) < (c1['high'] - c1['low']) * 0.5
        c3_down = c3['close'] < c3['open']
        
        if c1_up and c2_small and c3_down:
            confidence = min(1.0, (c1['close'] - c3['open']) / (c1['high'] - c1['low']))
            return {'detected': True, 'confidence': float(max(0.5, confidence))}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_break_of_structure(self, candles):
        """Price breaks recent swing with momentum."""
        if len(candles) < 5:
            return {'detected': False, 'confidence': 0.0}
        
        recent = candles[-5:]
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        
        swing_high = max(highs[:-1])
        swing_low = min(lows[:-1])
        
        current = candles[-1]
        
        bos_up = current['close'] > swing_high and current['close'] > current['open']
        bos_down = current['close'] < swing_low and current['close'] < current['open']
        
        if bos_up:
            confidence = min(1.0, (current['close'] - swing_high) / swing_high)
            return {'detected': True, 'confidence': float(confidence)}
        elif bos_down:
            confidence = min(1.0, (swing_low - current['close']) / swing_low)
            return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_fair_value_gap(self, candles):
        """Gap between candles with no trade volume."""
        if len(candles) < 2:
            return {'detected': False, 'confidence': 0.0}
        
        prev = candles[-2]
        curr = candles[-1]
        
        gap_up = curr['low'] > prev['high']
        gap_down = curr['high'] < prev['low']
        
        if gap_up:
            gap_size = curr['low'] - prev['high']
            confidence = min(1.0, gap_size / prev['high'])
            return {'detected': True, 'confidence': float(confidence)}
        elif gap_down:
            gap_size = prev['low'] - curr['high']
            confidence = min(1.0, gap_size / prev['low'])
            return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_ema_retest(self, candles, ema_values, ema_period=21):
        """Price returns to EMA and closes on correct side."""
        if len(candles) < 10 or len(ema_values) < 2:
            return {'detected': False, 'confidence': 0.0}
        
        prev_ema = ema_values[-2]
        curr_ema = ema_values[-1]
        current = candles[-1]
        previous = candles[-2]
        
        prev_above = previous['close'] > prev_ema
        curr_below = current['close'] < curr_ema
        curr_above = current['close'] > curr_ema
        
        retest_down = prev_above and (curr_below or abs(current['close'] - curr_ema) < curr_ema * 0.005)
        retest_up = not prev_above and (curr_above or abs(current['close'] - curr_ema) < curr_ema * 0.005)
        
        if retest_down or retest_up:
            distance = abs(current['close'] - curr_ema) / curr_ema
            confidence = 1.0 - min(1.0, distance / 0.01)
            return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def detect_sr_retest(self, candles, sr_zones):
        """Price returns to SR zone with confirmation."""
        if len(candles) < 2 or not sr_zones:
            return {'detected': False, 'confidence': 0.0}
        
        current = candles[-1]
        previous = candles[-2]
        
        for zone in sr_zones:
            zone_price = zone['price']
            tolerance = zone_price * 0.01
            
            prev_above = previous['close'] > zone_price
            curr_near = abs(current['close'] - zone_price) < tolerance
            
            if curr_near and prev_above != (current['close'] > zone_price):
                confidence = min(1.0, zone.get('strength', 0.5) * 1.5)
                return {'detected': True, 'confidence': float(confidence)}
        
        return {'detected': False, 'confidence': 0.0}

    def calculate_confirmation_score(self, candles, sr_zones=None, ema_values=None):
        """
        Calculate total confirmation score from all 8 patterns.
        Returns: {'confirmation_count': int, 'confirmation_score': float}
        """
        confirmations = []
        
        patterns = [
            ('engulfing', self.detect_engulfing(candles)),
            ('pinbar', self.detect_pinbar(candles)),
            ('morning_star', self.detect_morning_star(candles)),
            ('evening_star', self.detect_evening_star(candles)),
            ('bos', self.detect_break_of_structure(candles)),
            ('fvg', self.detect_fair_value_gap(candles)),
        ]
        
        if ema_values is not None:
            try:
                if len(ema_values) > 0:
                    patterns.append(('ema_retest', self.detect_ema_retest(candles, ema_values)))
            except (TypeError, ValueError):
                pass
        
        if sr_zones is not None and len(sr_zones) > 0:
            patterns.append(('sr_retest', self.detect_sr_retest(candles, sr_zones)))
        
        for name, result in patterns:
            if result['detected']:
                confirmations.append({
                    'pattern': name,
                    'confidence': result['confidence']
                })
        
        confirmation_count = len(confirmations)
        confirmation_score = sum(c['confidence'] for c in confirmations) / max(1, len(patterns))
        
        return {
            'confirmation_count': confirmation_count,
            'confirmation_score': float(confirmation_score),
            'min_met': confirmation_count >= self.min_confirmations,
            'patterns': confirmations
        }