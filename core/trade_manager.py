# -*- coding: utf-8 -*-
# FILE: core/trade_manager.py
# Logic V2.7: Smart Update (Fix PnL miss) & Manual Close Detection

import logging
import config
from core.storage_manager import load_state, save_state
import MetaTrader5 as mt5
from datetime import datetime
import math

logger = logging.getLogger("ExnessBot")

class TradeManager:
    def __init__(self, connector, checklist_manager):
        self.connector = connector
        self.checklist = checklist_manager
        self.state = load_state()
        
        if "tsl_disabled_tickets" not in self.state:
            self.state["tsl_disabled_tickets"] = []

    def execute_manual_trade(self, direction, preset_name, symbol, strict_mode, accept_min_lot=False):
        config.SYMBOL = symbol 
        acc_info = self.connector.get_account_info()
        res = self.checklist.run_pre_trade_checks(acc_info, self.state, symbol, strict_mode)
        if not res["passed"]: return "CHECKLIST_FAIL"

        params = config.PRESETS.get(preset_name, config.PRESETS["SCALPING"])
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return "ERR_NO_TICK"
        price = tick.ask if direction == "BUY" else tick.bid
        
        equity = acc_info['equity']
        sl_percent = params["SL_PERCENT"] / 100.0
        sl_distance = price * sl_percent
        if sl_distance == 0: return "ERR_CALC_SL"
        
        sym_info = mt5.symbol_info(symbol)
        contract_size = sym_info.trade_contract_size if sym_info else 1.0

        lot_size = 0.0
        if config.LOT_SIZE_MODE == "FIXED":
            lot_size = config.FIXED_LOT_VOLUME
        else:
            risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
            raw_lot = risk_usd / (sl_distance * contract_size)
            if raw_lot < config.MIN_LOT_SIZE:
                if accept_min_lot: lot_size = config.MIN_LOT_SIZE
                else:
                    real_risk_at_min = (config.MIN_LOT_SIZE * sl_distance * contract_size)
                    return f"CONFIRM_LOW_CAP|{config.MIN_LOT_SIZE}|{real_risk_at_min:.2f}"
            else:
                steps = round(raw_lot / config.LOT_STEP)
                lot_size = steps * config.LOT_STEP

        lot_size = min(lot_size, config.MAX_LOT_SIZE)
        if lot_size < config.MIN_LOT_SIZE: lot_size = config.MIN_LOT_SIZE

        rr_ratio = params["TP_RR_RATIO"]
        if direction == "BUY":
            sl_price = price - sl_distance
            tp_price = price + (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl_price = price + sl_distance
            tp_price = price - (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_SELL

        comment = f"V2_{preset_name}" 
        print(f"Executing {direction} [{preset_name}] on {symbol}: Lot {lot_size}, SL {sl_price:.2f}")
        
        result = self.connector.place_order(symbol, order_type, lot_size, sl_price, tp_price, config.MAGIC_NUMBER, comment)
        
        if result and result.retcode == 10009:
            self.state["trades_today_count"] += 1
            self.state["active_trades"].append(result.order)
            save_state(self.state)
            return "SUCCESS"
        else:
            err = result.comment if result else "Unknown"
            return f"ERR_MT5: {err}"

    def update_running_trades(self):
        # 1. CẬP NHẬT PnL & LỊCH SỬ (LOGIC MỚI: ĐIỂM DANH)
        try:
            # Lấy tất cả lệnh đang mở trên sàn
            current_positions = self.connector.get_all_open_positions()
            current_tickets = [p.ticket for p in current_positions]
            
            # Danh sách lệnh bot đang theo dõi
            tracked_tickets = list(self.state["active_trades"])
            
            # Tìm những lệnh "mất tích" (đã đóng)
            closed_tickets = [t for t in tracked_tickets if t not in current_tickets]
            
            if closed_tickets:
                for ticket in closed_tickets:
                    # Truy xuất lịch sử CỤ THỂ của ticket này
                    deals = mt5.history_deals_get(position=ticket)
                    
                    if deals:
                        # Deal cuối cùng là deal đóng lệnh (Entry Out)
                        exit_deal = deals[-1]
                        profit = exit_deal.profit + exit_deal.swap + exit_deal.commission
                        
                        # Update State
                        self.state["pnl_today"] += profit
                        
                        if profit < 0: self.state["losing_streak"] += 1
                        else: self.state["losing_streak"] = 0
                        
                        # Phân loại lý do đóng
                        close_reason = "Auto/TP/SL"
                        if exit_deal.comment and "User_Close" in exit_deal.comment:
                            close_reason = "Manual (User)"
                        elif exit_deal.reason == mt5.DEAL_REASON_SL:
                            close_reason = "Hit SL"
                        elif exit_deal.reason == mt5.DEAL_REASON_TP:
                            close_reason = "Hit TP"
                            
                        # Lưu vào lịch sử chi tiết
                        history_item = {
                            "ticket": ticket,
                            "symbol": exit_deal.symbol,
                            "profit": profit,
                            "time": datetime.fromtimestamp(exit_deal.time).strftime("%H:%M:%S"),
                            "reason": close_reason
                        }
                        if "daily_history" not in self.state: self.state["daily_history"] = []
                        self.state["daily_history"].append(history_item)

                        # Xóa khỏi danh sách theo dõi
                        self.state["active_trades"].remove(ticket)
                        if ticket in self.state.get("tsl_disabled_tickets", []):
                            self.state["tsl_disabled_tickets"].remove(ticket)
                            
                        print(f"[CLOSED] #{ticket} | PnL: {profit:.2f} | Reason: {close_reason}")
                
                # Lưu state ngay lập tức
                save_state(self.state)

        except Exception as e:
            print(f"Lỗi update: {e}")

        # 2. TRAILING STOP
        try:
            positions = self.connector.get_all_open_positions()
            my_positions = [p for p in positions if p.magic == config.MAGIC_NUMBER]
            for pos in my_positions:
                self._apply_trailing_logic(pos)
        except Exception:
            pass

    def toggle_tsl(self, ticket):
        disabled_list = self.state.get("tsl_disabled_tickets", [])
        if ticket in disabled_list:
            disabled_list.remove(ticket)
            is_active = True
        else:
            disabled_list.append(ticket)
            is_active = False
        self.state["tsl_disabled_tickets"] = disabled_list
        save_state(self.state)
        return is_active

    def is_tsl_active(self, ticket):
        return ticket not in self.state.get("tsl_disabled_tickets", [])

    def _apply_trailing_logic(self, position):
        if not self.is_tsl_active(position.ticket): return

        preset_name = "SCALPING" 
        if position.comment and position.comment.startswith("V2_"):
            parts = position.comment.split("_")
            if len(parts) > 1 and parts[1] in config.PRESETS:
                preset_name = parts[1]
        
        params = config.PRESETS[preset_name]
        symbol = position.symbol
        entry = position.price_open
        current_sl = position.sl
        current_price = position.price_current
        
        estimated_risk_dist = entry * (params["SL_PERCENT"] / 100.0)
        if estimated_risk_dist == 0: return

        profit_dist = abs(current_price - entry)
        current_r = profit_dist / estimated_risk_dist
        
        be_trigger = params["BE_TRIGGER_RR"]
        step_r = params["TRAILING_STEP_RR"]
        new_sl = None

        # A. Check Hòa Vốn
        if current_r >= be_trigger:
            is_losing_sl = False
            if position.type == 0: # BUY
                if current_sl < entry - 0.00001: is_losing_sl = True
            else: # SELL
                if current_sl > entry + 0.00001: is_losing_sl = True
            if is_losing_sl: new_sl = entry

            # B. Check Trailing Dương
            if current_r >= (be_trigger + step_r):
                steps_climbed = math.floor((current_r - be_trigger) / step_r)
                target_profit_r = steps_climbed * step_r
                target_profit_dist = target_profit_r * estimated_risk_dist
                
                if position.type == 0: # BUY
                    candidate_sl = entry + target_profit_dist
                    if candidate_sl > current_sl + 0.00001: new_sl = candidate_sl
                else: # SELL
                    candidate_sl = entry - target_profit_dist
                    if candidate_sl < current_sl - 0.00001 or current_sl == 0: new_sl = candidate_sl

        if new_sl is not None:
            point = mt5.symbol_info(symbol).point
            new_sl = round(new_sl / point) * point
            print(f"[TRAILING] {preset_name} | Ticket {position.ticket}: Lãi {current_r:.2f}R. Dời SL về {new_sl}")
            self.connector.modify_position(position.ticket, new_sl, position.tp)