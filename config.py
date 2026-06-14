"""
Configuration file for MT5 Trading Connector
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # MT5 Connection Settings
    MT5_PATH = os.getenv("MT5_PATH", "C:\\Program Files\\MetaTrader 5\\terminal64.exe")

    # Trading Settings
    DEFAULT_LOT = float(os.getenv("DEFAULT_LOT", "0.1"))
    DEFAULT_SLIPPAGE = int(os.getenv("DEFAULT_SLIPPAGE", "10"))
    DEFAULT_MAGIC_NUMBER = int(os.getenv("DEFAULT_MAGIC_NUMBER", "20240615"))

    # Risk Management
    MAX_LOT_SIZE = float(os.getenv("MAX_LOT_SIZE", "1.0"))
    MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))

    # Flask Settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "80"))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # TradingView Alert Settings
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # Optional: for webhook authentication
    ENABLE_AUTH = os.getenv("ENABLE_AUTH", "False").lower() == "true"

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "trading.log")

    # Symbols Mapping (TradingView symbol -> MT5 symbol)
    SYMBOLS = {
        # Forex
        "EURUSD": "EURUSD",
        "GBPUSD": "GBPUSD",
        "USDJPY": "USDJPY",
        "USDCHF": "USDCHF",
        "AUDUSD": "AUDUSD",
        "USDCAD": "USDCAD",
        "NZDUSD": "NZDUSD",
        "EURGBP": "EURGBP",
        "EURJPY": "EURJPY",
        "GBPJPY": "GBPJPY",
        # Commodities
        "XAUUSD": "XAUUSD",
        "XAGUSD": "XAGUSD",
        "USOIL": "USOIL",
        "UKOIL": "UKOIL",
        # Indices
        "US100": "US100",
        "US30": "US30",
        "GER40": "GER40",
    }

    # Action Keywords Mapping
    BUY_KEYWORDS = ["buy", "long", "做多", "买入", "多"]
    SELL_KEYWORDS = ["sell", "short", "做空", "卖出", "空"]
    CLOSE_KEYWORDS = ["close", "exit", "平仓", "平", "close_all"]
