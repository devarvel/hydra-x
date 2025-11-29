import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List

from modules.data_streamer import DataStreamer
from modules.exchange_connector import ExchangeConnector
from modules.signal_generator import SignalGenerator
from modules.telegram import TelegramNotifier

# Ensure logs directory exists to avoid FileHandler errors
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/hydra_x_main.log')
    ]
)
logger = logging.getLogger(__name__)


class HydraXBot:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.exchange = ExchangeConnector(self.config)
        self.data_streamer = DataStreamer(self.exchange)
        self.signal_generator = SignalGenerator(self.config)
        self.notifier = TelegramNotifier(self.config)

        self.symbols = self.config.get('symbols', ['BTCUSDT', 'XAUTUSDT'])
        self.timeframes = ['M5', 'M15', 'H1']

        self.current_signals: Dict[str, object] = {}
        self.signal_log: List[Dict] = []

    async def initialize(self):
        logger.info("Initializing HydraX Bot...")
        try:
            await self.exchange.initialize()
            logger.info("Exchange connector initialized")

            await self.data_streamer.initialize()
            logger.info("Data streamer initialized")

            await self.notifier.initialize()
            logger.info("Telegram notifier initialized")

            for symbol in self.symbols:
                self.current_signals[symbol] = None

            logger.info("Bot initialization complete")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100):
        try:
            candles = await self.data_streamer.get_candles(symbol, timeframe, limit)
            return candles
        except Exception as e:
            logger.warning(f"Error fetching {symbol} {timeframe}: {e}")
            return []

    async def process_signal(self, symbol: str):
        try:
            m5_candles = await self.fetch_candles(symbol, 'M5', 100)
            m15_candles = await self.fetch_candles(symbol, 'M15', 100)
            h1_candles = await self.fetch_candles(symbol, 'H1', 100)

            if not (m5_candles and m15_candles and h1_candles):
                logger.warning(f"Incomplete candle data for {symbol}")
                return

            spread = await self.exchange.get_spread(symbol)

            signal = self.signal_generator.generate_signal(
                symbol,
                m5_candles,
                m15_candles,
                h1_candles,
                spread,
            )

            self.current_signals[symbol] = signal

            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'symbol': symbol,
                'direction': getattr(signal, 'direction', None),
                'entry_price': getattr(signal, 'entry_price', None),
                'stop_loss': getattr(signal, 'stop_loss', None),
                'tp1': getattr(signal, 'tp1', None),
                'tp2': getattr(signal, 'tp2', None),
                'signal_strength': getattr(signal, 'signal_strength', None),
                'confirmation_count': getattr(signal, 'confirmation_count', None),
                'component_scores': getattr(signal, 'component_scores', None),
                'skip_reason': getattr(signal, 'skip_reason', None),
            }

            self.signal_log.append(log_entry)

            # Log a concise summary if the signal has numeric attributes
            strength = getattr(signal, 'signal_strength', None)
            conf = getattr(signal, 'confirmation_count', None)
            try:
                strength_str = f"strength={strength:.3f}" if isinstance(strength, (int, float)) else f"strength={strength}"
            except Exception:
                strength_str = f"strength={strength}"

            logger.info(
                f"Signal processed for {symbol}: {getattr(signal, 'direction', None)} (" 
                f"{strength_str}, confirmations={conf})"
            )
        except Exception as e:
            logger.error(f"Error processing signal for {symbol}: {e}")

    async def run_event_loop(self):
        logger.info("Starting bot event loop...")
        signal_interval = self.config.get('signal_interval', 5)

        try:
            iteration = 0
            while True:
                iteration += 1

                for symbol in self.symbols:
                    await self.process_signal(symbol)

                if iteration % 12 == 0:
                    logger.info(f"Bot running normally. Signals: {len(self.signal_log)} total")

                await asyncio.sleep(signal_interval)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        try:
            logger.info("Shutting down bot...")
            await self.exchange.close()
            await self.data_streamer.close()
            await self.notifier.shutdown()
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

    def get_current_signals(self) -> Dict:
        return self.current_signals

    def get_signal_history(self, limit: int = 100) -> List[Dict]:
        return self.signal_log[-limit:]


async def main():
    from utils import load_config

    try:
        config = load_config('config.yaml')

        bot = HydraXBot(config)
        await bot.initialize()

        await bot.run_event_loop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
    logger.info("Shutting down...")
