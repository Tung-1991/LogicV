# -*- coding: utf-8 -*-
# FILE: core/trade_manager.py

import logging
import config
from core.storage_manager import load_state, save_state
import MetaTrader5 as mt5
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger("ExnessBot")

class TradeManager:
    def __init__(self, connector, checklist_manager):
        self.connector = connector
        self.checklist = checklist_manager
        self.state = load_state()

    def execute_manual_trade(self, direction):
        """
        Hàm xử lý khi bấm nút LONG/SHORT.
        """
        # 1. Chạy lại Checklist lần cuối (Double Check an toàn)
        acc_info = self.connector.get_account_info()
        res = self.checklist.run_pre_trade_checks(acc_info, self.state)
        if not res["passed"]:
            return "CHECKLIST_FAIL"

        # 2. Lấy giá thị trường hiện tại
        symbol = config.SYMBOL
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return "ERR_NO_TICK"
        
        price = tick.ask if direction == "BUY" else tick.bid
        
        # 3. TÍNH TOÁN QUẢN LÝ VỐN (Risk Management)
        equity = acc_info['equity']
        
        # A. Tính khoảng cách SL (Distance)
        # Mặc định dùng mode PERCENT (SL = 0.4% giá)
        sl_percent = config.PRESET_SCALPING_FAST["SL_PERCENT"] / 100.0
        sl_distance = price * sl_percent
        
        # B. Tính Lot Size dựa trên Risk ($)
        if config.RISK_MODE == "PERCENT":
            risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
        else:
            risk_usd = config.RISK_PER_TRADE_USD
            
        # Lấy Contract Size (BTC thường là 1, Forex là 100000)
        sym_info = mt5.symbol_info(symbol)
        contract_size = sym_info.trade_contract_size if sym_info else 1.0
        
        if sl_distance == 0: return "ERR_CALC_SL"
        
        # Công thức Vàng: Lot = Tiền_Rủi_Ro / (Khoảng_Cách_SL * Contract_Size)
        raw_lot = risk_usd / (sl_distance * contract_size)
        
        # C. Kẹp Lot Size theo giới hạn sàn
        # V2.1 RULE: Nếu Lot tính ra nhỏ hơn Min Lot -> HỦY LỆNH.
        # (Nghĩa là vốn quá nhỏ hoặc SL quá xa, vào lệnh sẽ bị rủi ro > 0.3%)
        if raw_lot < config.MIN_LOT_SIZE:
            print(f"[RISK GUARD] Lot tính ra {raw_lot:.4f} < Min {config.MIN_LOT_SIZE}. HỦY LỆNH để bảo vệ vốn.")
            return "ERR_LOT_TOO_SMALL"
            
        # Làm tròn lot theo bước nhảy (Step) của sàn
        steps = round(raw_lot / config.LOT_STEP)
        lot_size = steps * config.LOT_STEP
        # Đảm bảo không vượt Max
        lot_size = min(lot_size, config.MAX_LOT_SIZE)
        
        # D. Tính giá SL / TP cụ thể
        rr_ratio = config.PRESET_SCALPING_FAST["TP_RR_RATIO"]
        
        if direction == "BUY":
            sl_price = price - sl_distance
            tp_price = price + (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl_price = price + sl_distance
            tp_price = price - (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_SELL

        # 4. GỬI LỆNH (EXECUTION)
        print(f"Executing {direction}: Lot {lot_size}, SL {sl_price:.2f}, TP {tp_price:.2f}")
        result = self.connector.place_order(
            symbol, order_type, lot_size, sl_price, tp_price, 
            config.MAGIC_NUMBER, "V2_Exec"
        )
        
        if result and result.retcode == 10009: # TRADE_RETCODE_DONE
            # Cập nhật ngay vào bộ nhớ
            self.state["trades_today_count"] += 1
            self.state["active_trades"].append(result.order)
            save_state(self.state)
            return "SUCCESS"
        else:
            err = result.comment if result else "Unknown"
            return f"ERR_MT5: {err}"

    def update_running_trades(self):
        """
        Hàm chạy ngầm liên tục:
        1. Kiểm tra lệnh đóng -> Cập nhật PnL & Streak.
        2. Dời SL (Trailing) cho lệnh đang chạy.
        """
        # --- 1. CẬP NHẬT TRẠNG THÁI (PnL & Streak) ---
        try:
            # Lấy lịch sử giao dịch trong 24h qua
            from_date = datetime.now() - timedelta(hours=24)
            history = mt5.history_deals_get(from_date, datetime.now())
            
            if history:
                for deal in history:
                    # Chỉ check lệnh của Bot (Magic Number) và là lệnh ĐÓNG (Entry Out)
                    if deal.magic == config.MAGIC_NUMBER and deal.entry == 1: 
                        pos_id = deal.position_id
                        
                        # Nếu lệnh này nằm trong danh sách đang theo dõi -> Nó vừa đóng
                        if pos_id in self.state["active_trades"]:
                            profit = deal.profit + deal.swap + deal.commission
                            
                            # Cộng dồn PnL hôm nay
                            self.state["pnl_today"] += profit
                            
                            # Cập nhật Chuỗi Thua (Losing Streak)
                            if profit < 0: # Thua
                                # Nếu lỗ quá nhỏ (kiểu trượt giá 0.01) có thể bỏ qua, nhưng strict thì tính luôn
                                self.state["losing_streak"] += 1
                            else: # Thắng
                                self.state["losing_streak"] = 0 # Reset về 0
                            
                            # Xóa khỏi danh sách active
                            self.state["active_trades"].remove(pos_id)
                            save_state(self.state)
                            print(f"[UPDATE] Trade Closed: {pos_id}. Profit: ${profit:.2f}. Streak: {self.state['losing_streak']}")

        except Exception as e:
            # print(f"Lỗi update history: {e}")
            pass

        # --- 2. TRAILING STOP (Dời SL) ---
        try:
            # Lấy danh sách lệnh đang mở trên sàn
            positions = self.connector.get_all_open_positions()
            my_positions = [p for p in positions if p.magic == config.MAGIC_NUMBER]
            
            for pos in my_positions:
                self._apply_trailing_logic(pos)
                
        except Exception as e:
            pass

    def _apply_trailing_logic(self, position):
        """Logic dời SL về Hòa Vốn (Break-Even)"""
        symbol = position.symbol
        entry = position.price_open
        sl = position.sl
        current_price = position.price_current
        
        # Cấu hình Trigger (khi lãi bao nhiêu R thì dời)
        be_trigger_rr = config.PRESET_SCALPING_FAST["BE_TRIGGER_RR"]
        
        # Tính khoảng cách Rủi ro ban đầu (1R)
        risk_dist = abs(entry - sl) if sl > 0 else 0
        if risk_dist == 0: return

        # Tính lãi hiện tại (theo khoảng cách giá)
        profit_dist = abs(current_price - entry)
        
        # Nếu lãi >= 0.8R (hoặc số config) -> Dời về Entry
        if profit_dist >= (risk_dist * be_trigger_rr):
            new_sl = entry # Dời về đúng giá vào lệnh (Hòa vốn)
            
            # Kiểm tra: Chỉ dời nếu SL mới tốt hơn SL cũ
            should_modify = False
            
            if position.type == 0: # BUY
                if new_sl > sl: should_modify = True # Chỉ dời lên
            elif position.type == 1: # SELL
                if new_sl < sl or sl == 0: should_modify = True # Chỉ dời xuống

            if should_modify:
                print(f"[TRAILING] Dời SL về hòa vốn cho lệnh {position.ticket}")
                self.connector.modify_position(position.ticket, new_sl, position.tp)