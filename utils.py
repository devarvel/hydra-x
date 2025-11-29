import os
import sys
import json
import logging
import asyncio
import signal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml
from dotenv import load_dotenv
import colorlog

load_dotenv()

_shutdown_event = None

def setup_logging(log_dir: str, level: str = "INFO", console_enabled: bool = True) -> logging.Logger:
    """Setup logging with file rotation and colored console output."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"hydra_x_{today}.log")
    
    logger = logging.getLogger("hydra_x")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        color_formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s]%(reset)s [%(levelname)s] [%(name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'blue',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(color_formatter)
        logger.addHandler(console_handler)
    
    return logger

def load_config(config_path: str) -> Dict[str, Any]:
    """Load YAML configuration file with environment variable support."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    config['api']['api_key'] = os.getenv('API_KEY', config['api'].get('api_key', ''))
    config['api']['api_secret'] = os.getenv('API_SECRET', config['api'].get('api_secret', ''))
    config['api']['passphrase'] = os.getenv('API_PASSPHRASE', config['api'].get('passphrase', ''))
    config['telegram']['token'] = os.getenv('TELEGRAM_TOKEN', config['telegram'].get('token', ''))
    config['telegram']['chat_id'] = os.getenv('TELEGRAM_CHAT_ID', config['telegram'].get('chat_id', ''))
    
    validate_config(config)
    return config

def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration parameters."""
    required_fields = ['exchange', 'symbols', 'risk_management', 'api']
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required configuration field: {field}")
    
    risk_cfg = config['risk_management']
    if not (1.5 <= risk_cfg.get('risk_percent', 1.75) <= 2.0):
        raise ValueError("risk_percent must be between 1.5 and 2.0")
    
    if not (1 <= risk_cfg.get('min_confirmations', 2) <= 3):
        raise ValueError("min_confirmations must be between 1 and 3")
    
    if risk_cfg.get('max_spread_points', 50) <= 0:
        raise ValueError("max_spread_points must be positive")

def get_current_utc_time() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)

def is_market_hours(symbol: str, config: Dict[str, Any]) -> bool:
    """Check if current time is within trading hours for symbol."""
    now = get_current_utc_time()
    
    if symbol == "XAUTUSDT":
        london_start = datetime.strptime(config['session']['xau_london_start'], "%H:%M").time()
        london_end = datetime.strptime(config['session']['xau_london_end'], "%H:%M").time()
        ny_start = datetime.strptime(config['session']['xau_ny_start'], "%H:%M").time()
        ny_end = datetime.strptime(config['session']['xau_ny_end'], "%H:%M").time()
        
        current_time = now.time()
        in_london = london_start <= current_time <= london_end
        in_ny = ny_start <= current_time <= ny_end
        
        return in_london or in_ny
    
    if symbol == "BTCUSDT" and config['session']['btc_trading_24h']:
        return True
    
    return True

def is_weekend() -> bool:
    """Check if current time is weekend."""
    now = get_current_utc_time()
    return now.weekday() >= 4

def round_to_precision(value: float, decimals: int) -> float:
    """Round value to specified decimal precision."""
    return round(value, decimals)

def validate_ohlc_data(candle: Dict[str, float]) -> bool:
    """Validate OHLC candle data integrity."""
    required_keys = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    if not all(key in candle for key in required_keys):
        return False
    
    o, h, l, c, v = candle['open'], candle['high'], candle['low'], candle['close'], candle['volume']
    
    if h < l or h < o or h < c or l > o or l > c:
        return False
    
    if v < 0:
        return False
    
    if any(not isinstance(candle[k], (int, float)) for k in required_keys[:-1]):
        return False
    
    return True

def save_state_to_json(data: Any, filepath: str) -> None:
    """Save state data to JSON file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def load_state_from_json(filepath: str) -> Optional[Any]:
    """Load state data from JSON file."""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)

def setup_graceful_shutdown(logger: logging.Logger) -> asyncio.Event:
    """Setup graceful shutdown handler for SIGINT."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info("Graceful shutdown initiated by user (SIGINT)")
        _shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    return _shutdown_event

def get_logger(name: str) -> logging.Logger:
    """Get logger instance for a module."""
    return logging.getLogger(f"hydra_x.{name}")

def seconds_until_next_candle(timeframe: str) -> int:
    """Calculate seconds until next candle opens."""
    now = get_current_utc_time()
    
    timeframe_seconds = {
        'M1': 60, 'M5': 300, 'M15': 900, 'H1': 3600, 'H4': 14400, 'D': 86400
    }
    
    if timeframe not in timeframe_seconds:
        return 0
    
    tf_seconds = timeframe_seconds[timeframe]
    timestamp = now.timestamp()
    seconds_into_candle = timestamp % tf_seconds
    return int(tf_seconds - seconds_into_candle)

def calculate_percentage_change(old_val: float, new_val: float) -> float:
    """Calculate percentage change between two values."""
    if old_val == 0:
        return 0.0
    return ((new_val - old_val) / abs(old_val)) * 100