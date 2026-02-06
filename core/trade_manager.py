# -*- coding: utf-8 -*-
# FILE: core/trade_manager.py
# V2.2.1: FIXED PRO FEE LOGIC & ENHANCED MULTI-TSL STATUS DISPLAY

import logging
import config
from core.storage_manager import load_state, save_state, append_trade_log
import MetaTrader5 as mt5
from datetime import datetime
import math

class TradeManager:
    def __init__(self, connector, checklist_manager, log_callback=None):
        self.connector = connector
        self.checklist = checklist_manager
        self.log_callback = log_callback 
        self.state = load_state()
        
        # --- INIT STATE ---
        if "daily_loss_count" not in self.state: self.state["daily_loss_count"] = 0
        if "trade_tactics" not in self.state: self.state["trade_tactics"] = {} 
        if self.state.get("trades_today_count", 0) == 0: self.state["daily_loss_count"] = 0

    def log(self, msg):
        if self.log_callback: self.log_callback(msg)
        else: print(msg)

    def get_trade_tactic(self, ticket):
        """Lấy combo tactic đang chạy cho lệnh (Ví dụ: 'BE+STEP_R')"""
        return self.state.get("trade_tactics", {}).get(str(ticket), "OFF")

    def update_trade_tactic(self, ticket, new_tactic_str):
        """Cập nhật chiến thuật mới cho lệnh"""
        if "trade_tactics" not in self.state: self.state["trade_tactics"] = {}
        self.state["trade_tactics"][str(ticket)] = new_tactic_str
        save_state(self.state)

    def execute_manual_trade(self, direction, preset_name, symbol, strict_mode, 
                             manual_lot=0.0, manual_tp=0.0, manual_sl=0.0, bypass_checklist=False, tsl_mode="BE+STEP_R"):
        
        config.SYMBOL = symbol 
        acc_info = self.connector.get_account_info()
        res = self.checklist.run_pre_trade_checks(acc_info, self.state, symbol, strict_mode)
        
        if not res["passed"]:
            if bypass_checklist:
                fail_reasons = [c['msg'] for c in res['checks'] if c['status'] == 'FAIL']
                self.log(f"⚠️ [FORCE] Bỏ qua lỗi: {fail_reasons}")
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
        
        # 1. Tính Lot/SL
        if manual_sl > 0: sl_distance = abs(price - manual_sl)
        else:
            sl_percent = params["SL_PERCENT"] / 100.0
            sl_distance = price * sl_percent

        if manual_lot > 0: lot_size = manual_lot
        else:
            if sl_distance == 0: return "ERR_CALC_SL"
            risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
            raw_lot = risk_usd / (sl_distance * contract_size)
            if raw_lot < config.MIN_LOT_SIZE: return f"ERR_LOT_TOO_SMALL|Risk:${risk_usd:.2f}"
            steps = round(raw_lot / config.LOT_STEP)
            lot_size = steps * config.LOT_STEP

        lot_size = min(lot_size, config.MAX_LOT_SIZE)
        if lot_size < config.MIN_LOT_SIZE: lot_size = config.MIN_LOT_SIZE

        # 2. Tính TP
        rr_ratio = params["TP_RR_RATIO"]
        sl_price = manual_sl if manual_sl > 0 else (price - sl_distance if direction == "BUY" else price + sl_distance)

        if manual_tp > 0: tp_price = manual_tp
        else:
            real_sl_dist = abs(price - sl_price)
            tp_price = price + (real_sl_dist * rr_ratio) if direction == "BUY" else price - (real_sl_dist * rr_ratio)

        # 3. Gửi lệnh
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        comment = f"V8_{preset_name}" 
        
        self.log(f"🚀 Exec {direction} {symbol} | Vol: {lot_size} | TSL: [{tsl_mode.replace('+', '/')}]")
        
        result = self.connector.place_order(symbol, order_type, lot_size, sl_price, tp_price, config.MAGIC_NUMBER, comment)
        if result and result.retcode == 10009:
            self.state["trades_today_count"] += 1
            if result.order not in self.state["active_trades"]:
                self.state["active_trades"].append(result.order)
            self.update_trade_tactic(result.order, tsl_mode)
            return "SUCCESS"
        return f"ERR_MT5: {result.comment if result else 'Unknown'}"

    def update_running_trades(self, account_type="STANDARD"):
        tsl_status_map = {} 
        try:
            current_positions = self.connector.get_all_open_positions()
            current_tickets = [p.ticket for p in current_positions]
            tracked_tickets = list(self.state["active_trades"])
            
            # --- Xử lý lệnh đã đóng ---
            closed_tickets = [t for t in tracked_tickets if t not in current_tickets]
            if closed_tickets:
                for ticket in closed_tickets:
                    s_ticket = str(ticket)
                    if s_ticket in self.state.get("trade_tactics", {}):
                         del self.state["trade_tactics"][s_ticket]
                         
                    deals = mt5.history_deals_get(position=ticket)
                    if deals:
                        exit_deal = deals[-1]
                        if exit_deal.entry == mt5.DEAL_ENTRY_OUT:
                            profit = exit_deal.profit + exit_deal.swap + getattr(exit_deal, 'commission', 0.0)
                            self.state["pnl_today"] += profit
                            if profit < 0: self.state["daily_loss_count"] += 1
                            
                            reason = "Cắt Tay" if "User_Close" in (exit_deal.comment or "") else \
                                     ("Dính SL" if exit_deal.reason == mt5.DEAL_REASON_SL else \
                                      ("Húp TP" if exit_deal.reason == mt5.DEAL_REASON_TP else "Client Close"))
                            
                            self.log(f"[{'BUY' if exit_deal.type == 1 else 'SELL'} {exit_deal.symbol}] #{ticket} | PnL: {profit:+.2f}$ | Lý do: {reason}")
                            append_trade_log(ticket, exit_deal.symbol, "BUY" if exit_deal.type==1 else "SELL", exit_deal.volume, profit, reason)
                            
                    if ticket in self.state["active_trades"]:
                        self.state["active_trades"].remove(ticket)

                save_state(self.state)

            # --- Cập nhật TSL cho lệnh đang chạy ---
            for pos in current_positions:
                if pos.magic == config.MAGIC_NUMBER: 
                    status = self._apply_trailing_logic_parallel(pos, account_type)
                    tsl_status_map[pos.ticket] = status

        except Exception as e:
            self.log(f"Lỗi update loop: {e}")
        
        return tsl_status_map

    def _apply_trailing_logic_parallel(self, position, account_type="STANDARD"):
        tactic_str = self.get_trade_tactic(position.ticket)
        if tactic_str == "OFF": return "TSL OFF"

        active_modes = tactic_str.split("+")
        symbol, entry, current_sl, current_price = position.symbol, position.price_open, position.sl, position.price_current
        volume, is_buy = position.volume, (position.type == mt5.ORDER_TYPE_BUY)
        
        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info else 0.00001
        
        # Lấy mốc 1R (Risk Unit) từ Preset
        preset_name = position.comment.split("_")[1] if (position.comment and "_" in position.comment) else "SCALPING"
        params = config.PRESETS.get(preset_name, config.PRESETS["SCALPING"])
        one_r_dist = entry * (params["SL_PERCENT"] / 100.0)
        if one_r_dist == 0: return "Err R"

        curr_dist = current_price - entry if is_buy else entry - current_price
        curr_r = curr_dist / one_r_dist
        
        candidates = []
        status_previews = []
        tsl_cfg = config.TSL_CONFIG

        # ---------------------------------------------------------
        # 1. BREAK-EVEN (BE) - FIXED PRO FEE LOGIC
        # ---------------------------------------------------------
        if "BE" in active_modes:
            # Sửa logic tính Comm: PRO/STANDARD = 0
            comm_rate = 0.0 if account_type in ["PRO", "STANDARD"] else \
                        config.COMMISSION_RATES.get(symbol, config.ACCOUNT_TYPES_CONFIG.get(account_type, {}).get("COMMISSION_PER_LOT", 0.0))
            
            total_fee = (comm_rate * volume) + abs(getattr(position, 'swap', 0))
            fee_dist = total_fee / (volume * sym_info.trade_contract_size) if sym_info.trade_contract_size > 0 else 0
            
            mode = tsl_cfg.get("BE_MODE", "SOFT")
            base = entry - fee_dist if (is_buy and mode=="SOFT") else (entry + fee_dist if (is_buy and mode=="SMART") else entry)
            if not is_buy: base = entry + fee_dist if mode=="SOFT" else (entry - fee_dist if mode=="SMART" else entry)

            be_sl = base + (tsl_cfg.get("BE_OFFSET_POINTS", 0) * point) if is_buy else base - (tsl_cfg.get("BE_OFFSET_POINTS", 0) * point)
            trig_r = tsl_cfg.get("BE_OFFSET_RR", 0.8)
            
            if curr_r >= trig_r:
                candidates.append((be_sl, "BE"))
            else:
                trig_p = entry + (one_r_dist * trig_r) if is_buy else entry - (one_r_dist * trig_r)
                status_previews.append((1, f"BE | {trig_p:.2f} -> {be_sl:.2f}"))

        # ---------------------------------------------------------
        # 2. STEP R (Logic dời theo n bước)
        # ---------------------------------------------------------
        if "STEP_R" in active_modes:
            sz, rt = tsl_cfg.get("STEP_R_SIZE", 1.0), tsl_cfg.get("STEP_R_RATIO", 0.8)
            steps = math.floor(curr_r / sz)
            
            if steps >= 1:
                step_sl = entry + (steps * one_r_dist * rt) if is_buy else entry - (steps * one_r_dist * rt)
                candidates.append((step_sl, f"STEP {steps}"))
            
            next_step = steps + 1
            n_trig = entry + (next_step * sz * one_r_dist) if is_buy else entry - (next_step * sz * one_r_dist)
            n_sl = entry + (next_step * one_r_dist * rt) if is_buy else entry - (next_step * one_r_dist * rt)
            status_previews.append((3, f"Step {next_step} | {n_trig:.2f} -> {n_sl:.2f}"))

        # ---------------------------------------------------------
        # 3. PNL LOCK (Logic theo % vốn)
        # ---------------------------------------------------------
        if "PNL" in active_modes:
            acc = self.connector.get_account_info()
            if acc:
                pnl_pct = ((position.profit + getattr(position, 'swap', 0)) / acc['balance']) * 100
                levels = sorted(tsl_cfg["PNL_LEVELS"], key=lambda x: x[0])
                
                best_pnl_sl = None
                for lvl in levels:
                    if pnl_pct >= lvl[0]:
                        lock_dist = (acc['balance'] * (lvl[1]/100.0)) / (volume * sym_info.trade_contract_size)
                        best_pnl_sl = entry + lock_dist if is_buy else entry - lock_dist
                    else:
                        trig_p = entry + ((acc['balance'] * (lvl[0]/100.0)) / (volume * sym_info.trade_contract_size)) if is_buy else \
                                 entry - ((acc['balance'] * (lvl[0]/100.0)) / (volume * sym_info.trade_contract_size))
                        status_previews.append((2, f"PnL {lvl[0]}% | {trig_p:.2f}"))
                        break
                if best_pnl_sl: candidates.append((best_pnl_sl, "PNL"))

        # ---------------------------------------------------------
        # CHỌN SL TỐT NHẤT & THỰC THI
        # ---------------------------------------------------------
        valid_moves = []
        for price, rule in candidates:
            price = round(price / point) * point
            if is_buy and price > current_sl + point: valid_moves.append((price, rule))
            elif not is_buy and (current_sl == 0 or price < current_sl - point): valid_moves.append((price, rule))

        if valid_moves:
            best_move = max(valid_moves, key=lambda x: x[0]) if is_buy else min(valid_moves, key=lambda x: x[0])
            self.log(f"⚡ [TSL] #{position.ticket} [{best_move[1]}] ➔ SL: {best_move[0]}")
            self.connector.modify_position(position.ticket, best_move[0], position.tp)
            return f"MOVED {best_move[1]}"

        # Nếu chưa dời, hiển thị mục tiêu quan trọng nhất (Step > PnL > BE)
        if status_previews:
            return sorted(status_previews, key=lambda x: x[0], reverse=True)[0][1]

        return "Monitoring..."