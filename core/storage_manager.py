# -*- coding: utf-8 -*-
# FILE: core/storage_manager.py

import json
import os
from datetime import datetime
from typing import Dict, Any

STATE_FILE = "data/bot_state.json"

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def load_state() -> Dict[str, Any]:
    """Tải trạng thái bot, tự động reset PnL nếu qua ngày mới."""
    
    # Cấu trúc mặc định
    default_state = {
        "date": get_today_str(),
        "pnl_today": 0.0,          # Lãi/Lỗ thực tế hôm nay ($)
        "starting_balance": 0.0,   # Số dư đầu ngày (để tính % Daily Loss)
        "trades_today_count": 0,   # Số lệnh đã vào hôm nay
        "losing_streak": 0,        # Chuỗi thua liên tiếp hiện tại
        "active_trades": []        # Danh sách ticket đang chạy
    }
    
    # Tạo thư mục data nếu chưa có
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    if not os.path.exists(STATE_FILE):
        return default_state

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
            # === LOGIC NGÀY MỚI (New Day Reset) ===
            if state.get("date") != get_today_str():
                print(f"--- [NEW DAY {get_today_str()}] Reset Daily Stats ---")
                state["date"] = get_today_str()
                state["pnl_today"] = 0.0
                state["trades_today_count"] = 0
                state["active_trades"] = [] 
                state["losing_streak"] = 0 # Reset chuỗi thua đầu ngày
                state["starting_balance"] = 0.0 # Để code tự lấy lại balance mới
                
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