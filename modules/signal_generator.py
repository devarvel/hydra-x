import numpy as np
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from modules.trend import TrendAnalyzer
from modules.support_resistance import SupportResistanceDetector
from modules.breakout import BreakoutEngine
from modules.sweep import LiquiditySweepDetector
from modules.price_action import PriceActionAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """Result object for signal generation."""
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    signal_strength: float
    confirmation_count: int
    component_scores: Dict
    skip_reason: Optional[str] = None
    timestamp: Optional[str] = None


class SignalGenerator:
    """Unified orchestrator for all signal generation engines."""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        self.trend_analyzer = TrendAnalyzer(
            ema_fast=self.config.get('ema_fast', 50),
            ema_slow=self.config.get('ema_slow', 200)
        )
        
        self.sr_detector = SupportResistanceDetector(
            lookback=self.config.get('sr_lookback', 3),
            cluster_tolerance=self.config.get('sr_tolerance', 0.0005),
            min_touches=self.config.get('sr_min_touches', 2)
        )
        
        self.breakout_engine = BreakoutEngine(
            compression_candles=self.config.get('compression_candles', (20, 40)),
            atr_threshold=self.config.get('atr_threshold', 1.5),
            min_body_ratio=self.config.get('min_body_ratio', 0.6),
            max_wick_ratio=self.config.get('max_wick_ratio', 0.25)
        )
        
        self.sweep_detector = LiquiditySweepDetector(
            wick_touch_tolerance=self.config.get('wick_tolerance', 0.001),
            min_closure_ratio=self.config.get('min_closure_ratio', 0.5)
        )
        
        self.pa_analyzer = PriceActionAnalyzer(
            min_confirmations=self.config.get('min_confirmations', 2)
        )
        
        self.min_signal_strength = self.config.get('min_signal_strength', 0.5)
        self.max_spread_points = self.config.get('max_spread_points', 50)
        self.atr_multiplier_tp1 = self.config.get('atr_multiplier_tp1', 1.5)
        self.atr_multiplier_tp2 = self.config.get('atr_multiplier_tp2', 2.5)

    def generate_signal(self, symbol: str, m5_candles: List, m15_candles: List,
                       h1_candles: List, current_bid_ask_spread: float = 0) -> SignalResult:
        """
        Generate comprehensive trade signal from all engines.
        
        Returns: SignalResult with direction, prices, strength, and component scores
        """
        
        if not m5_candles or not m15_candles or not h1_candles:
            return SignalResult(
                symbol=symbol,
                direction='NONE',
                entry_price=0,
                stop_loss=0,
                tp1=0,
                tp2=0,
                signal_strength=0.0,
                confirmation_count=0,
                component_scores={},
                skip_reason='insufficient_data'
            )
        
        current_candle = m5_candles[-1]
        entry_price = (current_candle['high'] + current_candle['low']) / 2
        
        spread_check = current_bid_ask_spread > self.max_spread_points
        if spread_check:
            return SignalResult(
                symbol=symbol,
                direction='NONE',
                entry_price=entry_price,
                stop_loss=0,
                tp1=0,
                tp2=0,
                signal_strength=0.0,
                confirmation_count=0,
                component_scores={},
                skip_reason='spread_too_wide'
            )
        
        trend_result = self.trend_analyzer.get_trend_confirmation(m15_candles, h1_candles[-1])
        
        sr_zones = self.sr_detector.get_zones(m5_candles)
        
        breakout_result = self.breakout_engine.generate_breakout_signal(m5_candles)
        
        sweep_result = self.sweep_detector.detect_sweep(m5_candles, sr_zones)
        
        ema_values = None
        try:
            closes = np.array([c['close'] for c in m5_candles])
            ema_values = self.trend_analyzer.calculate_ema(closes, 50)
        except Exception:
            ema_values = None
        
        pa_result = self.pa_analyzer.calculate_confirmation_score(
            m5_candles,
            sr_zones=sr_zones,
            ema_values=ema_values
        )
        
        component_scores = {
            'trend_strength': 0.7 if trend_result['confirmed'] else 0.3,
            'breakout_score': breakout_result['strength'],
            'sweep_score': sweep_result['score'],
            'pa_score': pa_result['confirmation_score'],
            'trend_direction': trend_result['m15_trend'],
            'h1_bias': trend_result['h1_bias']
        }
        
        if breakout_result['signal'] == 'NONE':
            return SignalResult(
                symbol=symbol,
                direction='NONE',
                entry_price=entry_price,
                stop_loss=0,
                tp1=0,
                tp2=0,
                signal_strength=0.0,
                confirmation_count=pa_result['confirmation_count'],
                component_scores=component_scores,
                skip_reason='no_breakout'
            )
        
        final_strength = np.mean([
            component_scores['trend_strength'],
            component_scores['breakout_score'],
            component_scores['sweep_score'],
            component_scores['pa_score']
        ])
        
        confirmation_count = pa_result['confirmation_count']
        
        direction = breakout_result['signal']
        
        atm_tp = self.breakout_engine.calculate_atr(m5_candles, period=14)
        if atm_tp is None:
            atm_tp = abs(current_candle['high'] - current_candle['low'])
        
        if direction == 'LONG':
            recent_lows = [c['low'] for c in m5_candles[-20:]]
            stop_loss = min(recent_lows) - 20 * (current_candle['close'] / 10000)
            tp1 = entry_price + atm_tp * self.atr_multiplier_tp1
            tp2 = entry_price + atm_tp * self.atr_multiplier_tp2
        else:
            recent_highs = [c['high'] for c in m5_candles[-20:]]
            stop_loss = max(recent_highs) + 20 * (current_candle['close'] / 10000)
            tp1 = entry_price - atm_tp * self.atr_multiplier_tp1
            tp2 = entry_price - atm_tp * self.atr_multiplier_tp2
        
        if final_strength < self.min_signal_strength:
            return SignalResult(
                symbol=symbol,
                direction='NONE',
                entry_price=entry_price,
                stop_loss=stop_loss,
                tp1=tp1,
                tp2=tp2,
                signal_strength=final_strength,
                confirmation_count=confirmation_count,
                component_scores=component_scores,
                skip_reason='strength_too_low'
            )
        
        logger.info(f"Signal generated for {symbol}: {direction} at {entry_price:.2f}, "
                   f"strength={final_strength:.3f}, confirmations={confirmation_count}")
        
        return SignalResult(
            symbol=symbol,
            direction=direction,
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            tp1=float(tp1),
            tp2=float(tp2),
            signal_strength=float(final_strength),
            confirmation_count=confirmation_count,
            component_scores=component_scores
        )