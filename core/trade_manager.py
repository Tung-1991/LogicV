# -*- coding: utf-8 -*-
# FILE: core/trade_manager.py
# Logic V2.4: Full Features (Symbol Select, Strict Mode, Low Cap Confirm, Staircase Trailing)

import logging
import config
from core.storage_manager import load_state, save_state
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import math

logger = logging.getLogger("ExnessBot")

class TradeManager:
    def __init__(self, connector, checklist_manager):
        self.connector = connector
        self.checklist = checklist_manager
        self.state = load_state()

    def execute_manual_trade(self, direction, preset_name, symbol, strict_mode, accept_min_lot=False):
        # Cập nhật Config Global để các module khác biết đang trade con gì
        config.SYMBOL = symbol 

        # 1. Chạy Checklist (Truyền thêm symbol và strict_mode để check Spread/Ping)
        acc_info = self.connector.get_account_info()
        res = self.checklist.run_pre_trade_checks(acc_info, self.state, symbol, strict_mode)
        if not res["passed"]:
            return "CHECKLIST_FAIL"

        # 2. Lấy thông số Preset
        params = config.PRESETS.get(preset_name, config.PRESETS["SCALPING"])
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return "ERR_NO_TICK"
        
        price = tick.ask if direction == "BUY" else tick.bid
        
        # 3. TÍNH TOÁN SL/TP & VOLUME
        equity = acc_info['equity']
        
        # A. Tính khoảng cách SL
        sl_percent = params["SL_PERCENT"] / 100.0
        sl_distance = price * sl_percent
        
        if sl_distance == 0: return "ERR_CALC_SL"
        
        sym_info = mt5.symbol_info(symbol)
        contract_size = sym_info.trade_contract_size if sym_info else 1.0

        # B. Tính Lot Size
        lot_size = 0.0
        
        if config.LOT_SIZE_MODE == "FIXED":
            lot_size = config.FIXED_LOT_VOLUME
        else:
            # Mode DYNAMIC
            if hasattr(config, 'RISK_MODE') and config.RISK_MODE == "PERCENT":
                 risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
            else:
                 risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
            
            raw_lot = risk_usd / (sl_distance * contract_size)
            
            # Xử lý vốn nhỏ: Hỏi chứ không hủy
            if raw_lot < config.MIN_LOT_SIZE:
                if accept_min_lot:
                    lot_size = config.MIN_LOT_SIZE
                else:
                    real_risk_at_min = (config.MIN_LOT_SIZE * sl_distance * contract_size)
                    return f"CONFIRM_LOW_CAP|{config.MIN_LOT_SIZE}|{real_risk_at_min:.2f}"
            else:
                steps = round(raw_lot / config.LOT_STEP)
                lot_size = steps * config.LOT_STEP

        # Kẹp giới hạn Max/Min
        lot_size = min(lot_size, config.MAX_LOT_SIZE)
        if lot_size < config.MIN_LOT_SIZE: lot_size = config.MIN_LOT_SIZE

        # C. Tính giá SL / TP
        rr_ratio = params["TP_RR_RATIO"]
        
        if direction == "BUY":
            sl_price = price - sl_distance
            tp_price = price + (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl_price = price + sl_distance
            tp_price = price - (sl_distance * rr_ratio)
            order_type = mt5.ORDER_TYPE_SELL

        # 4. GỬI LỆNH
        comment = f"V2_{preset_name}" 
        
        print(f"Executing {direction} [{preset_name}] on {symbol}: Lot {lot_size}, SL {sl_price:.2f}")
        
        result = self.connector.place_order(
            symbol, order_type, lot_size, sl_price, tp_price, 
            config.MAGIC_NUMBER, comment
        )
        
        if result and result.retcode == 10009:
            self.state["trades_today_count"] += 1
            self.state["active_trades"].append(result.order)
            save_state(self.state)
            return "SUCCESS"
        else:
            err = result.comment if result else "Unknown"
            return f"ERR_MT5: {err}"

    def update_running_trades(self):
        # 1. CẬP NHẬT PnL & STREAK
        try:
            from_date = datetime.now() - timedelta(hours=24)
            history = mt5.history_deals_get(from_date, datetime.now())
            if history:
                for deal in history:
                    if deal.magic == config.MAGIC_NUMBER and deal.entry == 1: 
                        pos_id = deal.position_id
                        if pos_id in self.state["active_trades"]:
                            profit = deal.profit + deal.swap + deal.commission
                            self.state["pnl_today"] += profit
                            
                            if profit < 0: self.state["losing_streak"] += 1
                            else: self.state["losing_streak"] = 0
                            
                            self.state["active_trades"].remove(pos_id)
                            save_state(self.state)
                            print(f"[UPDATE] Closed {pos_id}. PnL: {profit:.2f}. Streak: {self.state['losing_streak']}")
        except Exception:
            pass

        # 2. TRAILING STOP
        try:
            positions = self.connector.get_all_open_positions()
            my_positions = [p for p in positions if p.magic == config.MAGIC_NUMBER]
            for pos in my_positions:
                self._apply_trailing_logic(pos)
        except Exception:
            pass

    def _apply_trailing_logic(self, position):
        # 1. Xác định Preset
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
        
        # Ước lượng Risk
        estimated_risk_dist = entry * (params["SL_PERCENT"] / 100.0)
        if estimated_risk_dist == 0: return

        profit_dist = abs(current_price - entry)
        current_r = profit_dist / estimated_risk_dist
        
        be_trigger = params["BE_TRIGGER_RR"]
        step_r = params["TRAILING_STEP_RR"]
        
        new_sl = None

        # A. Check Hòa Vốn
        if current_r >= be_trigger:
            dist_to_entry = abs(current_sl - entry)
            is_losing_sl = False
            if position.type == 0: # BUY
                if current_sl < entry - 0.00001: is_losing_sl = True
            else: # SELL
                if current_sl > entry + 0.00001: is_losing_sl = True
                
            if is_losing_sl:
                new_sl = entry

            # B. Check Trailing Dương
            if current_r >= (be_trigger + step_r):
                steps_climbed = math.floor((current_r - be_trigger) / step_r)
                
                target_profit_r = steps_climbed * step_r
                target_profit_dist = target_profit_r * estimated_risk_dist
                
                if position.type == 0: # BUY
                    candidate_sl = entry + target_profit_dist
                    if candidate_sl > current_sl + 0.00001:
                        new_sl = candidate_sl
                else: # SELL
                    candidate_sl = entry - target_profit_dist
                    if candidate_sl < current_sl - 0.00001 or current_sl == 0:
                        new_sl = candidate_sl

        # 4. Thực thi dời SL
        if new_sl is not None:
            point = mt5.symbol_info(symbol).point
            new_sl = round(new_sl / point) * point
            print(f"[TRAILING] {preset_name} | Ticket {position.ticket}: Lãi {current_r:.2f}R. Dời SL về {new_sl}")
            self.connector.modify_position(position.ticket, new_sl, position.tp)