import numpy as np
import pandas as pd
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SupportResistanceDetector:
    """Detects swing highs/lows and clusters them into support/resistance zones."""

    def __init__(self, lookback=3, cluster_tolerance=0.0005, min_touches=2):
        self.lookback = lookback
        self.cluster_tolerance = cluster_tolerance
        self.min_touches = min_touches
        self.candle_count = 0
        self.zones = []

    def detect_swings(self, candles):
        """
        Detect swing highs and swing lows using lookback period.
        Returns: {'swings': [{'price': float, 'type': 'high'|'low', 'index': int}]}
        """
        swings = []
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        
        for i in range(self.lookback, len(candles) - self.lookback):
            is_swing_high = True
            is_swing_low = True
            
            for j in range(1, self.lookback + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
            
            if is_swing_high:
                swings.append({
                    'price': float(highs[i]),
                    'type': 'high',
                    'index': i
                })
            
            if is_swing_low:
                swings.append({
                    'price': float(lows[i]),
                    'type': 'low',
                    'index': i
                })
        
        return swings

    def cluster_zones(self, swings):
        """
        Cluster swings within tolerance range (0.05% default).
        Returns: [{'price': float, 'type': 'high'|'low', 'touches': int, 'strength': float}]
        """
        if not swings:
            return []
        
        highs = [s for s in swings if s['type'] == 'high']
        lows = [s for s in swings if s['type'] == 'low']
        
        zones = []
        
        for swing_list, zone_type in [(highs, 'high'), (lows, 'low')]:
            if not swing_list:
                continue
            
            sorted_swings = sorted(swing_list, key=lambda x: x['price'])
            clustered = []
            current_cluster = [sorted_swings[0]]
            
            for swing in sorted_swings[1:]:
                tolerance = current_cluster[0]['price'] * self.cluster_tolerance
                
                if abs(swing['price'] - current_cluster[0]['price']) <= tolerance:
                    current_cluster.append(swing)
                else:
                    avg_price = np.mean([s['price'] for s in current_cluster])
                    clustered.append({
                        'price': float(avg_price),
                        'type': zone_type,
                        'touches': len(current_cluster),
                        'strength': min(1.0, len(current_cluster) / 5.0)
                    })
                    current_cluster = [swing]
            
            if current_cluster:
                avg_price = np.mean([s['price'] for s in current_cluster])
                clustered.append({
                    'price': float(avg_price),
                    'type': zone_type,
                    'touches': len(current_cluster),
                    'strength': min(1.0, len(current_cluster) / 5.0)
                })
            
            zones.extend(clustered)
        
        return [z for z in zones if z['touches'] >= self.min_touches]

    def update_zones(self, candles):
        """
        Auto-update zones every 100 candles.
        """
        self.candle_count += len(candles)
        
        if self.candle_count >= 100 or not self.zones:
            swings = self.detect_swings(candles)
            self.zones = self.cluster_zones(swings)
            self.candle_count = 0
        
        return self.zones

    def get_zones(self, candles=None):
        """
        Get current support/resistance zones.
        """
        if candles:
            return self.update_zones(candles)
        return self.zones

    def find_nearest_zone(self, price, zone_type=None):
        """
        Find nearest zone to current price.
        Returns: {'price': float, 'distance': float, 'type': str, 'strength': float} or None
        """
        if not self.zones:
            return None
        
        filtered_zones = self.zones
        if zone_type:
            filtered_zones = [z for z in self.zones if z['type'] == zone_type]
        
        if not filtered_zones:
            return None
        
        nearest = min(filtered_zones, key=lambda z: abs(z['price'] - price))
        distance = abs(nearest['price'] - price)
        
        return {
            'price': nearest['price'],
            'distance': float(distance),
            'type': nearest['type'],
            'strength': nearest['strength'],
            'touches': nearest['touches']
        }