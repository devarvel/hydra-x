"""Foundation Infrastructure Validation Script - v2."""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/app/hydra_x_v2_1804')

from utils import setup_logging, load_config, get_logger
from modules.exchange_connector import ExchangeConnector
from modules.data_streamer import DataStreamer

async def run_validation():
    """Run comprehensive foundation validation."""
    
    logger = setup_logging(
        log_dir="/app/hydra_x_v2_1804/logs",
        level="INFO",
        console_enabled=True
    )
    
    validation_results = {
        'timestamp': datetime.utcnow().isoformat(),
        'tests': {},
        'overall_status': 'PASS'
    }
    
    try:
        logger.info("\n" + "=" * 80)
        logger.info("FOUNDATION INFRASTRUCTURE VALIDATION - v2")
        logger.info("=" * 80)
        
        logger.info("\n[TEST 1/8] Loading Configuration...")
        try:
            config = load_config('/app/hydra_x_v2_1804/config.yaml')
            logger.info("✓ Configuration loaded successfully")
            logger.info(f"  - Exchange: {config['exchange']}")
            logger.info(f"  - Symbols: {config['symbols']}")
            logger.info(f"  - Timeframes: {config['timeframes']}")
            logger.info(f"  - Risk percent: {config['risk_management']['risk_percent']}%")
            validation_results['tests']['config_loading'] = 'PASS'
        except Exception as e:
            logger.error(f"✗ Configuration loading failed: {e}")
            validation_results['tests']['config_loading'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
            return False
        
        logger.info("\n[TEST 2/8] Directory Structure...")
        required_dirs = [
            '/app/hydra_x_v2_1804/modules',
            '/app/hydra_x_v2_1804/data',
            '/app/hydra_x_v2_1804/logs'
        ]
        dirs_ok = True
        for dir_path in required_dirs:
            if os.path.isdir(dir_path):
                logger.info(f"✓ {dir_path}")
            else:
                logger.error(f"✗ Missing: {dir_path}")
                dirs_ok = False
        validation_results['tests']['directory_structure'] = 'PASS' if dirs_ok else 'FAIL'
        if not dirs_ok:
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n[TEST 3/8] Module Files...")
        required_modules = [
            '/app/hydra_x_v2_1804/main.py',
            '/app/hydra_x_v2_1804/utils.py',
            '/app/hydra_x_v2_1804/indicators.py',
            '/app/hydra_x_v2_1804/config.yaml',
            '/app/hydra_x_v2_1804/requirements.txt',
        ]
        modules_ok = True
        for module_path in required_modules:
            if os.path.isfile(module_path):
                logger.info(f"✓ {module_path}")
            else:
                logger.error(f"✗ Missing: {module_path}")
                modules_ok = False
        validation_results['tests']['module_files'] = 'PASS' if modules_ok else 'FAIL'
        if not modules_ok:
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n[TEST 4/8] Exchange Connectivity...")
        connector = None
        try:
            connector = ExchangeConnector(config)
            if await connector.connect():
                logger.info(f"✓ Connected to {connector.get_exchange_name()} exchange")
                validation_results['tests']['exchange_connectivity'] = 'PASS'
            else:
                logger.error("✗ Exchange connection failed")
                validation_results['tests']['exchange_connectivity'] = 'FAIL'
                validation_results['overall_status'] = 'FAIL'
        except Exception as e:
            logger.error(f"✗ Exchange connection error: {e}")
            validation_results['tests']['exchange_connectivity'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
        
        if not connector:
            logger.error("Cannot proceed without exchange connection")
            return False
        
        logger.info("\n[TEST 5/8] Historical Data Fetching...")
        try:
            streamer = DataStreamer(connector, config)
            data_ok = True
            for symbol in config['symbols']:
                for timeframe in config['timeframes']:
                    if await streamer.fetch_historical_candles(symbol, timeframe, limit=100):
                        cache_size = streamer.get_cache_size(symbol, timeframe)
                        logger.info(f"✓ {symbol} {timeframe}: {cache_size} candles cached")
                    else:
                        logger.error(f"✗ Failed to fetch {symbol} {timeframe}")
                        data_ok = False
            validation_results['tests']['historical_data'] = 'PASS' if data_ok else 'FAIL'
            if not data_ok:
                validation_results['overall_status'] = 'FAIL'
        except Exception as e:
            logger.error(f"✗ Historical data fetching error: {e}")
            validation_results['tests']['historical_data'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n[TEST 6/8] Data Validation...")
        try:
            validation_ok = True
            for symbol in config['symbols']:
                for timeframe in config['timeframes']:
                    candles = streamer.get_candles(symbol, timeframe)
                    if not candles:
                        logger.error(f"✗ No candles for {symbol} {timeframe}")
                        validation_ok = False
                        continue
                    
                    for candle in candles:
                        if 'open' not in candle or 'close' not in candle:
                            logger.error(f"✗ Invalid candle format for {symbol} {timeframe}")
                            validation_ok = False
                            break
                    
                    if validation_ok:
                        latest = streamer.get_latest_candle(symbol, timeframe)
                        logger.info(f"✓ {symbol} {timeframe}: Latest close = {latest['close']:.2f}")
            
            validation_results['tests']['data_validation'] = 'PASS' if validation_ok else 'FAIL'
            if not validation_ok:
                validation_results['overall_status'] = 'FAIL'
        except Exception as e:
            logger.error(f"✗ Data validation error: {e}")
            validation_results['tests']['data_validation'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n[TEST 7/8] Logging Infrastructure...")
        try:
            log_dir = '/app/hydra_x_v2_1804/logs'
            log_files = os.listdir(log_dir)
            if log_files:
                logger.info(f"✓ Logging infrastructure working ({len(log_files)} log files)")
                for log_file in log_files[:3]:
                    logger.info(f"  - {log_file}")
                validation_results['tests']['logging_infrastructure'] = 'PASS'
            else:
                logger.warning("⚠ No log files found yet")
                validation_results['tests']['logging_infrastructure'] = 'PASS'
        except Exception as e:
            logger.error(f"✗ Logging infrastructure error: {e}")
            validation_results['tests']['logging_infrastructure'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n[TEST 8/8] File Permissions...")
        try:
            test_file = '/app/hydra_x_v2_1804/data/test_write.txt'
            Path('/app/hydra_x_v2_1804/data').mkdir(parents=True, exist_ok=True)
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info("✓ File permissions OK (can write to data directory)")
            validation_results['tests']['file_permissions'] = 'PASS'
        except Exception as e:
            logger.error(f"✗ File permissions error: {e}")
            validation_results['tests']['file_permissions'] = 'FAIL'
            validation_results['overall_status'] = 'FAIL'
        
        logger.info("\n" + "=" * 80)
        logger.info(f"VALIDATION RESULT: {validation_results['overall_status']}")
        logger.info("=" * 80 + "\n")
        
        report_path = '/app/hydra_x_v2_1804/data/foundation_validation_report.json'
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        logger.info(f"Validation report saved to: {report_path}")
        
        return validation_results['overall_status'] == 'PASS'
        
    except Exception as e:
        logger.error(f"Validation script error: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = asyncio.run(run_validation())
    sys.exit(0 if success else 1)