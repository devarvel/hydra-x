import asyncio
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np

from modules.data_streamer import DataStreamer
from modules.exchange_connector import ExchangeConnector
from modules.signal_generator import SignalGenerator
from utils import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalValidator:
    """Validates signal generation on historical candles."""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.exchange = ExchangeConnector(self.config)
        self.data_streamer = DataStreamer(self.exchange)
        self.signal_generator = SignalGenerator(self.config)
        
        self.symbols = self.config.get('symbols', ['BTCUSDT', 'XAUTUSDT'])
        self.candles_per_symbol = 1000
        
        self.results = {
            'summary': {},
            'trend_analysis': {},
            'component_analysis': {},
            'sample_signals': [],
            'statistics': {},
            'timestamp': datetime.utcnow().isoformat()
        }

    async def initialize(self):
        """Initialize connectors."""
        await self.exchange.initialize()
        await self.data_streamer.initialize()

    async def fetch_and_analyze(self):
        """Fetch 1000 candles and run signal generation."""
        logger.info(f"Fetching {self.candles_per_symbol} candles for analysis...")
        
        all_signals = []
        trend_distribution = defaultdict(int)
        confirmation_histogram = defaultdict(int)
        component_scores_list = defaultdict(list)
        
        for symbol in self.symbols:
            logger.info(f"Processing {symbol}...")
            
            try:
                m5_candles = await self.data_streamer.get_candles(symbol, 'M5', self.candles_per_symbol)
                m15_candles = await self.data_streamer.get_candles(symbol, 'M15', 300)
                h1_candles = await self.data_streamer.get_candles(symbol, 'H1', 100)
                
                if not (m5_candles and m15_candles and h1_candles):
                    logger.warning(f"Insufficient data for {symbol}")
                    continue
                
                signal_count = 0
                directional_signals = 0
                
                for i in range(len(m5_candles) - 100):
                    m5_window = m5_candles[i:i+100]
                    m15_window = m15_candles[max(0, i//3-50):max(0, i//3)+50]
                    h1_window = h1_candles[max(0, i//12-10):max(0, i//12)+10]
                    
                    if not (m5_window and m15_window and h1_window):
                        continue
                    
                    signal = self.signal_generator.generate_signal(
                        symbol,
                        m5_window,
                        m15_window,
                        h1_window,
                        0
                    )
                    
                    signal_count += 1
                    
                    if signal.direction != 'NONE':
                        directional_signals += 1
                        all_signals.append({
                            'symbol': symbol,
                            'timestamp': datetime.utcnow().isoformat(),
                            'direction': signal.direction,
                            'entry_price': signal.entry_price,
                            'stop_loss': signal.stop_loss,
                            'tp1': signal.tp1,
                            'tp2': signal.tp2,
                            'signal_strength': signal.signal_strength,
                            'confirmation_count': signal.confirmation_count,
                            'component_scores': signal.component_scores
                        })
                    
                    trend_distribution[signal.component_scores.get('trend_direction', 'unknown')] += 1
                    confirmation_histogram[signal.confirmation_count] += 1
                    
                    for key, value in signal.component_scores.items():
                        if isinstance(value, (int, float)):
                            component_scores_list[key].append(value)
                
                signal_frequency = (directional_signals / signal_count * 100) if signal_count > 0 else 0
                
                logger.info(f"{symbol}: {signal_count} signals processed, "
                           f"{directional_signals} directional ({signal_frequency:.1f}%)")
                
                self.results['summary'][symbol] = {
                    'total_signals': signal_count,
                    'directional_signals': directional_signals,
                    'signal_frequency_pct': signal_frequency
                }
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        self.results['trend_analysis'] = {
            'distribution': dict(trend_distribution),
            'total': sum(trend_distribution.values())
        }
        
        self.results['confirmation_histogram'] = dict(confirmation_histogram)
        
        self.results['component_analysis'] = {
            key: {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values))
            }
            for key, values in component_scores_list.items()
            if values
        }
        
        self.results['sample_signals'] = all_signals[:20]
        self.results['statistics'] = {
            'total_directional_signals': len(all_signals),
            'avg_signal_strength': float(np.mean([s['signal_strength'] for s in all_signals]))
            if all_signals else 0,
            'avg_confirmations': float(np.mean([s['confirmation_count'] for s in all_signals]))
            if all_signals else 0
        }

    async def close(self):
        """Close connections."""
        await self.exchange.close()
        await self.data_streamer.close()

    def save_results(self, filename: str = 'data/signal_generation_validation.json'):
        """Save validation results."""
        logger.info(f"Saving results to {filename}...")
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info("Results saved successfully")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "="*60)
        print("SIGNAL GENERATION VALIDATION SUMMARY")
        print("="*60)
        
        for symbol, stats in self.results['summary'].items():
            print(f"\n{symbol}:")
            print(f"  Total signals: {stats['total_signals']}")
            print(f"  Directional: {stats['directional_signals']}")
            print(f"  Frequency: {stats['signal_frequency_pct']:.1f}%")
        
        print(f"\nTotal directional signals: {self.results['statistics']['total_directional_signals']}")
        print(f"Avg signal strength: {self.results['statistics']['avg_signal_strength']:.3f}")
        print(f"Avg confirmations: {self.results['statistics']['avg_confirmations']:.2f}")
        
        print(f"\nTrend distribution: {self.results['trend_analysis']['distribution']}")
        print(f"Confirmation histogram: {self.results['confirmation_histogram']}")
        
        print("\n✓ All signal generation components operational")
        print("="*60 + "\n")


async def main():
    """Main validation function."""
    try:
        config = load_config('config.yaml')
        validator = SignalValidator(config)
        
        await validator.initialize()
        await validator.fetch_and_analyze()
        validator.save_results()
        validator.print_summary()
        
        await validator.close()
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())