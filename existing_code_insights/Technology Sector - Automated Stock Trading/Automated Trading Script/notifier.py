"""
TELEGRAM NOTIFICATION MODULE
============================
Handles Telegram notifications for trading events
"""

import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env")

# Telegram configuration
ENABLE_NOTIFICATIONS = os.getenv("ENABLE_NOTIFICATIONS", "0") == "1"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    """
    Send a message to Telegram
    
    Args:
        message (str): Message to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not ENABLE_NOTIFICATIONS:
        logging.debug("Telegram notifications disabled")
        return False
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram bot token or chat ID not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logging.info("Telegram notification sent successfully")
            return True
        else:
            logging.error(f"Failed to send Telegram notification: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Error sending Telegram notification: {e}")
        return False

def notify_trade_opened(symbol, side, quantity, fill_price, order_id, sentiment=None, timestamp=None):
    """
    Send notification when a trade is opened
    
    Args:
        symbol (str): Stock symbol
        side (str): BUY or SELL
        quantity (int): Number of shares
        fill_price (float): Fill price per share
        order_id (str): Order ID
        sentiment (float, optional): Sentiment score
        timestamp (datetime, optional): Trade timestamp
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    # Format the message
    message = f"""🚀 <b>TRADE OPENED</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Side:</b> {side}
🔢 <b>Quantity:</b> {quantity:,} shares
💰 <b>Fill Price:</b> ${fill_price:.2f}
🆔 <b>Order ID:</b> {order_id}
🕐 <b>Time:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""

    if sentiment is not None:
        message += f"\n🎯 <b>Sentiment:</b> {sentiment:.4f}"
    
    # Calculate total value
    total_value = quantity * fill_price
    message += f"\n💵 <b>Total Value:</b> ${total_value:,.2f}"
    
    return send_telegram_message(message)

def notify_trade_closed(symbol, quantity, exit_price, realized_pnl, realized_pnl_pct, 
                       exit_reason, order_id, holding_time_minutes, timestamp=None):
    """
    Send notification when a trade is closed
    
    Args:
        symbol (str): Stock symbol
        quantity (int): Number of shares
        exit_price (float): Exit price per share
        realized_pnl (float): Realized P&L in dollars
        realized_pnl_pct (float): Realized P&L percentage
        exit_reason (str): Reason for exit (TP/SL/Time)
        order_id (str): Order ID
        holding_time_minutes (float): Holding time in minutes
        timestamp (datetime, optional): Trade timestamp
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    # Determine emoji based on P&L
    pnl_emoji = "📈" if realized_pnl >= 0 else "📉"
    result_emoji = "✅" if realized_pnl >= 0 else "❌"
    
    # Format holding time
    if holding_time_minutes >= 60:
        holding_time_str = f"{holding_time_minutes/60:.1f} hours"
    else:
        holding_time_str = f"{holding_time_minutes:.0f} minutes"
    
    # Format the message
    message = f"""{result_emoji} <b>TRADE CLOSED</b>

📊 <b>Symbol:</b> {symbol}
🔢 <b>Quantity:</b> {quantity:,} shares
💰 <b>Exit Price:</b> ${exit_price:.2f}
{pnl_emoji} <b>P&L:</b> ${realized_pnl:+,.2f} ({realized_pnl_pct:+.2f}%)
🎯 <b>Exit Reason:</b> {exit_reason}
🆔 <b>Order ID:</b> {order_id}
⏱️ <b>Holding Time:</b> {holding_time_str}
🕐 <b>Time:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""
    
    # Calculate total exit value
    total_exit_value = quantity * exit_price
    message += f"\n💵 <b>Total Exit Value:</b> ${total_exit_value:,.2f}"
    
    return send_telegram_message(message)

def notify_system_status(message, status_type="INFO"):
    """
    Send system status notification
    
    Args:
        message (str): Status message
        status_type (str): Type of status (INFO, WARNING, ERROR)
    """
    emoji_map = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "🚨"
    }
    
    emoji = emoji_map.get(status_type, "ℹ️")
    formatted_message = f"{emoji} <b>SYSTEM {status_type}</b>\n\n{message}"
    
    return send_telegram_message(formatted_message)

def test_telegram_connection():
    """
    Test Telegram connection by sending a test message
    
    Returns:
        bool: True if successful, False otherwise
    """
    test_message = "🧪 <b>TEST MESSAGE</b>\n\nTelegram notifications are working correctly!"
    return send_telegram_message(test_message)


