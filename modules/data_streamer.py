import asyncio
import logging
from typing import Dict, List, Optional, Any
from collections import deque
from datetime import datetime, timezone
from utils import get_logger, validate_ohlc_data

logger = get_logger("data_streamer")

class DataStreamer:
    """Handle real-time OHLCV data streaming with WebSocket and REST fallback."""
    
    def __init__(self, exchange_connector, config: Dict[str, Any]):
        self.connector = exchange_connector
        self.config = config
        self.candles_cache = {}
        self.cache_size = config['data_streaming'].get('candle_cache_size', 500)
        self.polling_interval = config['data_streaming'].get('polling_interval', 2)
        self.reconnect_max_delay = config['data_streaming'].get('reconnect_max_delay', 60)
        self.validation_enabled = config['data_streaming'].get('validation_enabled', True)
        
        self._initialize_cache()
    
    def _initialize_cache(self) -> None:
        """Initialize candle cache for each symbol and timeframe."""
        for symbol in self.config['symbols']:
            self.candles_cache[symbol] = {}
            for timeframe in self.config['timeframes']:
                self.candles_cache[symbol][timeframe] = deque(maxlen=self.cache_size)
    
    async def fetch_historical_candles(self, symbol: str, timeframe: str, limit: int = 100) -> bool:
        """Fetch historical OHLCV data and populate cache."""
        try:
            candles = await self.connector.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            for candle in candles:
                candle_dict = self._format_candle(candle, timeframe)
                
                if self.validation_enabled and not validate_ohlc_data(candle_dict):
                    logger.warning(f"Invalid candle data for {symbol} {timeframe}: {candle_dict}")
                    continue
                
                self.candles_cache[symbol][timeframe].append(candle_dict)
            
            logger.info(f"Loaded {len(self.candles_cache[symbol][timeframe])} candles for {symbol} {timeframe}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fetch historical candles for {symbol} {timeframe}: {e}")
            return False
    
    def _format_candle(self, candle: List, timeframe: str) -> Dict[str, Any]:
        """Format ccxt candle data to standardized format."""
        return {
            'timestamp': candle[0],
            'open': candle[1],
            'high': candle[2],
            'low': candle[3],
            'close': candle[4],
            'volume': candle[5],
            'datetime': datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
            'timeframe': timeframe
        }
    
    async def stream_real_time_candles(self, symbol: str, timeframe: str) -> None:
        """Stream real-time candles via polling (REST fallback)."""
        reconnect_delay = 1
        
        while True:
            try:
                candles = await self.connector.fetch_ohlcv(symbol, timeframe, limit=5)
                
                for candle in candles:
                    candle_dict = self._format_candle(candle, timeframe)
                    
                    if self.validation_enabled and not validate_ohlc_data(candle_dict):
                        logger.warning(f"Invalid real-time candle for {symbol} {timeframe}")
                        continue
                    
                    self.candles_cache[symbol][timeframe].append(candle_dict)
                
                reconnect_delay = 1
                await asyncio.sleep(self.polling_interval)
                
            except Exception as e:
                logger.error(f"Error streaming {symbol} {timeframe}: {e}")
                await asyncio.sleep(min(reconnect_delay, self.reconnect_max_delay))
                reconnect_delay *= 2
    
    def get_candles(self, symbol: str, timeframe: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get cached candles for symbol and timeframe."""
        if symbol not in self.candles_cache or timeframe not in self.candles_cache[symbol]:
            return []
        
        candles = list(self.candles_cache[symbol][timeframe])
        
        if count and len(candles) > count:
            return candles[-count:]
        
        return candles
    
    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Get most recent candle for symbol and timeframe."""
        candles = self.get_candles(symbol, timeframe, count=1)
        return candles[0] if candles else None
    
    def get_cache_size(self, symbol: str, timeframe: str) -> int:
        """Get current cache size for symbol and timeframe."""
        if symbol not in self.candles_cache or timeframe not in self.candles_cache[symbol]:
            return 0
        return len(self.candles_cache[symbol][timeframe])