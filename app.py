"""
MT5 Trading Connector - Flask Application
Receives TradingView webhook alerts and forwards them to MT5 for execution
"""
import logging
import secrets
import atexit
from flask import Flask, request, jsonify
from config import Config
from mt5_client import MT5Client
from tradingview_parser import TradingViewParser

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize clients
mt5_client = MT5Client()
tv_parser = TradingViewParser()


def verify_auth():
    """Verify request authentication if enabled"""
    if not Config.ENABLE_AUTH:
        return True

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return secrets.compare_digest(token, Config.AUTH_TOKEN)

    return False


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    mt5_status = mt5_client.is_connected()
    return jsonify({
        "status": "healthy" if mt5_status else "degraded",
        "mt5_connected": mt5_status,
        "account": mt5_client.account_info if mt5_status else None,
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Main webhook endpoint for TradingView alerts

    Expected JSON format:
    {
        "action": "buy" | "sell" | "close",
        "symbol": "EURUSD",
        "volume": 0.1,
        "sl": 1.0800,  // optional
        "tp": 1.0900,  // optional
        "comment": "optional comment"
    }

    Also supports plain text alerts and other TradingView formats.
    """
    # Verify authentication
    if not verify_auth():
        logger.warning("Unauthorized webhook attempt")
        return jsonify({"error": "Unauthorized"}), 401

    # Parse request data
    try:
        if request.is_json:
            data = request.get_json()
        elif request.form:
            data = dict(request.form)
        else:
            data = {"text": request.get_data(as_text=True)}
    except Exception as e:
        logger.error(f"Failed to parse request: {e}")
        return jsonify({"error": "Invalid request format"}), 400

    logger.info(f"Received signal: {data}")

    # Parse TradingView signal
    signal = tv_parser.parse(data)
    if not signal:
        logger.warning(f"Failed to parse signal: {data}")
        return jsonify({"error": "Failed to parse signal"}), 400

    # Validate signal
    valid, error_msg = tv_parser.validate_signal(signal)
    if not valid:
        logger.warning(f"Invalid signal: {error_msg}")
        return jsonify({"error": f"Invalid signal: {error_msg}"}), 400

    logger.info(f"Parsed signal: action={signal.action}, symbol={signal.symbol}, volume={signal.volume}")

    # Execute trade
    result = execute_trade(signal)

    if result.get("success"):
        return jsonify({
            "status": "success",
            "signal": {
                "action": signal.action,
                "symbol": signal.symbol,
                "volume": signal.volume,
            },
            "result": result,
        })
    else:
        return jsonify({
            "status": "error",
            "signal": {
                "action": signal.action,
                "symbol": signal.symbol,
                "volume": signal.volume,
            },
            "error": result.get("error"),
        }), 400


def execute_trade(signal):
    """Execute trading signal on MT5"""
    if not mt5_client.is_connected():
        if not mt5_client.connect():
            return {"success": False, "error": "Failed to connect to MT5"}

    try:
        if signal.action == "BUY":
            return mt5_client.buy(
                symbol=signal.symbol,
                volume=signal.volume,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                comment=signal.comment,
            )

        elif signal.action == "SELL":
            return mt5_client.sell(
                symbol=signal.symbol,
                volume=signal.volume,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                comment=signal.comment,
            )

        elif signal.action == "CLOSE":
            # Close all positions for the symbol
            return {
                "success": True,
                "closed_positions": mt5_client.close_all_positions(signal.symbol),
            }

    except Exception as e:
        logger.exception(f"Trade execution error: {e}")
        return {"success": False, "error": str(e)}


@app.route("/positions", methods=["GET"])
def get_positions():
    """Get current open positions"""
    if not mt5_client.is_connected():
        if not mt5_client.connect():
            return jsonify({"error": "Failed to connect to MT5"}), 500

    symbol = request.args.get("symbol")
    positions = mt5_client.get_positions(symbol)

    return jsonify({
        "positions": positions,
        "count": len(positions),
    })


@app.route("/position/<int:ticket>", methods=["DELETE"])
def close_position(ticket: int):
    """Close a specific position by ticket"""
    if not mt5_client.is_connected():
        if not mt5_client.connect():
            return jsonify({"error": "Failed to connect to MT5"}), 500

    result = mt5_client.close_position(ticket)

    if result.get("success"):
        return jsonify({"status": "success", "result": result})
    else:
        return jsonify({"error": result.get("error")}), 400


@app.route("/positions", methods=["DELETE"])
def close_all_positions():
    """Close all positions"""
    if not mt5_client.is_connected():
        if not mt5_client.connect():
            return jsonify({"error": "Failed to connect to MT5"}), 500

    symbol = request.args.get("symbol")
    results = mt5_client.close_all_positions(symbol)

    return jsonify({
        "status": "success",
        "closed": results,
    })


@app.route("/symbol/<symbol>", methods=["GET"])
def get_symbol_info(symbol: str):
    """Get symbol information"""
    if not mt5_client.is_connected():
        if not mt5_client.connect():
            return jsonify({"error": "Failed to connect to MT5"}), 500

    info = mt5_client.get_symbol_info(symbol.upper())

    if info:
        return jsonify(info)
    else:
        return jsonify({"error": "Symbol not found"}), 404


@app.route("/connect", methods=["POST"])
def connect_mt5():
    """Manually connect to MT5"""
    if mt5_client.is_connected():
        return jsonify({"status": "already_connected"})

    if mt5_client.connect():
        return jsonify({"status": "connected", "account": mt5_client.account_info})
    else:
        return jsonify({"error": "Failed to connect to MT5"}), 500


@app.route("/disconnect", methods=["POST"])
def disconnect_mt5():
    """Manually disconnect from MT5"""
    mt5_client.disconnect()
    return jsonify({"status": "disconnected"})


# Startup and shutdown handlers
@app.before_request
def ensure_mt5_connection():
    """Ensure MT5 is connected before processing requests"""
    pass  # Connection is lazy, happens on first trade


@app.after_request
def after_request(response):
    """Add CORS headers"""
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    return response


@atexit.register
def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    mt5_client.disconnect()


# Error handlers
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad Request"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found"}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error")
    return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    logger.info("Starting MT5 Trading Connector...")

    # Attempt to connect to MT5 on startup
    if not mt5_client.connect():
        logger.warning("Could not connect to MT5 on startup. Will retry on first request.")

    # Run Flask app
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True,
    )
