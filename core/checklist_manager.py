# -*- coding: utf-8 -*-
# FILE: core/checklist_manager.py

import config

class ChecklistManager:
    def __init__(self, connector):
        self.connector = connector

    def run_pre_trade_checks(self, account_info, state) -> dict:
        """
        Kiểm tra toàn bộ điều kiện trước khi cho phép hiện nút Trade.
        Trả về: { 'passed': True/False, 'checks': list_details }
        """
        checks = []
        all_passed = True
        
        # 1. Connection Check (Kiểm tra kết nối)
        if self.connector._is_connected:
            checks.append({"name": "Kết nối MT5", "status": "OK", "msg": "Tốt"})
        else:
            checks.append({"name": "Kết nối MT5", "status": "FAIL", "msg": "Mất kết nối"})
            all_passed = False

        # 2. Account Info Check (Dữ liệu tài khoản)
        if not account_info:
             checks.append({"name": "Dữ liệu TK", "status": "FAIL", "msg": "Không lấy được"})
             all_passed = False
             return {"passed": False, "checks": checks}

        # Tự động set Vốn Đầu Ngày nếu chưa có (để tính % lỗ)
        if state["starting_balance"] == 0:
            state["starting_balance"] = account_info.get('balance', 0)

        # 3. RULE: Daily Loss Limit (Quan trọng nhất - Chống cháy TK)
        start_bal = state["starting_balance"]
        pnl_today = state["pnl_today"]
        
        loss_pct = 0.0
        if start_bal > 0:
            loss_pct = (pnl_today / start_bal) * 100
        
        # Lưu ý: pnl_today âm nghĩa là lỗ (Ví dụ: -1.6%)
        if loss_pct <= -config.MAX_DAILY_LOSS_PERCENT:
            checks.append({"name": "Daily Loss", "status": "FAIL", 
                           "msg": f"Đã chạm {loss_pct:.2f}% (Limit -{config.MAX_DAILY_LOSS_PERCENT}%)"})
            all_passed = False
        else:
            checks.append({"name": "Daily Loss", "status": "OK", 
                           "msg": f"Hiện tại: {loss_pct:.2f}%"})

        # 4. RULE: Losing Streak (Chống tâm lý cay cú)
        streak = state["losing_streak"]
        if streak >= config.MAX_LOSING_STREAK:
            checks.append({"name": "Chuỗi Thua", "status": "FAIL", 
                           "msg": f"Thua {streak} lệnh (Max {config.MAX_LOSING_STREAK})"})
            all_passed = False
        else:
            checks.append({"name": "Chuỗi Thua", "status": "OK", 
                           "msg": f"{streak} / {config.MAX_LOSING_STREAK}"})

        # 5. RULE: Max Trades (Chống overtrade)
        trades_count = state["trades_today_count"]
        if trades_count >= config.MAX_TRADES_PER_DAY:
            checks.append({"name": "Số Lệnh/Ngày", "status": "FAIL", 
                           "msg": f"Đã đi {trades_count} lệnh"})
            all_passed = False
        else:
             checks.append({"name": "Số Lệnh/Ngày", "status": "OK", 
                           "msg": f"{trades_count} / {config.MAX_TRADES_PER_DAY}"})

        # 6. RULE: One Position Only (Chỉ 1 lệnh 1 lúc)
        # Lọc xem có lệnh nào của Bot (theo Magic Number) đang chạy không
        positions = self.connector.get_all_open_positions()
        my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]
        
        if len(my_pos) > 0:
            checks.append({"name": "Trạng thái", "status": "FAIL", "msg": "Đang có lệnh chạy"})
            all_passed = False
        else:
            checks.append({"name": "Trạng thái", "status": "OK", "msg": "Sẵn sàng"})

        return {"passed": all_passed, "checks": checks}