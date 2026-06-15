"""
TradingView Signal Parser - Parses and validates TradingView webhook alerts
"""
import logging
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """Parsed trading signal"""
    action: str  # BUY, SELL, CLOSE
    symbol: str
    volume: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    order_type: Optional[str] = None  # market, limit, stop
    comment: str = ""


class TradingViewParser:
    """Parser for TradingView webhook signals"""

    def __init__(self):
        self.symbols = Config.SYMBOLS
        self.buy_keywords = Config.BUY_KEYWORDS
        self.sell_keywords = Config.SELL_KEYWORDS
        self.close_keywords = Config.CLOSE_KEYWORDS

    def parse(self, data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Parse TradingView webhook data into a TradingSignal

        Supports multiple TradingView alert formats:
        1. JSON with structured fields
        2. Plain text with keyword patterns
        3. Pine Script variable references
        """
        if isinstance(data, str):
            return self._parse_text(data)

        if not isinstance(data, dict):
            logger.warning(f"Unsupported data type: {type(data)}")
            return None

        # Try standard JSON format first
        signal = self._parse_json(data)
        if signal:
            return signal

        # Try text field parsing
        if "text" in data or "message" in data or "body" in data:
            text = data.get("text") or data.get("message") or data.get("body", "")
            return self._parse_text(str(text))

        logger.warning(f"Could not parse signal data: {data}")
        return None

    def _parse_json(self, data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Parse structured JSON format"""
        # Normalize field names (case insensitive)
        normalized = {k.lower(): v for k, v in data.items()}

        # Extract action
        action = self._extract_action(normalized)
        if not action:
            return None

        # Extract symbol
        symbol = self._extract_symbol(normalized)
        if not symbol:
            return None

        # Extract volume
        volume = self._extract_volume(normalized)

        # Extract SL/TP
        stop_loss = self._extract_price(normalized.get("sl") or normalized.get("stoploss") or normalized.get("stop_loss") or normalized.get("stop"))
        take_profit = self._extract_price(normalized.get("tp") or normalized.get("takeprofit") or normalized.get("take_profit") or normalized.get("target"))

        # Extract optional fields
        comment = str(normalized.get("comment", "") or "")
        order_type = (normalized.get("type") or normalized.get("ordertype") or "market")
        if order_type:
            order_type = str(order_type).lower()
        else:
            order_type = "market"

        return TradingSignal(
            action=action,
            symbol=symbol,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_type=order_type,
            comment=comment,
        )

    def _parse_text(self, text: str) -> Optional[TradingSignal]:
        """Parse plain text alerts with keyword patterns"""
        text_lower = text.lower()

        # Determine action
        action = None
        for keyword in self.close_keywords:
            if keyword.lower() in text_lower:
                action = "CLOSE"
                break

        if not action:
            for keyword in self.buy_keywords:
                if keyword.lower() in text_lower:
                    action = "BUY"
                    break

        if not action:
            for keyword in self.sell_keywords:
                if keyword.lower() in text_lower:
                    action = "SELL"
                    break

        if not action:
            logger.warning(f"No valid action found in text: {text}")
            return None

        # Extract symbol
        symbol = self._extract_symbol_from_text(text)
        if not symbol:
            return None

        # Extract volume
        volume = self._extract_volume_from_text(text)

        # Extract SL/TP
        stop_loss = self._extract_sl_tp_from_text(text, "sl")
        take_profit = self._extract_sl_tp_from_text(text, "tp")

        return TradingSignal(
            action=action,
            symbol=symbol,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _extract_action(self, data: Dict[str, str]) -> Optional[str]:
        """Extract trading action from data"""
        action_field = data.get("action") or data.get("signal") or data.get("direction") or data.get("cmd")

        if not action_field:
            return None

        try:
            action_str = str(action_field).lower()
        except (ValueError, TypeError):
            return None

        for keyword in self.close_keywords:
            if keyword.lower() in action_str:
                return "CLOSE"

        for keyword in self.buy_keywords:
            if keyword.lower() in action_str:
                return "BUY"

        for keyword in self.sell_keywords:
            if keyword.lower() in action_str:
                return "SELL"

        return None

    def _extract_symbol(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract trading symbol from data"""
        # Try common field names
        raw_symbol = data.get("symbol") or data.get("ticker") or data.get("s") or data.get("sym")

        # Handle None or empty values
        if not raw_symbol:
            return None

        # Convert to string and normalize
        try:
            symbol = str(raw_symbol).upper().strip()
        except (ValueError, TypeError):
            logger.warning(f"Invalid symbol value: {raw_symbol}")
            return None

        if not symbol or symbol == "NONE":
            return None

        # Check if symbol exists in our mapping
        if symbol in self.symbols:
            return self.symbols[symbol]

        # Check without mapping (direct symbol)
        if symbol in self.symbols.values():
            return symbol

        # Try partial match
        for tv_symbol, mt5_symbol in self.symbols.items():
            if symbol == tv_symbol or symbol == mt5_symbol:
                return mt5_symbol

        # Return as-is if not in mapping (might be valid MT5 symbol)
        return symbol

    def _extract_symbol_from_text(self, text: str) -> Optional[str]:
        """Extract symbol from plain text using regex patterns"""
        text_upper = text.upper()

        # Pattern 1: Explicit symbol keyword
        patterns = [
            r"\bSYMBOL[:\s=]+([A-Z]{3,6}[A-Z0-9]*)\b",
            r"\bTICKER[:\s=]+([A-Z]{3,6}[A-Z0-9]*)\b",
            r"\b([A-Z]{6})\b",  # 6-char symbols like EURUSD
            r"\b([A-Z]{3}[/][A-Z]{3})\b",  # Forex format EUR/USD
        ]

        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                symbol = match.group(1).replace("/", "")
                # Validate against known symbols
                if symbol in self.symbols or symbol in self.symbols.values():
                    return self.symbols.get(symbol, symbol)
                # Return anyway if it looks like a valid symbol
                if len(symbol) >= 6:
                    return symbol

        return None

    def _extract_volume(self, data: Dict[str, Any]) -> float:
        """Extract volume/lot size from data"""
        volume_field = data.get("volume") or data.get("lotsize") or data.get("lot") or data.get("v") or data.get("q")

        if volume_field is None:
            return Config.DEFAULT_LOT

        try:
            volume = float(volume_field)
            if volume <= 0:
                return Config.DEFAULT_LOT
            return min(volume, Config.MAX_LOT_SIZE)  # Cap at max lot
        except (ValueError, TypeError):
            return Config.DEFAULT_LOT

    def _extract_volume_from_text(self, text: str) -> float:
        """Extract volume from plain text"""
        patterns = [
            r"\bVOLUME[:\s=]+([0-9.]+)",
            r"\bLOT[S]?[:\s=]+([0-9.]+)",
            r"\b([0-9.]+)\s*LOT",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    volume = float(match.group(1))
                    return min(volume, Config.MAX_LOT_SIZE)
                except ValueError:
                    continue

        return Config.DEFAULT_LOT

    def _extract_price(self, value) -> Optional[float]:
        """Extract and validate price value"""
        if not value or value == 0:
            return None

        try:
            price = float(value)
            return price if price > 0 else None
        except (ValueError, TypeError):
            return None

    def _extract_sl_tp_from_text(self, text: str, field: str) -> Optional[float]:
        """Extract SL/TP from plain text"""
        patterns = {
            "sl": [r"\bSL[:\s=]+([0-9.]+)", r"\bSTOP\s*LOSS[:\s=]+([0-9.]+)"],
            "tp": [r"\bTP[:\s=]+([0-9.]+)", r"\bTAKE\s*PROFIT[:\s=]+([0-9.]+)", r"\bTARGET[:\s=]+([0-9.]+)"],
        }

        for pattern in patterns.get(field, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue

        return None

    def validate_signal(self, signal: TradingSignal) -> Tuple[bool, Optional[str]]:
        """Validate a parsed signal"""
        if not signal.action:
            return False, "Missing action"

        if not signal.symbol:
            return False, "Missing symbol"

        if signal.volume <= 0:
            return False, "Invalid volume"

        if signal.stop_loss and signal.stop_loss <= 0:
            return False, "Invalid stop loss"

        if signal.take_profit and signal.take_profit <= 0:
            return False, "Invalid take profit"

        return True, None
