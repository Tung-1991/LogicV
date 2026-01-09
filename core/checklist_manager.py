# -*- coding: utf-8 -*-
# FILE: core/checklist_manager.py
# Checklist Manager V2.5 - Upgrade: Check Max Positions from Config

import config
import MetaTrader5 as mt5

class ChecklistManager:
    def __init__(self, connector):
        self.connector = connector

    def run_pre_trade_checks(self, account_info, state, symbol, strict_mode=True) -> dict:
        checks = []
        all_passed = True
        
        # 1. Connection & Ping & Spread Check
        if self.connector._is_connected:
            # --- A. CHECK PING ---
            # Lấy thông tin Ping từ MT5
            ping_ms = mt5.terminal_info().ping_last / 1000
            ping_status = "OK"
            
            # [NÂNG CẤP] Dùng ngưỡng từ Config thay vì số cứng 150
            try:
                max_ping = config.MAX_PING_MS
            except AttributeError:
                max_ping = 150 # Fallback nếu quên cấu hình

            if ping_ms > max_ping: 
                ping_status = "WARN"
                if strict_mode: 
                    all_passed = False # Chặn nếu strict mode bật
                    ping_status = "FAIL"

            # --- B. CHECK SPREAD ---
            tick = mt5.symbol_info_tick(symbol)
            spread_points = 0
            if tick:
                spread_points = (tick.ask - tick.bid) / mt5.symbol_info(symbol).point
            
            # [NÂNG CẤP] Dùng ngưỡng từ Config thay vì số cứng 50
            try:
                max_spread = config.MAX_SPREAD_POINTS
            except AttributeError:
                max_spread = 50 # Fallback nếu quên cấu hình

            spread_msg = f"Ping {ping_ms:.0f}ms | Spr {spread_points:.0f}"
            
            # Logic kiểm tra Spread
            if spread_points > max_spread:
                if strict_mode:
                    checks.append({"name": "Mạng & Spread", "status": "FAIL", "msg": spread_msg})
                    all_passed = False
                else:
                    checks.append({"name": "Mạng & Spread", "status": "WARN", "msg": spread_msg})
            elif ping_status == "FAIL":
                 checks.append({"name": "Mạng & Spread", "status": "FAIL", "msg": spread_msg})
            else:
                 checks.append({"name": "Mạng & Spread", "status": "OK", "msg": spread_msg})

        else:
            checks.append({"name": "Kết nối MT5", "status": "FAIL", "msg": "Mất kết nối"})
            all_passed = False

        # 2. Account Check
        if not account_info:
             checks.append({"name": "Dữ liệu TK", "status": "FAIL", "msg": "Lỗi"})
             return {"passed": False, "checks": checks}

        if state["starting_balance"] == 0:
            state["starting_balance"] = account_info.get('balance', 0)

        # 3. Daily Loss Check
        start_bal = state["starting_balance"]
        pnl_today = state["pnl_today"]
        loss_pct = (pnl_today / start_bal * 100) if start_bal > 0 else 0
        
        if loss_pct <= -config.MAX_DAILY_LOSS_PERCENT:
            checks.append({"name": "Daily Loss", "status": "FAIL", "msg": f"{loss_pct:.2f}%"})
            all_passed = False
        else:
            checks.append({"name": "Daily Loss", "status": "OK", "msg": f"{loss_pct:.2f}%"})

        # 4. Losing Streak Check
        streak = state["losing_streak"]
        if streak >= config.MAX_LOSING_STREAK:
            checks.append({"name": "Chuỗi Thua", "status": "FAIL", "msg": f"{streak} lệnh"})
            all_passed = False
        else:
            checks.append({"name": "Chuỗi Thua", "status": "OK", "msg": f"{streak} lệnh"})

        # 5. Trades Today Check
        count = state["trades_today_count"]
        if count >= config.MAX_TRADES_PER_DAY:
            checks.append({"name": "Số Lệnh", "status": "FAIL", "msg": f"{count} lệnh"})
            all_passed = False
        else:
             checks.append({"name": "Số Lệnh", "status": "OK", "msg": f"{count}"})

        # 6. Open Position Check (Đã update theo Config)
        positions = self.connector.get_all_open_positions()
        # Lọc lệnh của bot mình (theo Magic Number)
        my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]
        
        # [MỚI] So sánh với MAX_OPEN_POSITIONS trong config
        # Lưu ý: Đảm bảo file config.py đã có biến MAX_OPEN_POSITIONS
        try:
            max_open_pos = config.MAX_OPEN_POSITIONS
        except AttributeError:
            max_open_pos = 1 # Fallback an toàn mặc định là 1 nếu quên config

        if len(my_pos) >= max_open_pos:
            checks.append({"name": "Trạng thái", "status": "FAIL", "msg": f"Full ({len(my_pos)}/{max_open_pos})"})
            all_passed = False
        else:
            checks.append({"name": "Trạng thái", "status": "OK", "msg": f"Đang chạy: {len(my_pos)}"})

        return {"passed": all_passed, "checks": checks}