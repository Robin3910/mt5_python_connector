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

    def __init__(self):
        self.connected = False
        self.account_info: Optional[Dict] = None

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

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
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
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price_info["ask"],
            "sl": stop_loss if stop_loss else 0,
            "tp": take_profit if take_profit else 0,
            "deviation": Config.DEFAULT_SLIPPAGE,
            "magic": magic if magic else Config.DEFAULT_MAGIC_NUMBER,
            "comment": comment or "TV Signal",
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

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
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL,
            "price": price_info["bid"],
            "sl": stop_loss if stop_loss else 0,
            "tp": take_profit if take_profit else 0,
            "deviation": Config.DEFAULT_SLIPPAGE,
            "magic": magic if magic else Config.DEFAULT_MAGIC_NUMBER,
            "comment": comment or "TV Signal",
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

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
            "type_filling": mt5.ORDER_FILLING_FOK,
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
