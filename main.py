# -*- coding: utf-8 -*-
# FILE: main.py
# V5.1 FIX: Fixed Crash 'commission' & Added Fee Preview

import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import threading
import time
import sys
import json
import os
from datetime import datetime
import MetaTrader5 as mt5

import config
from core.exness_connector import ExnessConnector
from core.checklist_manager import ChecklistManager
from core.trade_manager import TradeManager
from core.storage_manager import load_state, save_state

TSL_SETTINGS_FILE = "data/tsl_settings.json"

class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PRO SCALPING V5.1 (STABLE FIX)")
        self.root.geometry("1200x820")
        self.root.configure(bg="#121212")
        self.root.attributes("-topmost", True)
        
        self.var_strict_mode = tk.BooleanVar(value=config.STRICT_MODE_DEFAULT)
        self.var_confirm_close = tk.BooleanVar(value=True)
        
        self.var_manual_lot = tk.StringVar(value="")
        self.var_manual_tp = tk.StringVar(value="")
        self.var_manual_sl = tk.StringVar(value="")
        self.var_bypass_checklist = tk.BooleanVar(value=config.MANUAL_CONFIG["BYPASS_CHECKLIST"])
        
        self.running = True
        self.load_tsl_settings()

        print(">>> Đang kết nối MT5...")
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> MT5 CONNECTED.")
        
        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)

        self.main_paned = tk.PanedWindow(root, orient="horizontal", bg="#121212")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        self.frm_left = tk.Frame(self.main_paned, bg="#1e1e1e", width=420)
        self.frm_right = tk.Frame(self.main_paned, bg="#252526", width=780)
        
        self.main_paned.add(self.frm_left)
        self.main_paned.add(self.frm_right)

        self.setup_left_panel()
        self.setup_right_panel()

        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log("Hệ thống V5.1 (Fix Crash) đã khởi động.")

    def load_tsl_settings(self):
        if os.path.exists(TSL_SETTINGS_FILE):
            try:
                with open(TSL_SETTINGS_FILE, "r") as f:
                    saved_cfg = json.load(f)
                    for k, v in saved_cfg.items():
                        if k in config.TSL_CONFIG:
                            config.TSL_CONFIG[k] = v
                print(">>> Đã load cấu hình TSL cá nhân.")
            except Exception as e:
                print(f"Lỗi load TSL settings: {e}")

    def save_tsl_settings(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(TSL_SETTINGS_FILE, "w") as f:
                json.dump(config.TSL_CONFIG, f, indent=4)
            print(">>> Đã lưu cấu hình TSL.")
        except Exception as e:
            print(f"Lỗi lưu TSL settings: {e}")

    def setup_left_panel(self):
        # HEADER
        self.lbl_equity = tk.Label(self.frm_left, text="$----", font=("Impact", 26), fg="#00e676", bg="#1e1e1e")
        self.lbl_equity.pack(pady=(15, 0))
        self.lbl_acc_info = tk.Label(self.frm_left, text="ID: --- | Server: ---", font=("Arial", 8), fg="#888", bg="#1e1e1e")
        self.lbl_acc_info.pack(pady=(2, 5))
        self.lbl_stats = tk.Label(self.frm_left, text="PnL: $0.00", font=("Arial", 12, "bold"), fg="white", bg="#1e1e1e")
        self.lbl_stats.pack(pady=(0, 5))

        btn_reset = tk.Button(self.frm_left, text="🔄 Reset Daily Stats", font=("Arial", 8), 
                              bg="#333333", fg="gray", bd=0, activebackground="#444", activeforeground="white",
                              command=self.reset_daily_stats)
        btn_reset.pack(pady=(0, 5))

        # SETUP BOX
        frm_setup = tk.LabelFrame(self.frm_left, text=" SETUP ", font=("Arial", 9, "bold"), fg="#FFD700", bg="#1e1e1e")
        frm_setup.pack(fill="x", padx=10, pady=5)

        f1 = tk.Frame(frm_setup, bg="#1e1e1e")
        f1.pack(fill="x", pady=5)
        self.cbo_symbol = ttk.Combobox(f1, values=config.COIN_LIST, state="readonly", width=8)
        self.cbo_symbol.set(config.DEFAULT_SYMBOL)
        self.cbo_symbol.pack(side="left", padx=5)
        
        self.cbo_preset = ttk.Combobox(f1, values=list(config.PRESETS.keys()), state="readonly", width=8)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.pack(side="left", padx=5)
        
        btn_tsl = tk.Button(f1, text="⚙ TSL", font=("Arial", 8, "bold"), bg="#444", fg="white", width=6, command=self.open_tsl_popup)
        btn_tsl.pack(side="left", padx=5)

        self.lbl_price = tk.Label(f1, text="0.00", font=("Consolas", 12, "bold"), fg="#00e676", bg="#1e1e1e")
        self.lbl_price.pack(side="right", padx=5)

        # MANUAL ENTRY
        frm_manual = tk.LabelFrame(self.frm_left, text=" MANUAL INPUT (Optional) ", font=("Arial", 9, "bold"), fg="#FF9800", bg="#1e1e1e")
        frm_manual.pack(fill="x", padx=10, pady=5)
        
        fm_grid = tk.Frame(frm_manual, bg="#1e1e1e")
        fm_grid.pack(fill="x", padx=5, pady=5)
        tk.Label(fm_grid, text="LOT:", fg="gray", bg="#1e1e1e").grid(row=0, column=0, padx=2)
        tk.Entry(fm_grid, textvariable=self.var_manual_lot, width=6, bg="#333", fg="white", insertbackground="white").grid(row=0, column=1, padx=2)
        tk.Label(fm_grid, text="TP:", fg="gray", bg="#1e1e1e").grid(row=0, column=2, padx=2)
        tk.Entry(fm_grid, textvariable=self.var_manual_tp, width=8, bg="#333", fg="white", insertbackground="white").grid(row=0, column=3, padx=2)
        tk.Label(fm_grid, text="SL:", fg="gray", bg="#1e1e1e").grid(row=0, column=4, padx=2)
        tk.Entry(fm_grid, textvariable=self.var_manual_sl, width=8, bg="#333", fg="white", insertbackground="white").grid(row=0, column=5, padx=2)
        tk.Checkbutton(frm_manual, text="Bypass Checklist (Force Trade)", variable=self.var_bypass_checklist, 
                       bg="#1e1e1e", fg="#ff5252", selectcolor="#1e1e1e", activebackground="#1e1e1e", font=("Arial", 8)).pack(anchor="w", padx=5)

        # PREVIEW (UPDATED FEE)
        frm_preview = tk.LabelFrame(self.frm_left, text=" PREVIEW ", font=("Arial", 9, "bold"), fg="#03A9F4", bg="#1e1e1e")
        frm_preview.pack(fill="x", padx=10, pady=5)
        
        # Line 1: Lot & Fee
        fp1 = tk.Frame(frm_preview, bg="#1e1e1e")
        fp1.pack(fill="x", padx=5, pady=2)
        self.lbl_preview_lot = tk.Label(fp1, text="Lot: ---", font=("Consolas", 12, "bold"), fg="white", bg="#1e1e1e")
        self.lbl_preview_lot.pack(side="left")
        
        # [NEW] Fee Preview
        self.lbl_preview_fee = tk.Label(fp1, text="Fee: ---", font=("Consolas", 10, "italic"), fg="#FFD700", bg="#1e1e1e")
        self.lbl_preview_fee.pack(side="right")
        
        # Line 2: Risk & Reward
        fp2 = tk.Frame(frm_preview, bg="#1e1e1e")
        fp2.pack(fill="x", padx=5, pady=2)
        self.lbl_preview_risk = tk.Label(fp2, text="Risk: ---", font=("Consolas", 10), fg="#ff5252", bg="#1e1e1e")
        self.lbl_preview_risk.pack(side="left")
        self.lbl_preview_reward = tk.Label(fp2, text="Rew: ---", font=("Consolas", 10), fg="#00e676", bg="#1e1e1e")
        self.lbl_preview_reward.pack(side="right")
        
        # Line 3: TP / SL
        fp3 = tk.Frame(frm_preview, bg="#1e1e1e")
        fp3.pack(fill="x", padx=5, pady=5)
        tk.Label(fp3, text="TP:", font=("Arial", 9, "bold"), fg="gray", bg="#1e1e1e").pack(side="left")
        self.lbl_preview_tp_val = tk.Label(fp3, text="---", font=("Consolas", 12, "bold"), fg="#00e676", bg="#1e1e1e")
        self.lbl_preview_tp_val.pack(side="left", padx=(0, 15))
        self.lbl_preview_sl_val = tk.Label(fp3, text="---", font=("Consolas", 12, "bold"), fg="#ff5252", bg="#1e1e1e")
        self.lbl_preview_sl_val.pack(side="right")
        tk.Label(fp3, text="SL:", font=("Arial", 9, "bold"), fg="gray", bg="#1e1e1e").pack(side="right")

        # CHECKLIST
        frm_check = tk.LabelFrame(self.frm_left, text=" CHECKLIST ", fg="gray", bg="#1e1e1e")
        frm_check.pack(fill="x", padx=10, pady=5)
        self.check_labels = {}
        check_keys = ["Mạng/Spread", "Daily Loss", "Số Lệnh Thua", "Số Lệnh", "Trạng thái"]
        for name in check_keys:
            l = tk.Label(frm_check, text=f"• {name}", font=("Arial", 9), bg="#1e1e1e", fg="gray", anchor="w")
            l.pack(fill="x", padx=5)
            self.check_labels[name] = l

        # BUTTONS
        f_btn = tk.Frame(self.frm_left, bg="#1e1e1e")
        f_btn.pack(pady=10)
        self.btn_long = tk.Button(f_btn, text="LONG", bg="#2e7d32", fg="white", font=("Arial", 12, "bold"), width=12, height=2,
                                  command=lambda: self.on_click_trade("BUY"))
        self.btn_long.grid(row=0, column=0, padx=5)
        self.btn_short = tk.Button(f_btn, text="SHORT", bg="#c62828", fg="white", font=("Arial", 12, "bold"), width=12, height=2,
                                   command=lambda: self.on_click_trade("SELL"))
        self.btn_short.grid(row=0, column=1, padx=5)

        # LOG
        tk.Label(self.frm_left, text="SYSTEM LOG:", font=("Arial", 8, "bold"), fg="gray", bg="#1e1e1e", anchor="w").pack(fill="x", padx=10)
        self.txt_log = tk.Text(self.frm_left, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def setup_right_panel(self):
        h_frame = tk.Frame(self.frm_right, bg="#252526")
        h_frame.pack(fill="x", pady=10, padx=5)
        
        tk.Label(h_frame, text="RUNNING TRADES", font=("Arial", 11, "bold"), fg="white", bg="#252526").pack(side="left")
        tk.Button(h_frame, text="📜 LỊCH SỬ HÔM NAY", bg="#424242", fg="white", font=("Arial", 8),
                  command=self.show_history_popup).pack(side="right")

        cols = ("Time", "Symbol", "Type", "Vol", "Entry", "SL", "Risk", "Est.Fee", "TSL", "PnL", "Close")
        self.tree = ttk.Treeview(self.frm_right, columns=cols, show="headings", height=25)
        
        self.tree.heading("Time", text="Time"); self.tree.column("Time", width=60, anchor="center")
        self.tree.heading("Symbol", text="Coin"); self.tree.column("Symbol", width=60, anchor="center")
        self.tree.heading("Type", text="Type"); self.tree.column("Type", width=40, anchor="center")
        self.tree.heading("Vol", text="Vol"); self.tree.column("Vol", width=40, anchor="center")
        self.tree.heading("Entry", text="Entry"); self.tree.column("Entry", width=60, anchor="center")
        self.tree.heading("SL", text="SL"); self.tree.column("SL", width=60, anchor="center")
        self.tree.heading("Risk", text="Risk ($)"); self.tree.column("Risk", width=60, anchor="center")
        self.tree.heading("Est.Fee", text="Est.Fee"); self.tree.column("Est.Fee", width=60, anchor="center")
        self.tree.heading("TSL", text="TSL Status"); self.tree.column("TSL", width=80, anchor="center")
        self.tree.heading("PnL", text="PnL ($)"); self.tree.column("PnL", width=70, anchor="center")
        self.tree.heading("Close", text="X"); self.tree.column("Close", width=30, anchor="center")
        
        self.tree.pack(fill="both", expand=True, padx=5)
        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)

        f_foot = tk.Frame(self.frm_right, bg="#252526")
        f_foot.pack(fill="x", pady=5, padx=5)
        tk.Checkbutton(f_foot, text="Hỏi xác nhận trước khi đóng lệnh (Safety)", variable=self.var_confirm_close,
                       bg="#252526", fg="white", selectcolor="#252526", activebackground="#252526").pack(anchor="w")

    def open_tsl_popup(self):
        top = Toplevel(self.root)
        top.title("Cấu hình TSL Nâng Cao")
        top.geometry("420x550")
        top.configure(bg="#1e1e1e")
        top.attributes("-topmost", True)

        def make_section(title):
            l = tk.Label(top, text=title, font=("Arial", 10, "bold"), fg="#03A9F4", bg="#1e1e1e", anchor="w")
            l.pack(fill="x", padx=10, pady=(15, 5))
            return tk.Frame(top, bg="#1e1e1e")

        # 1. MAIN SWITCH & STRATEGY
        f1 = make_section("1. CHIẾN THUẬT (Priority)")
        f1.pack(fill="x", padx=20)
        
        tk.Label(f1, text="Strategy:", fg="white", bg="#1e1e1e").pack(side="left")
        cbo_strat = ttk.Combobox(f1, values=["BEST_PRICE", "PRIORITY_PNL", "PRIORITY_BE"], state="readonly", width=15)
        cbo_strat.set(config.TSL_CONFIG.get("STRATEGY", "BEST_PRICE"))
        cbo_strat.pack(side="right")

        # 2. RULE BE
        f2 = make_section("2. BREAK-EVEN (Hoà Vốn)")
        f2.pack(fill="x", padx=20)
        
        f2_1 = tk.Frame(f2, bg="#1e1e1e")
        f2_1.pack(fill="x")
        tk.Label(f2_1, text="Mode:", fg="white", bg="#1e1e1e").pack(side="left")
        cbo_be_mode = ttk.Combobox(f2_1, values=["SOFT", "SMART", "HARD"], state="readonly", width=10)
        cbo_be_mode.set(config.TSL_CONFIG.get("BE_MODE", "SOFT"))
        cbo_be_mode.pack(side="right")
        tk.Label(f2, text="*SOFT: SL = Entry - Fee (Lỗ phí)\n*SMART: SL = Entry + Fee (Hoà tiền)\n*HARD: SL = Entry", 
                 font=("Arial", 8, "italic"), fg="gray", bg="#1e1e1e", justify="left").pack(anchor="w", pady=5)

        # 3. RULE PNL
        f3 = make_section("3. PNL PROTECTION (% Balance)")
        f3.pack(fill="x", padx=20)
        
        tk.Label(f3, text="Cấu hình các mốc bảo vệ lợi nhuận:", fg="gray", bg="#1e1e1e").pack(anchor="w", pady=(0,5))
        f3_h = tk.Frame(f3, bg="#1e1e1e")
        f3_h.pack(fill="x")
        tk.Label(f3_h, text="Trigger (%):", font=("Arial", 8), fg="#00e676", bg="#1e1e1e", width=15).pack(side="left")
        tk.Label(f3_h, text="Lock (%):", font=("Arial", 8), fg="#ff5252", bg="#1e1e1e", width=15).pack(side="right")
        
        current_levels = config.TSL_CONFIG.get("PNL_LEVELS", [])
        while len(current_levels) < 3: current_levels.append([0.0, 0.0])
        
        self.pnl_entries = []
        for i in range(3):
            row = tk.Frame(f3, bg="#1e1e1e")
            row.pack(fill="x", pady=2)
            e_trig = tk.Entry(row, width=10, bg="#333", fg="white", justify="center")
            e_trig.insert(0, str(current_levels[i][0]))
            e_trig.pack(side="left", padx=10)
            tk.Label(row, text="--->", fg="gray", bg="#1e1e1e").pack(side="left")
            e_lock = tk.Entry(row, width=10, bg="#333", fg="white", justify="center")
            e_lock.insert(0, str(current_levels[i][1]))
            e_lock.pack(side="right", padx=10)
            self.pnl_entries.append((e_trig, e_lock))

        # 4. RULE STEP
        f4 = make_section("4. STEP R (Gồng lời)")
        f4.pack(fill="x", padx=20)
        f4_1 = tk.Frame(f4, bg="#1e1e1e")
        f4_1.pack(fill="x")
        tk.Label(f4_1, text="Step Size (R):", fg="white", bg="#1e1e1e").pack(side="left")
        entry_step = tk.Entry(f4_1, width=10, bg="#333", fg="white", justify="right")
        entry_step.insert(0, str(config.TSL_CONFIG.get("STEP_SIZE_RR", 0.5)))
        entry_step.pack(side="right")

        def save_cfg():
            try:
                config.TSL_CONFIG["STRATEGY"] = cbo_strat.get()
                config.TSL_CONFIG["BE_MODE"] = cbo_be_mode.get()
                config.TSL_CONFIG["STEP_SIZE_RR"] = float(entry_step.get())
                new_levels = []
                for e_t, e_l in self.pnl_entries:
                    try:
                        t = float(e_t.get())
                        l = float(e_l.get())
                        if t > 0: new_levels.append([t, l])
                    except: pass
                new_levels.sort(key=lambda x: x[0])
                config.TSL_CONFIG["PNL_LEVELS"] = new_levels
                self.save_tsl_settings() 
                messagebox.showinfo("Success", "Đã lưu cấu hình TSL thành công!")
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Lỗi định dạng số: {e}")

        tk.Button(top, text="LƯU CẤU HÌNH", bg="#2e7d32", fg="white", font=("Arial", 10, "bold"), height=2,
                  command=save_cfg).pack(pady=30, fill="x", padx=30)

    def log(self, msg, error=False):
        timestamp = time.strftime("%H:%M:%S")
        text = f"[{timestamp}] {msg}\n"
        try:
            self.txt_log.config(state="normal")
            self.txt_log.insert("end", text)
            if error:
                self.txt_log.tag_add("err", "end-2l", "end-1c")
                self.txt_log.tag_config("err", foreground="#ff5252")
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")
        except: pass
    
    def reset_daily_stats(self):
        if messagebox.askyesno("Xác nhận", "Bạn muốn xóa toàn bộ Lãi/Lỗ và bộ đếm hôm nay về 0?"):
            self.trade_mgr.state["pnl_today"] = 0.0
            self.trade_mgr.state["trades_today_count"] = 0
            self.trade_mgr.state["daily_loss_count"] = 0
            self.trade_mgr.state["daily_history"] = []
            save_state(self.trade_mgr.state)
            self.log(">>> Đã Reset thủ công thống kê ngày!", True)

    def bg_update_loop(self):
        while self.running:
            try:
                sym = self.cbo_symbol.get()
                preset = self.cbo_preset.get()
                strict = self.var_strict_mode.get()
                self.trade_mgr.update_running_trades()
                acc = self.connector.get_account_info()
                state = self.trade_mgr.state
                check_res = self.checklist_mgr.run_pre_trade_checks(acc, state, sym, strict)
                tick = mt5.symbol_info_tick(sym)
                positions = self.connector.get_all_open_positions()
                my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]
                self.root.after(0, self.update_ui, acc, state, check_res, tick, preset, sym, my_pos)
            except Exception as e: print(e)
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui(self, acc, state, check_res, tick, preset, sym, positions):
        if acc: 
            self.lbl_equity.config(text=f"${acc['equity']:,.2f}")
            acc_id = acc.get('login', '---')
            acc_server = acc.get('server', '---')
            self.lbl_acc_info.config(text=f"ID: {acc_id} | Server: {acc_server}")

        pnl_color = "#00e676" if state["pnl_today"] >= 0 else "#ff5252"
        self.lbl_stats.config(text=f"PnL: ${state['pnl_today']:.2f}", fg=pnl_color)
        if tick: self.lbl_price.config(text=f"{tick.ask:.2f}")

        can_trade = check_res["passed"]
        is_bypass = self.var_bypass_checklist.get()
        if is_bypass: can_trade = True

        for item in check_res["checks"]:
            name = item["name"]
            stt = item["status"]
            msg = item["msg"]
            if stt == "OK": color = "#00e676"
            elif stt == "WARN": color = "#FFD700"
            else: color = "#ff5252"
            if name == "Daily Loss" and stt == "OK" and "-" in msg: color = "#ff9800"
            if name in self.check_labels:
                icon = "✔" if stt == "OK" else ("!" if stt == "WARN" else "✖")
                self.check_labels[name].config(text=f"{icon} {name}: {msg}", fg=color)

        state_btn = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != state_btn:
            self.btn_long.config(state=state_btn)
            self.btn_short.config(state=state_btn)

        if tick and acc:
            params = config.PRESETS.get(preset)
            equity = acc['equity']
            price = tick.ask
            contract_size = 1.0 
            sym_info = mt5.symbol_info(sym)
            if sym_info: contract_size = sym_info.trade_contract_size

            try: manual_lot = float(self.var_manual_lot.get()) if self.var_manual_lot.get() else 0
            except: manual_lot = 0
            try: manual_tp = float(self.var_manual_tp.get()) if self.var_manual_tp.get() else 0
            except: manual_tp = 0
            try: manual_sl = float(self.var_manual_sl.get()) if self.var_manual_sl.get() else 0
            except: manual_sl = 0

            sl_pct = params["SL_PERCENT"] / 100.0
            if manual_sl > 0: sl_dist = abs(price - manual_sl)
            else: sl_dist = price * sl_pct
            
            final_lot = 0.0
            if manual_lot > 0:
                final_lot = manual_lot
                risk_usd = final_lot * sl_dist * contract_size
            else:
                if config.LOT_SIZE_MODE == "FIXED": 
                    final_lot = config.FIXED_LOT_VOLUME
                    risk_usd = final_lot * sl_dist * contract_size
                else:
                    risk_to_spend = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
                    if sl_dist > 0:
                        raw_lot = risk_to_spend / (sl_dist * contract_size)
                        final_lot = max(config.MIN_LOT_SIZE, round(raw_lot / config.LOT_STEP) * config.LOT_STEP)
                        final_lot = min(final_lot, config.MAX_LOT_SIZE)
                        risk_usd = final_lot * sl_dist * contract_size
                    else:
                        risk_usd = 0

            if sl_dist > 0:
                self.lbl_preview_lot.config(text=f"Lot: {final_lot:.2f}")
                risk_pct = (risk_usd / equity * 100) if equity > 0 else 0
                self.lbl_preview_risk.config(text=f"Risk: ${risk_usd:.2f} ({risk_pct:.1f}%)")
                
                p_tp = manual_tp if manual_tp > 0 else (price + sl_dist * params["TP_RR_RATIO"])
                p_sl = manual_sl if manual_sl > 0 else (price - sl_dist)
                
                reward_dist = abs(p_tp - price)
                reward_usd = reward_dist * final_lot * contract_size
                reward_pct = (reward_usd / equity * 100) if equity > 0 else 0
                
                self.lbl_preview_reward.config(text=f"Rew: ${reward_usd:.2f} ({reward_pct:.1f}%)")
                self.lbl_preview_tp_val.config(text=f"{p_tp:.2f}")
                self.lbl_preview_sl_val.config(text=f"{p_sl:.2f}")

                # [FIXED] EST. FEE CALCULATION
                comm_rate = config.COMMISSION_RATES.get(sym, 0.0)
                spread_cost = 0.0
                if tick: # Spread cost = Spread * Vol * Contract
                    spread_val = (tick.ask - tick.bid)
                    spread_cost = spread_val * final_lot * contract_size
                
                total_est_fee = (comm_rate * final_lot) + spread_cost
                self.lbl_preview_fee.config(text=f"Est.Fee: -${total_est_fee:.2f}")

            else:
                self.lbl_preview_lot.config(text="Lot: ???")

        # TABLE UPDATE (FIXED CRASH)
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for p in positions:
            p_type = "BUY" if p.type == 0 else "SELL"
            time_str = datetime.fromtimestamp(p.time).strftime("%H:%M:%S")
            contract_size = 1.0
            sym_info = mt5.symbol_info(p.symbol)
            current_tick = mt5.symbol_info_tick(p.symbol)
            if sym_info: contract_size = sym_info.trade_contract_size
            
            risk_val = 0.0
            if p.sl > 0:
                 sl_dist = abs(p.price_open - p.sl)
                 risk_val = sl_dist * contract_size * p.volume

            comm_rate = config.COMMISSION_RATES.get(p.symbol, 0.0)
            comm_val = comm_rate * p.volume
            spread_cost = 0.0
            if current_tick and sym_info:
                spread_val = (current_tick.ask - current_tick.bid)
                spread_cost = spread_val * contract_size * p.volume
            
            # [FIX CRASH] Use getattr for safety
            swap_val = getattr(p, 'swap', 0.0)
            total_fee_est = comm_val + spread_cost + abs(swap_val)

            is_tsl_on = self.trade_mgr.is_tsl_active(p.ticket)
            tsl_info = "[PAUSED]"
            if is_tsl_on:
                mode = config.TSL_CONFIG.get("BE_MODE", "SOFT")
                tsl_info = f"ON ({mode})"

            # [FIX CRASH] Use getattr for safety
            total_profit = p.profit + swap_val + getattr(p, 'commission', 0.0)

            self.tree.insert("", "end", iid=p.ticket, values=(
                time_str, p.symbol, p_type, p.volume,
                f"{p.price_open:.2f}", f"{p.sl:.2f}", 
                f"${risk_val:.2f}", 
                f"-${total_fee_est:.2f}", 
                tsl_info,
                f"{total_profit:.2f}", "[ ❌ ]"
            ))

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            row_id = self.tree.identify_row(event.y)
            col_id = self.tree.identify_column(event.x)
            if not row_id: return
            ticket = int(row_id)
            if col_id == "#9": 
                new_state = self.trade_mgr.toggle_tsl(ticket)
                state_str = "BẬT" if new_state else "TẮT"
                self.log(f"Đã {state_str} TSL cho lệnh #{ticket}")
            elif col_id == "#11": 
                self.handle_close_request(ticket)

    def handle_close_request(self, ticket):
        positions = self.connector.get_all_open_positions()
        target = next((p for p in positions if p.ticket == ticket), None)
        if not target:
            self.log("Lệnh không còn tồn tại.", True)
            return
        if self.var_confirm_close.get():
            if not messagebox.askyesno("Xác nhận", f"Bạn chắc chắn muốn đóng lệnh #{ticket}?"):
                return
        self.log(f"Đang đóng lệnh #{ticket}...")
        threading.Thread(target=lambda: self.connector.close_position(target)).start()

    def on_click_trade(self, direction):
        s = self.cbo_symbol.get()
        p = self.cbo_preset.get()
        strict = self.var_strict_mode.get()
        
        try: m_lot = float(self.var_manual_lot.get())
        except: m_lot = 0.0
        try: m_tp = float(self.var_manual_tp.get())
        except: m_tp = 0.0
        try: m_sl = float(self.var_manual_sl.get())
        except: m_sl = 0.0
        bypass = self.var_bypass_checklist.get()

        self.log(f"Đang gửi lệnh {direction} {s} (Bypass={bypass})...")
        def run():
            res = self.trade_mgr.execute_manual_trade(direction, p, s, strict, manual_lot=m_lot, manual_tp=m_tp, manual_sl=m_sl, bypass_checklist=bypass)
            if res == "SUCCESS": 
                self.root.after(0, lambda: self.log(f"✅ Đã khớp lệnh {direction} {s}!", False))
            elif res.startswith("ERR_LOT_TOO_SMALL"):
                self.root.after(0, lambda: messagebox.showwarning("Vốn nhỏ", f"Không thể vào lệnh: {res}"))
            elif res == "CHECKLIST_FAIL":
                self.root.after(0, lambda: messagebox.showerror("Blocked", "Vi phạm Checklist! (Tick 'Bypass' nếu muốn ép lệnh)"))
            else:
                self.root.after(0, lambda: self.log(f"❌ LỖI: {res}", True))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Lỗi: {res}"))
        threading.Thread(target=run).start()

    def show_history_popup(self):
        top = Toplevel(self.root)
        top.title("Lịch Sử Giao Dịch Hôm Nay")
        top.geometry("750x450")
        top.configure(bg="#1e1e1e")
        lbl_title = tk.Label(top, text=f"SESSION: {self.trade_mgr.state.get('date', 'N/A')}", 
                             font=("Arial", 12, "bold"), fg="#FFD700", bg="#1e1e1e")
        lbl_title.pack(pady=10)
        cols = ("Time", "Symbol", "Type", "PnL", "Reason")
        tree = ttk.Treeview(top, columns=cols, show="headings", height=12)
        tree.heading("Time", text="Time"); tree.column("Time", width=80, anchor="center")
        tree.heading("Symbol", text="Coin"); tree.column("Symbol", width=80, anchor="center")
        tree.heading("Type", text="Type"); tree.column("Type", width=60, anchor="center")
        tree.heading("PnL", text="PnL ($)"); tree.column("PnL", width=80, anchor="center")
        tree.heading("Reason", text="Reason"); tree.column("Reason", width=150, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=5)
        hist_data = self.trade_mgr.state.get("daily_history", [])
        total_pnl = 0
        for item in hist_data:
            pnl = item['profit']
            total_pnl += pnl
            tag = "win" if pnl >= 0 else "loss"
            tree.insert("", "end", values=(item.get('time'), item.get('symbol'), item.get('type'), f"${pnl:.2f}", item.get('reason')), tags=(tag,))
        tree.tag_configure("win", foreground="#00e676")
        tree.tag_configure("loss", foreground="#ff5252")
        lbl_sum = tk.Label(top, text=f"Tổng PnL Session: ${total_pnl:.2f} | Tổng lệnh: {len(hist_data)}",
                           font=("Consolas", 11, "bold"), fg="white", bg="#1e1e1e")
        lbl_sum.pack(pady=10)
        tk.Button(top, text="Đóng", command=top.destroy, bg="#424242", fg="white").pack(pady=5)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit()