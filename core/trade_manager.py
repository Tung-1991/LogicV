# -*- coding: utf-8 -*-
# FILE: core/trade_manager.py
# Trade Manager V5.2: Dynamic Fee Calculation (Account Types) & TSL V3

import logging
import config
from core.storage_manager import load_state, save_state, append_trade_log
import MetaTrader5 as mt5
from datetime import datetime
import math

logger = logging.getLogger("ExnessBot")

class TradeManager:
    def __init__(self, connector, checklist_manager):
        self.connector = connector
        self.checklist = checklist_manager
        self.state = load_state()
        if "daily_loss_count" not in self.state: self.state["daily_loss_count"] = 0
        if "tsl_disabled_tickets" not in self.state: self.state["tsl_disabled_tickets"] = []
        if self.state.get("trades_today_count", 0) == 0: self.state["daily_loss_count"] = 0

    def execute_manual_trade(self, direction, preset_name, symbol, strict_mode, 
                             manual_lot=0.0, manual_tp=0.0, manual_sl=0.0, bypass_checklist=False):
        
        config.SYMBOL = symbol 
        acc_info = self.connector.get_account_info()
        res = self.checklist.run_pre_trade_checks(acc_info, self.state, symbol, strict_mode)
        
        if not res["passed"]:
            if bypass_checklist:
                fail_reasons = [c['msg'] for c in res['checks'] if c['status'] == 'FAIL']
                print(f"⚠️ [FORCE TRADE] Đã bỏ qua lỗi Checklist: {fail_reasons}")
            else:
                return "CHECKLIST_FAIL"

        params = config.PRESETS.get(preset_name, config.PRESETS["SCALPING"])
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return "ERR_NO_TICK"
        
        price = tick.ask if direction == "BUY" else tick.bid
        equity = acc_info['equity']
        sym_info = mt5.symbol_info(symbol)
        contract_size = sym_info.trade_contract_size if sym_info else 1.0

        lot_size = 0.0
        sl_distance = 0.0
        if manual_sl > 0: sl_distance = abs(price - manual_sl)
        else:
            sl_percent = params["SL_PERCENT"] / 100.0
            sl_distance = price * sl_percent

        if manual_lot > 0: lot_size = manual_lot
        else:
            if config.LOT_SIZE_MODE == "FIXED": lot_size = config.FIXED_LOT_VOLUME
            else:
                if sl_distance == 0: return "ERR_CALC_SL"
                risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
                raw_lot = risk_usd / (sl_distance * contract_size)
                if raw_lot < config.MIN_LOT_SIZE: return f"ERR_LOT_TOO_SMALL|MaxRisk:${risk_usd:.2f}"
                steps = round(raw_lot / config.LOT_STEP)
                lot_size = steps * config.LOT_STEP

        lot_size = min(lot_size, config.MAX_LOT_SIZE)
        if lot_size < config.MIN_LOT_SIZE: lot_size = config.MIN_LOT_SIZE

        rr_ratio = params["TP_RR_RATIO"]
        if manual_sl > 0: sl_price = manual_sl
        else:
            if direction == "BUY": sl_price = price - sl_distance
            else: sl_price = price + sl_distance

        if manual_tp > 0: tp_price = manual_tp
        else:
            real_sl_dist = abs(price - sl_price)
            if direction == "BUY": tp_price = price + (real_sl_dist * rr_ratio)
            else: tp_price = price - (real_sl_dist * rr_ratio)

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        comment = f"V2_{preset_name}" 
        print(f"Executing {direction} | Lot {lot_size} | Entry {price} | SL {sl_price} | TP {tp_price}")
        
        result = self.connector.place_order(symbol, order_type, lot_size, sl_price, tp_price, config.MAGIC_NUMBER, comment)
        if result and result.retcode == 10009:
            self.state["trades_today_count"] += 1
            self.state["active_trades"].append(result.order)
            save_state(self.state)
            return "SUCCESS"
        else:
            err = result.comment if result else "Unknown"
            return f"ERR_MT5: {err}"

    def update_running_trades(self, account_type="STANDARD"):
        """
        [UPDATE] Thêm tham số account_type để tính phí Comm chuẩn xác cho TSL
        """
        try:
            current_positions = self.connector.get_all_open_positions()
            current_tickets = [p.ticket for p in current_positions]
            tracked_tickets = list(self.state["active_trades"])
            closed_tickets = [t for t in tracked_tickets if t not in current_tickets]
            
            if closed_tickets:
                for ticket in closed_tickets:
                    deals = mt5.history_deals_get(position=ticket)
                    if not deals or len(deals) == 0: continue
                    exit_deal = deals[-1]
                    if exit_deal.entry != mt5.DEAL_ENTRY_OUT: continue

                    # [FIX CRASH] Use getattr
                    profit = exit_deal.profit + exit_deal.swap + getattr(exit_deal, 'commission', 0.0)
                    self.state["pnl_today"] += profit
                    
                    if "daily_loss_count" not in self.state: self.state["daily_loss_count"] = 0
                    if profit < 0: 
                        self.state["daily_loss_count"] += 1
                        print(f">>> [LOSS] #{ticket} (${profit:.2f}) -> Count: {self.state['daily_loss_count']}")
                    else:
                        mode = getattr(config, "LOSS_COUNT_MODE", "TOTAL")
                        if mode == "STREAK": self.state["daily_loss_count"] = 0
                        
                    close_reason = "Auto/TP/SL"
                    if exit_deal.comment and "User_Close" in exit_deal.comment: close_reason = "Manual (User)"
                    elif exit_deal.reason == mt5.DEAL_REASON_SL: close_reason = "Hit SL"
                    elif exit_deal.reason == mt5.DEAL_REASON_TP: close_reason = "Hit TP"
                    
                    type_str = "BUY" if exit_deal.type == 1 else "SELL"
                    append_trade_log(ticket, exit_deal.symbol, type_str, exit_deal.volume, profit, close_reason)

                    history_item = {
                        "ticket": ticket, "symbol": exit_deal.symbol, "type": type_str,
                        "profit": profit, "time": datetime.fromtimestamp(exit_deal.time).strftime("%H:%M:%S"),
                        "reason": close_reason
                    }
                    if "daily_history" not in self.state: self.state["daily_history"] = []
                    self.state["daily_history"].append(history_item)

                    self.state["active_trades"].remove(ticket)
                    if ticket in self.state.get("tsl_disabled_tickets", []):
                        self.state["tsl_disabled_tickets"].remove(ticket)
                    print(f"[CLOSED] #{ticket} | PnL: {profit:.2f}")
                save_state(self.state)

            for pos in current_positions:
                if pos.magic == config.MAGIC_NUMBER: 
                    # Truyền account_type vào hàm xử lý TSL
                    self._apply_trailing_logic_v3(pos, account_type)

        except Exception as e:
            print(f"Lỗi update: {e}")

    def _apply_trailing_logic_v3(self, position, account_type="STANDARD"):
        if not self.is_tsl_active(position.ticket): return
        symbol = position.symbol
        entry = position.price_open
        current_sl = position.sl
        current_price = position.price_current
        volume = position.volume
        is_buy = (position.type == mt5.ORDER_TYPE_BUY)
        
        preset_name = "SCALPING" 
        if position.comment and position.comment.startswith("V2_"):
            parts = position.comment.split("_")
            if len(parts) > 1 and parts[1] in config.PRESETS: preset_name = parts[1]
        
        preset_params = config.PRESETS.get(preset_name, config.PRESETS["SCALPING"])
        sl_pct = preset_params["SL_PERCENT"] / 100.0
        r_distance = entry * sl_pct
        if r_distance == 0: return
        
        current_dist_from_entry = current_price - entry if is_buy else entry - current_price
        current_r_gain = current_dist_from_entry / r_distance

        candidates = []
        tsl_cfg = config.TSL_CONFIG
        
        # RULE 1: BE (Break-Even)
        if tsl_cfg["BE_ACTIVE"]:
            if current_r_gain >= tsl_cfg.get("BE_OFFSET_RR", 0.8):
                contract_size = mt5.symbol_info(symbol).trade_contract_size
                
                # --- [NEW] LOGIC TÍNH PHÍ DYNAMIC ---
                # 1. Lấy phí từ Config theo Loại Tài Khoản
                acc_cfg = config.ACCOUNT_TYPES_CONFIG.get(account_type, config.ACCOUNT_TYPES_CONFIG["STANDARD"])
                comm_per_lot = acc_cfg["COMMISSION_PER_LOT"]
                
                # 2. Nếu symbol có cấu hình riêng (VD Crypto) thì ưu tiên
                specific_rate = config.COMMISSION_RATES.get(symbol, 0.0)
                if specific_rate > 0: comm_per_lot = specific_rate
                
                # 3. Tính tổng phí USD
                # [FIX CRASH] Use getattr for swap
                swap_val = getattr(position, 'swap', 0.0)
                total_fee_usd = (comm_per_lot * volume) + abs(swap_val)
                # ------------------------------------
                
                if contract_size > 0: fee_dist = total_fee_usd / (volume * contract_size)
                else: fee_dist = 0

                mode = tsl_cfg.get("BE_MODE", "SOFT")
                be_price = entry 
                if mode == "SOFT": be_price = entry - fee_dist if is_buy else entry + fee_dist
                elif mode == "SMART": be_price = entry + fee_dist if is_buy else entry - fee_dist
                candidates.append((be_price, f"BE_{mode}"))

        # RULE 2: PNL
        if tsl_cfg["PNL_ACTIVE"]:
            acc = self.connector.get_account_info()
            if acc:
                balance = acc['balance']
                # [FIX CRASH] Use getattr
                current_pnl = position.profit + getattr(position, 'swap', 0.0) + getattr(position, 'commission', 0.0)
                pnl_pct = (current_pnl / balance) * 100
                target_lock_pct = 0.0
                for level in tsl_cfg["PNL_LEVELS"]:
                    if pnl_pct >= level[0]: target_lock_pct = level[1]
                
                if target_lock_pct > 0:
                    lock_usd = balance * (target_lock_pct / 100.0)
                    contract_size = mt5.symbol_info(symbol).trade_contract_size
                    lock_dist = lock_usd / (volume * contract_size)
                    pnl_sl_price = entry + lock_dist if is_buy else entry - lock_dist
                    candidates.append((pnl_sl_price, f"PNL_LOCK_{target_lock_pct}%"))

        # RULE 3: STEP
        if tsl_cfg["STEP_ACTIVE"]:
            step_r = tsl_cfg.get("STEP_SIZE_RR", 0.5)
            steps_climbed = math.floor(current_r_gain / step_r)
            if steps_climbed >= 1:
                lock_r = (steps_climbed * step_r) - 0.2 
                if lock_r > 0:
                    lock_dist = lock_r * r_distance
                    step_sl_price = entry + lock_dist if is_buy else entry - lock_dist
                    candidates.append((step_sl_price, "STEP_R"))

        if not candidates: return

        final_sl = None
        chosen_rule = ""
        strategy = tsl_cfg.get("STRATEGY", "BEST_PRICE")
        
        valid_candidates = []
        for price, rule in candidates:
            is_better = False
            if is_buy:
                if price > current_sl + 0.00001: is_better = True
            else: 
                if (current_sl == 0) or (price < current_sl - 0.00001): is_better = True
            if is_better: valid_candidates.append((price, rule))
        
        if not valid_candidates: return

        if strategy == "BEST_PRICE":
            if is_buy: best = max(valid_candidates, key=lambda x: x[0])
            else: best = min(valid_candidates, key=lambda x: x[0])
            final_sl, chosen_rule = best
        elif strategy == "PRIORITY_PNL":
            pnl_cand = [x for x in valid_candidates if "PNL" in x[1]]
            if pnl_cand: final_sl, chosen_rule = pnl_cand[-1]
            else:
                if is_buy: final_sl, chosen_rule = max(valid_candidates, key=lambda x: x[0])
                else: final_sl, chosen_rule = min(valid_candidates, key=lambda x: x[0])
        elif strategy == "PRIORITY_BE":
            be_cand = [x for x in valid_candidates if "BE" in x[1]]
            if be_cand: final_sl, chosen_rule = be_cand[0]
            else:
                if is_buy: final_sl, chosen_rule = max(valid_candidates, key=lambda x: x[0])
                else: final_sl, chosen_rule = min(valid_candidates, key=lambda x: x[0])

        if final_sl is not None:
            point = mt5.symbol_info(symbol).point
            final_sl = round(final_sl / point) * point
            if abs(final_sl - current_sl) > 0.00001:
                print(f"[TSL V3] {chosen_rule} | Ticket {position.ticket} | Dời SL về {final_sl}")
                self.connector.modify_position(position.ticket, final_sl, position.tp)

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