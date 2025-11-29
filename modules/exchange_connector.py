import asyncio
import logging
from typing import Dict, List, Optional, Any
from utils import get_logger

try:
    import ccxt.pro as ccxt_pro
    HAS_CCXT_PRO = True
except ImportError:
    HAS_CCXT_PRO = False

import ccxt

logger = get_logger("exchange_connector")

class ExchangeConnector:
    """Handle exchange connectivity with automatic failover and testnet support."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchange_hierarchy = ['bybit', 'okx', 'mexc', 'gate', 'binance']
        self.exchange = None
        self.exchange_name = None
        
    async def connect(self) -> bool:
        """Attempt to connect to configured exchange with failover."""
        preferred_exchange = self.config['exchange'].lower()
        
        if preferred_exchange in self.exchange_hierarchy:
            if await self._try_connect(preferred_exchange):
                return True
        
        for exchange_name in self.exchange_hierarchy:
            if exchange_name != preferred_exchange:
                if await self._try_connect(exchange_name):
                    return True
        
        logger.error("Failed to connect to any exchange in hierarchy")
        return False
    
    async def _try_connect(self, exchange_name: str) -> bool:
        """Attempt connection to specific exchange."""
        try:
            exchange_class = getattr(ccxt, exchange_name)
            
            exchange_config = {
                'apiKey': self.config['api'].get('api_key', ''),
                'secret': self.config['api'].get('api_secret', ''),
                'enableRateLimit': True,
                'timeout': 30000,
            }
            
            if exchange_name == 'okx':
                exchange_config['password'] = self.config['api'].get('passphrase', '')
            
            if self.config['api'].get('testnet', True):
                exchange_config['sandboxMode'] = True
                if hasattr(exchange_class, 'has') and 'sandbox' in exchange_class.has:
                    logger.info(f"Connecting to {exchange_name} testnet")
            
            self.exchange = exchange_class(exchange_config)
            self.exchange_name = exchange_name
            
            await self._test_connection()
            logger.info(f"Successfully connected to {exchange_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to connect to {exchange_name}: {e}")
            return False
    
    async def _test_connection(self) -> None:
        """Test exchange connection with ping."""
        try:
            ticker = self.exchange.fetch_ticker(self.config['symbols'][0])
            logger.info(f"Exchange connection test successful - {self.config['symbols'][0]} price: {ticker['last']}")
        except Exception as e:
            raise Exception(f"Connection test failed: {e}")
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert standard timeframe format to exchange-specific format."""
        timeframe_map = {
            'M1': {'bybit': '1', 'okx': '1m', 'mexc': '1m', 'gate': '1m', 'binance': '1m'},
            'M5': {'bybit': '5', 'okx': '5m', 'mexc': '5m', 'gate': '5m', 'binance': '5m'},
            'M15': {'bybit': '15', 'okx': '15m', 'mexc': '15m', 'gate': '15m', 'binance': '15m'},
            'M30': {'bybit': '30', 'okx': '30m', 'mexc': '30m', 'gate': '30m', 'binance': '30m'},
            'H1': {'bybit': '60', 'okx': '1h', 'mexc': '1h', 'gate': '1h', 'binance': '1h'},
            'H4': {'bybit': '240', 'okx': '4h', 'mexc': '4h', 'gate': '4h', 'binance': '4h'},
            'D': {'bybit': 'D', 'okx': '1D', 'mexc': '1D', 'gate': '1d', 'binance': '1d'},
        }
        
        if timeframe not in timeframe_map:
            return timeframe
        
        exchange_name = self.exchange_name.lower()
        if exchange_name not in timeframe_map[timeframe]:
            return timeframe
        
        return timeframe_map[timeframe][exchange_name]
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """Fetch historical OHLCV data."""
        try:
            converted_tf = self._convert_timeframe(timeframe)
            return self.exchange.fetch_ohlcv(symbol, converted_tf, limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol} {timeframe}: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data."""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            raise
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise
    
    def get_exchange_name(self) -> str:
        """Get current connected exchange name."""
        return self.exchange_name