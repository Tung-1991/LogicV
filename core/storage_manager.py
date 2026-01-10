# -*- coding: utf-8 -*-
# FILE: core/storage_manager.py
# Updated: Reset theo giờ Config & Ghi log Realtime

import json
import os
import csv
from datetime import datetime, timedelta
from typing import Dict, Any
import config 

STATE_FILE = "data/bot_state.json"
HISTORY_FILE = "data/trade_history_log.csv" 
MASTER_LOG_FILE = "data/trade_history_master.csv" # File log chi tiết

def get_today_str():
    """Lấy ngày theo phiên (trừ đi giờ reset để tính phiên)"""
    now = datetime.now()
    if now.hour < config.RESET_HOUR:
        # Ví dụ: 2h sáng ngày 10/1 => Vẫn tính là phiên ngày 09/1
        prev_day = now - timedelta(days=1)
        return prev_day.strftime("%Y-%m-%d")
    else:
        return now.strftime("%Y-%m-%d")

def append_trade_log(ticket, symbol, type_str, volume, pnl, close_reason):
    """Ghi 1 dòng vào file CSV ngay lập tức (Giờ máy tính)"""
    file_exists = os.path.isfile(MASTER_LOG_FILE)
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
        with open(MASTER_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Time", "Ticket", "Symbol", "Type", "Vol", "PnL ($)", "Reason"])
            
            writer.writerow([now_str, ticket, symbol, type_str, volume, f"{pnl:.2f}", close_reason])
    except Exception as e:
        print(f"Lỗi ghi log CSV: {e}")

def save_daily_history_to_csv(prev_date, pnl, trades_count, win_streak, lose_streak):
    file_exists = os.path.isfile(HISTORY_FILE)
    try:
        with open(HISTORY_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "PnL ($)", "Total Trades", "End Streak"])
            
            streak_str = f"L{lose_streak}" if lose_streak > 0 else f"W{win_streak}"
            writer.writerow([prev_date, f"{pnl:.2f}", trades_count, streak_str])
            print(f">>> Đã lưu lịch sử ngày {prev_date} vào {HISTORY_FILE}")
    except Exception as e:
        print(f"Lỗi lưu lịch sử CSV: {e}")

def load_state() -> Dict[str, Any]:
    default_state = {
        "date": get_today_str(),
        "pnl_today": 0.0,
        "starting_balance": 0.0,
        "trades_today_count": 0,
        "losing_streak": 0,
        "active_trades": [],
        "tsl_disabled_tickets": [],
        "daily_history": []
    }
    
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    if not os.path.exists(STATE_FILE):
        return default_state

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
            if "daily_history" not in state: state["daily_history"] = []
            if "tsl_disabled_tickets" not in state: state["tsl_disabled_tickets"] = []

            # LOGIC NGÀY MỚI (Dùng hàm get_today_str mới)
            current_date = get_today_str()
            saved_date = state.get("date")

            if saved_date != current_date:
                print(f"--- [NEW SESSION] Chuyển từ {saved_date} sang {current_date} ---")
                
                save_daily_history_to_csv(
                    saved_date, 
                    state.get("pnl_today", 0), 
                    state.get("trades_today_count", 0),
                    0, 
                    state.get("losing_streak", 0)
                )

                state["date"] = current_date
                state["pnl_today"] = 0.0
                state["trades_today_count"] = 0
                state["losing_streak"] = 0 
                state["daily_history"] = [] 
                state["starting_balance"] = 0.0 
                
            return state
    except Exception as e:
        print(f"Lỗi đọc state: {e}. Dùng default.")
        return default_state

def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"Lỗi lưu state: {e}")