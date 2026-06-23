"""
MT5 Client Wrapper - Handles all MT5 trading operations
"""
import logging
import MetaTrader5 as mt5
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import Config

logger = logging.getLogger(__name__)


class MT5Client:
    """MT5 trading client with connection management and trading operations"""

    # Class-level variable to store supported filling mode
    _supported_filling_mode = None

    def __init__(self):
        self.connected = False
        self.account_info: Optional[Dict] = None

    def _get_supported_filling_mode(self, symbol: str) -> int:
        """Get the supported filling mode for the symbol"""
        if MT5Client._supported_filling_mode is not None:
            return MT5Client._supported_filling_mode

        # Try to get from symbol info
        info = mt5.symbol_info(symbol)
        if info is not None:
            # Check if trade_filling_mode attribute exists (newer MT5 Python versions)
            if hasattr(info, 'filling_mode'):
                filling_mode = info.filling_mode
                if filling_mode & (1 << mt5.ORDER_FILLING_FOK):
                    MT5Client._supported_filling_mode = mt5.ORDER_FILLING_FOK
                elif filling_mode & (1 << mt5.ORDER_FILLING_RETURN):
                    MT5Client._supported_filling_mode = mt5.ORDER_FILLING_RETURN
                elif filling_mode & (1 << mt5.ORDER_FILLING_IOC):
                    MT5Client._supported_filling_mode = mt5.ORDER_FILLING_IOC
                else:
                    MT5Client._supported_filling_mode = mt5.ORDER_FILLING_FOK
                logger.info(f"Supported filling mode from symbol: {MT5Client._supported_filling_mode}")
                return MT5Client._supported_filling_mode

        # Fallback: try RETURN mode first (widely supported), then FOK
        MT5Client._supported_filling_mode = mt5.ORDER_FILLING_RETURN
        logger.info(f"Using fallback filling mode: {MT5Client._supported_filling_mode}")
        return MT5Client._supported_filling_mode

    def connect(self) -> bool:
        """Initialize MT5 connection"""
        if self.connected:
            logger.info("MT5 already connected")
            return True

        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            return False

        self.connected = True
        logger.info("MT5 connected successfully")

        # Get account info
        account = mt5.account_info()
        if account:
            self.account_info = {
                "login": account.login,
                "server": account.server,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "free_margin": account.margin_free,
                "leverage": account.leverage,
            }
            logger.info(f"Account: {account.login} @ {account.server}")

        return True

    def disconnect(self):
        """Shutdown MT5 connection"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 disconnected")

    def is_connected(self) -> bool:
        """Check if MT5 is connected"""
        return self.connected and mt5.terminal_info() is not None

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Resolve symbol name to actual MT5 symbol.
        
        Handles cases where TradingView uses 'XAUUSD' but MT5 has 'XAUUSD.m' or 'XAUUSD+'.
        """
        if not self.is_connected():
            return symbol

        # First, try exact match (case-insensitive)
        all_symbols = mt5.symbols_get()
        if all_symbols is None:
            logger.warning("Failed to get symbols list from MT5")
            return symbol

        # Build a case-insensitive lookup map
        symbol_map = {}
        for s in all_symbols:
            name_upper = s.name.upper()
            if name_upper not in symbol_map:
                symbol_map[name_upper] = s.name

        # Try exact match first
        symbol_upper = symbol.upper()
        if symbol_upper in symbol_map:
            resolved = symbol_map[symbol_upper]
            if resolved != symbol:
                logger.info(f"Resolved symbol '{symbol}' -> '{resolved}' (exact match)")
            return resolved

        # Try partial match: find symbols that start with the input
        # e.g., 'xauusd' matches 'xauusd.m', 'xauusd+'
        partial_matches = []
        for name_upper, actual_name in symbol_map.items():
            if name_upper.startswith(symbol_upper) or name_upper.replace(".", "").replace("+", "").startswith(symbol_upper):
                partial_matches.append(actual_name)

        if partial_matches:
            if len(partial_matches) == 1:
                resolved = partial_matches[0]
                logger.info(f"Resolved symbol '{symbol}' -> '{resolved}' (partial match)")
                return resolved
            else:
                # Multiple matches, prefer shorter names without suffixes
                # Sort by length and pick the shortest (usually the base symbol)
                partial_matches.sort(key=len)
                resolved = partial_matches[0]
                logger.info(f"Resolved symbol '{symbol}' -> '{resolved}' (selected from {partial_matches})")
                return resolved

        logger.warning(f"Could not resolve symbol '{symbol}' in MT5")
        return symbol

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol information"""
        if not self.is_connected():
            return None

        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"Symbol {symbol} not found")
            return None

        return {
            "symbol": info.name,
            "bid": info.bid,
            "ask": info.ask,
            "spread": info.spread,
            "digits": info.digits,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "tick_value": info.trade_tick_value,
            "tick_size": info.trade_tick_size,
        }

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask price"""
        if not self.is_connected():
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions, optionally filtered by symbol"""
        if not self.is_connected():
            return []

        # Resolve symbol before querying positions
        query_symbol = self.resolve_symbol(symbol) if symbol else symbol

        positions = mt5.positions_get(symbol=query_symbol) if query_symbol else mt5.positions_get()
        if positions is None:
            return []

        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "profit": p.profit,
                "magic": p.magic,
                "comment": p.comment,
                "time": datetime.fromtimestamp(p.time),
            }
            for p in positions
        ]

    def get_position_by_ticket(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get position by ticket number"""
        if not self.is_connected():
            return None

        position = mt5.position_get_by_ticket(ticket)
        if position is None:
            return None

        return {
            "ticket": position.ticket,
            "symbol": position.symbol,
            "type": "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": position.volume,
            "price_open": position.price_open,
            "price_current": position.price_current,
            "profit": position.profit,
            "magic": position.magic,
        }

    def buy(
        self,
        symbol: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
        magic: int = None,
    ) -> Optional[Dict[str, Any]]:
        """Open BUY position"""
        if not self.is_connected():
            return {"success": False, "error": "MT5 not connected"}

        # Resolve symbol name to actual MT5 symbol
        symbol = self.resolve_symbol(symbol)

        # Validate symbol
        if not mt5.symbol_select(symbol, True):
            return {"success": False, "error": f"Symbol {symbol} not available"}

        # Get current price
        price_info = self.get_current_price(symbol)
        if not price_info:
            return {"success": False, "error": f"Cannot get price for {symbol}"}

        # Validate volume
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            vol = symbol_info["volume_min"]
            if volume < vol:
                return {"success": False, "error": f"Volume {volume} below minimum {vol}"}
            if volume > symbol_info["volume_max"]:
                return {"success": False, "error": f"Volume {volume} exceeds maximum {symbol_info['volume_max']}"}

        # Prepare request
        filling_mode = self._get_supported_filling_mode(symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price_info["ask"],
            "deviation": Config.DEFAULT_SLIPPAGE,
            "magic": magic if magic else Config.DEFAULT_MAGIC_NUMBER,
            "comment": comment or "TV Signal",
            "type_filling": filling_mode,
        }

        # Only add SL/TP if provided
        if stop_loss is not None and stop_loss > 0:
            request["sl"] = stop_loss
        if take_profit is not None and take_profit > 0:
            request["tp"] = take_profit

        logger.info(f"BUY {symbol}: volume={volume}, price={price_info['ask']}")
        result = mt5.order_send(request)

        return self._parse_trade_result(result)

    def sell(
        self,
        symbol: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
        magic: int = None,
    ) -> Optional[Dict[str, Any]]:
        """Open SELL position"""
        if not self.is_connected():
            return {"success": False, "error": "MT5 not connected"}

        # Resolve symbol name to actual MT5 symbol
        symbol = self.resolve_symbol(symbol)

        # Validate symbol
        if not mt5.symbol_select(symbol, True):
            return {"success": False, "error": f"Symbol {symbol} not available"}

        # Get current price
        price_info = self.get_current_price(symbol)
        if not price_info:
            return {"success": False, "error": f"Cannot get price for {symbol}"}

        # Validate volume
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            vol = symbol_info["volume_min"]
            if volume < vol:
                return {"success": False, "error": f"Volume {volume} below minimum {vol}"}
            if volume > symbol_info["volume_max"]:
                return {"success": False, "error": f"Volume {volume} exceeds maximum {symbol_info['volume_max']}"}

        # Prepare request
        filling_mode = self._get_supported_filling_mode(symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL,
            "price": price_info["bid"],
            "deviation": Config.DEFAULT_SLIPPAGE,
            "magic": magic if magic else Config.DEFAULT_MAGIC_NUMBER,
            "comment": comment or "TV Signal",
            "type_filling": filling_mode,
        }

        # Only add SL/TP if provided
        if stop_loss is not None and stop_loss > 0:
            request["sl"] = stop_loss
        if take_profit is not None and take_profit > 0:
            request["tp"] = take_profit

        logger.info(f"SELL {symbol}: volume={volume}, price={price_info['bid']}")
        result = mt5.order_send(request)

        return self._parse_trade_result(result)

    def close_position(self, ticket: int, volume: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Close a position by ticket"""
        if not self.is_connected():
            return {"success": False, "error": "MT5 not connected"}

        position = self.get_position_by_ticket(ticket)
        if not position:
            return {"success": False, "error": f"Position {ticket} not found"}

        close_volume = volume if volume else position["volume"]
        order_type = mt5.ORDER_TYPE_SELL if position["type"] == "BUY" else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position["symbol"],
            "volume": close_volume,
            "type": order_type,
            "position": ticket,
            "price": self.get_current_price(position["symbol"])["bid" if order_type == mt5.ORDER_TYPE_SELL else "ask"],
            "deviation": Config.DEFAULT_SLIPPAGE,
            "magic": position["magic"],
            "comment": "Closed by TV Signal",
            "type_filling": self._get_supported_filling_mode(position["symbol"]),
        }

        logger.info(f"CLOSE position {ticket}: {position['symbol']} {close_volume} lots")
        result = mt5.order_send(request)

        return self._parse_trade_result(result)

    def close_all_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Close all positions, optionally filtered by symbol"""
        results = []
        positions = self.get_positions(symbol)

        for pos in positions:
            result = self.close_position(pos["ticket"])
            results.append({"ticket": pos["ticket"], "result": result})

        return results

    def close_by_magic(self, magic: int) -> List[Dict[str, Any]]:
        """Close all positions with specific magic number"""
        positions = self.get_positions()
        results = []
        for pos in positions:
            if pos["magic"] == magic:
                result = self.close_position(pos["ticket"])
                results.append({"ticket": pos["ticket"], "result": result})
        return results

    def _parse_trade_result(self, result) -> Dict[str, Any]:
        """Parse MT5 trade result"""
        if result is None:
            error = mt5.last_error()
            logger.error(f"Trade result is None, last error: {error}")
            return {"success": False, "error": f"Trade failed: {error}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Trade failed: retcode={result.retcode}, comment={result.comment}")
            return {
                "success": False,
                "error": f"Retcode {result.retcode}: {result.comment}",
                "retcode": result.retcode,
                "deal": result.deal,
                "order": result.order,
            }

        logger.info(f"Trade success: deal={result.deal}, order={result.order}")
        return {
            "success": True,
            "deal": result.deal,
            "order": result.order,
            "volume": result.volume,
            "price": result.price,
            "comment": result.comment,
        }
