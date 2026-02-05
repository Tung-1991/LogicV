# -*- coding: utf-8 -*-
# FILE: main.py
# V7.1: UI REMASTERED - CLEAN & BIG DATA - SCROLLBAR KEPT

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, Menu
import threading
import time
import sys
import json
import os
from datetime import datetime
import MetaTrader5 as mt5

# --- IMPORT MODULES ---
import config
from core.exness_connector import ExnessConnector
from core.checklist_manager import ChecklistManager
from core.trade_manager import TradeManager
from core.storage_manager import load_state, save_state

TSL_SETTINGS_FILE = "data/tsl_settings.json"

# --- CẤU HÌNH GIAO DIỆN ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Font cấu hình mới (To và Rõ hơn)
FONT_MAIN = ("Roboto", 13)
FONT_BOLD = ("Roboto", 13, "bold")
FONT_EQUITY = ("Roboto", 36, "bold") # Equity siêu to
FONT_PNL = ("Roboto", 18, "bold")
FONT_SECTION = ("Roboto", 12, "bold")
FONT_BIG_VAL = ("Consolas", 20, "bold") # Số liệu Risk/Reward to

class BotUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window Config
        self.title("PRO SCALPING V7.1 - DASHBOARD")
        self.geometry("1450x900")
        
        # --- Variables ---
        self.var_strict_mode = tk.BooleanVar(value=config.STRICT_MODE_DEFAULT)
        self.var_confirm_close = tk.BooleanVar(value=True)
        self.var_account_type = tk.StringVar(value=config.DEFAULT_ACCOUNT_TYPE)
        
        self.var_manual_lot = tk.StringVar(value="")
        self.var_manual_tp = tk.StringVar(value="")
        self.var_manual_sl = tk.StringVar(value="")
        self.var_bypass_checklist = tk.BooleanVar(value=config.MANUAL_CONFIG["BYPASS_CHECKLIST"])
        self.var_direction = tk.StringVar(value="BUY") 
        
        self.running = True
        self.load_tsl_settings()

        print(">>> Đang kết nối MT5...")
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> MT5 CONNECTED.")
        
        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)

        # --- GRID LAYOUT CHÍNH ---
        self.grid_columnconfigure(0, weight=0, minsize=420) # Cột trái cố định size
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)

        # =========================================================
        # PANEL TRÁI (CONTROLS) - GIỮ SCROLLBAR
        # =========================================================
        self.frm_left = ctk.CTkScrollableFrame(self, width=400, corner_radius=0, label_text="")
        self.frm_left.grid(row=0, column=0, sticky="nswe")
        self.frm_left.grid_columnconfigure(0, weight=1)

        self.setup_left_panel(self.frm_left)

        # =========================================================
        # PANEL PHẢI (DATA & LOG)
        # =========================================================
        self.frm_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frm_right.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)
        
        self.setup_right_panel(self.frm_right)

        # --- LOOP & THREAD ---
        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log("Giao diện V7.1 đã khởi động.")

    # ==================================================================
    # SETUP LEFT PANEL (UI MỚI)
    # ==================================================================
    def setup_left_panel(self, parent):
        # 1. HEADER: EQUITY & PNL (Gộp lại cho gọn)
        f_top = ctk.CTkFrame(parent, fg_color="#1a1a1a", corner_radius=8)
        f_top.pack(fill="x", pady=(5, 10), padx=5)
        
        self.lbl_equity = ctk.CTkLabel(f_top, text="$----", font=FONT_EQUITY, text_color="#00e676")
        self.lbl_equity.pack(pady=(15, 0))
        
        f_pnl = ctk.CTkFrame(f_top, fg_color="transparent")
        f_pnl.pack(pady=(0, 10))
        
        self.lbl_stats = ctk.CTkLabel(f_pnl, text="Today: $0.00", font=FONT_PNL, text_color="white")
        self.lbl_stats.pack(side="left", padx=5)
        # Nút refresh nhỏ
        ctk.CTkButton(f_pnl, text="⟳", width=30, height=20, fg_color="#333", hover_color="#444", 
                      command=self.reset_daily_stats).pack(side="left", padx=5)

        self.lbl_acc_info = ctk.CTkLabel(f_top, text="ID: --- | Server: ---", font=("Roboto", 10), text_color="gray")
        self.lbl_acc_info.pack(pady=(0, 5))

        # 2. SETTINGS & INFO (Gọn gàng hơn)
        f_set = ctk.CTkFrame(parent, fg_color="transparent")
        f_set.pack(fill="x", padx=5, pady=5)
        f_set.columnconfigure(1, weight=1)

        # Hàng 1: Coin + Market Price (Nhỏ gọn)
        ctk.CTkLabel(f_set, text="COIN:", font=FONT_SECTION, text_color="gray").grid(row=0, column=0, sticky="w")
        
        f_coin_row = ctk.CTkFrame(f_set, fg_color="transparent")
        f_coin_row.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.cbo_symbol = ctk.CTkOptionMenu(f_coin_row, values=config.COIN_LIST, font=FONT_BOLD, width=120)
        self.cbo_symbol.set(config.DEFAULT_SYMBOL)
        self.cbo_symbol.pack(side="left")
        
        self.lbl_price = ctk.CTkLabel(f_coin_row, text="0.00", font=("Consolas", 14), text_color="#00e676")
        self.lbl_price.pack(side="right", padx=10)

        # Hàng 2: Preset + Acc Type
        ctk.CTkLabel(f_set, text="MODE:", font=FONT_SECTION, text_color="gray").grid(row=1, column=0, sticky="w", pady=5)
        
        f_mode_row = ctk.CTkFrame(f_set, fg_color="transparent")
        f_mode_row.grid(row=1, column=1, sticky="ew", padx=5)
        
        self.cbo_preset = ctk.CTkOptionMenu(f_mode_row, values=list(config.PRESETS.keys()), font=FONT_MAIN, width=100)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.pack(side="left", fill="x", expand=True, padx=(0,2))

        self.cbo_account_type = ctk.CTkOptionMenu(f_mode_row, values=list(config.ACCOUNT_TYPES_CONFIG.keys()), font=FONT_MAIN, width=80)
        self.cbo_account_type.set(config.DEFAULT_ACCOUNT_TYPE)
        self.cbo_account_type.pack(side="right", fill="x", padx=(2,0))

        # Hàng 3: TSL Button + Force Trade Checkbox (Gom vào đây)
        f_tools = ctk.CTkFrame(f_set, fg_color="transparent")
        f_tools.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 5))
        
        ctk.CTkButton(f_tools, text="⚙ TSL CONFIG", font=("Roboto", 11, "bold"), height=24, 
                      fg_color="#424242", hover_color="#616161",
                      command=self.open_tsl_popup).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.chk_force = ctk.CTkCheckBox(f_tools, text="Force Trade (Bỏ qua Check)", variable=self.var_bypass_checklist, 
                        font=("Roboto", 11), text_color="#ccc", checkbox_width=20, checkbox_height=20)
        self.chk_force.pack(side="right")

        # 3. MANUAL INPUT (Thẳng hàng)
        f_input = ctk.CTkFrame(parent, fg_color="transparent")
        f_input.pack(fill="x", padx=5, pady=10)
        f_input.grid_columnconfigure((0,1,2), weight=1)

        def make_inp(p, title, var, col):
            f = ctk.CTkFrame(p, fg_color="#2b2b2b", corner_radius=6)
            f.grid(row=0, column=col, padx=3, sticky="ew")
            ctk.CTkLabel(f, text=title, font=("Roboto", 10, "bold"), text_color="#aaa").pack(pady=(2,0))
            e = ctk.CTkEntry(f, textvariable=var, font=("Consolas", 14, "bold"), height=30, 
                             justify="center", fg_color="transparent", border_width=0)
            e.pack(fill="x")
            return e

        make_inp(f_input, "VOL (Lot)", self.var_manual_lot, 0)
        make_inp(f_input, "TP (Price)", self.var_manual_tp, 1)
        make_inp(f_input, "SL (Price)", self.var_manual_sl, 2)

        # 4. BIG DATA DISPLAY (Risk/Reward) - ĐIỂM NHẤN
        f_dashboard = ctk.CTkFrame(parent, fg_color="#252526", corner_radius=8, border_width=1, border_color="#333")
        f_dashboard.pack(fill="x", padx=5, pady=5)
        
        # Header Info
        f_head_db = ctk.CTkFrame(f_dashboard, fg_color="transparent")
        f_head_db.pack(fill="x", padx=10, pady=5)
        self.lbl_prev_lot = ctk.CTkLabel(f_head_db, text="LOT: 0.00", font=FONT_BOLD, text_color="#FFD700")
        self.lbl_prev_lot.pack(side="left")
        self.lbl_fee_info = ctk.CTkLabel(f_head_db, text="Fee: $0.00", font=("Roboto", 11), text_color="gray")
        self.lbl_fee_info.pack(side="right")
        
        ctk.CTkFrame(f_dashboard, height=1, fg_color="#444").pack(fill="x", padx=5) # Line

        # Grid Risk/Reward
        f_grid_db = ctk.CTkFrame(f_dashboard, fg_color="transparent")
        f_grid_db.pack(fill="x", padx=5, pady=5)
        f_grid_db.columnconfigure((0,1), weight=1)

        # Cột Reward (Xanh)
        f_rew = ctk.CTkFrame(f_grid_db, fg_color="transparent")
        f_rew.grid(row=0, column=0, sticky="nsew", padx=2)
        ctk.CTkLabel(f_rew, text="TARGET (TP)", font=("Roboto", 10), text_color="#00C853").pack()
        self.lbl_prev_tp = ctk.CTkLabel(f_rew, text="---", font=("Consolas", 14), text_color="#00e676")
        self.lbl_prev_tp.pack()
        self.lbl_prev_rew = ctk.CTkLabel(f_rew, text="+$0.0", font=FONT_BIG_VAL, text_color="#00e676")
        self.lbl_prev_rew.pack()

        # Cột Risk (Đỏ)
        f_risk = ctk.CTkFrame(f_grid_db, fg_color="transparent")
        f_risk.grid(row=0, column=1, sticky="nsew", padx=2)
        ctk.CTkLabel(f_risk, text="STOPLOSS (SL)", font=("Roboto", 10), text_color="#ff5252").pack()
        self.lbl_prev_sl = ctk.CTkLabel(f_risk, text="---", font=("Consolas", 14), text_color="#ff5252")
        self.lbl_prev_sl.pack()
        self.lbl_prev_risk = ctk.CTkLabel(f_risk, text="-$0.0", font=FONT_BIG_VAL, text_color="#ff5252")
        self.lbl_prev_risk.pack()

        # 5. ACTION BUTTONS (Gọn hơn)
        self.seg_direction = ctk.CTkSegmentedButton(parent, values=["BUY", "SELL"], font=("Roboto", 14, "bold"), 
                                                    command=self.on_direction_change, height=32,
                                                    selected_color="#00C853", selected_hover_color="#009624")
        self.seg_direction.set("BUY")
        self.seg_direction.pack(fill="x", padx=10, pady=(15, 5))

        self.btn_action = ctk.CTkButton(parent, text="EXECUTE BUY", font=("Roboto", 16, "bold"), height=45, 
                                        fg_color="#00C853", hover_color="#009624", command=self.on_click_trade)
        self.btn_action.pack(fill="x", padx=10, pady=(0, 10))

        # 6. SYSTEM HEALTH
        f_sys = ctk.CTkFrame(parent, fg_color="#1a1a1a")
        f_sys.pack(fill="x", padx=5, pady=(10, 20))
        
        ctk.CTkLabel(f_sys, text=" STATUS CHECKS", font=("Roboto", 11, "bold"), text_color="gray").pack(anchor="w", padx=5, pady=(5,0))
        
        self.check_labels = {}
        checks = ["Mạng/Spread", "Daily Loss", "Số Lệnh Thua", "Số Lệnh", "Trạng thái"]
        for name in checks:
            l = ctk.CTkLabel(f_sys, text=f"• {name}", font=("Roboto", 12), text_color="gray", anchor="w")
            l.pack(fill="x", padx=10)
            self.check_labels[name] = l

    # ==================================================================
    # SETUP RIGHT PANEL
    # ==================================================================
    def setup_right_panel(self, parent):
        f_head = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        f_head.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(f_head, text="RUNNING TRADES", font=("Roboto", 16, "bold")).pack(side="left")
        ctk.CTkButton(f_head, text="History", width=80, height=24, command=self.show_history_popup, fg_color="#444").pack(side="right")

        f_tree_container = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        f_tree_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=30, font=("Arial", 11))
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", font=("Arial", 11, "bold"), relief="flat")
        style.map("Treeview", background=[('selected', '#3949ab')])

        cols = ("Time", "Symbol", "Type", "Vol", "Entry", "SL", "TP", "Swap", "Comm", "PnL", "X")
        self.tree = ttk.Treeview(f_tree_container, columns=cols, show="headings", style="Treeview")
        
        headers = ["Time", "Coin", "Type", "Vol", "Entry", "SL", "TP", "Swap", "Fee", "PnL", "✖"]
        widths = [60, 70, 50, 50, 80, 80, 80, 50, 50, 90, 30]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="center")

        sb = ttk.Scrollbar(f_tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", padx=2, pady=2)

        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.on_tree_right_click)

        f_log = ctk.CTkFrame(parent, height=150, fg_color="#1e1e1e")
        f_log.pack(fill="x", pady=(10, 0))
        f_log.pack_propagate(False)

        f_log_head = ctk.CTkFrame(f_log, fg_color="transparent", height=25)
        f_log_head.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f_log_head, text="SYSTEM LOG", font=("Roboto", 11, "bold"), text_color="#aaa").pack(side="left")
        ctk.CTkCheckBox(f_log_head, text="Safe Close", variable=self.var_confirm_close, font=("Roboto", 10), checkbox_width=16, checkbox_height=16).pack(side="right")

        self.txt_log = ctk.CTkTextbox(f_log, font=("Consolas", 11), text_color="#00e676", fg_color="black")
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=(0,5))
        self.txt_log.configure(state="disabled")

    # ==================================================================
    # LOGIC FUNCTIONS
    # ==================================================================
    def on_direction_change(self, value):
        self.var_direction.set(value)
        sym = self.cbo_symbol.get()
        if value == "BUY":
            self.btn_action.configure(text=f"BUY {sym}", fg_color="#00C853", hover_color="#009624")
            self.seg_direction.configure(selected_color="#00C853", selected_hover_color="#009624")
        else:
            self.btn_action.configure(text=f"SELL {sym}", fg_color="#D50000", hover_color="#B71C1C")
            self.seg_direction.configure(selected_color="#D50000", selected_hover_color="#B71C1C")

    def load_tsl_settings(self):
        if os.path.exists(TSL_SETTINGS_FILE):
            try:
                with open(TSL_SETTINGS_FILE, "r") as f:
                    saved_cfg = json.load(f)
                    for k, v in saved_cfg.items():
                        if k in config.TSL_CONFIG: config.TSL_CONFIG[k] = v
            except Exception as e: print(f"Lỗi load TSL: {e}")

    def save_tsl_settings(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(TSL_SETTINGS_FILE, "w") as f:
                json.dump(config.TSL_CONFIG, f, indent=4)
        except Exception: pass

    def get_fee_config(self, symbol):
        # 1. Ưu tiên Config riêng cho Symbol (BTC/ETH)
        specific_rate = config.COMMISSION_RATES.get(symbol, 0.0)
        if specific_rate > 0: return specific_rate
        
        # 2. Nếu không có, lấy theo loại tài khoản
        acc_type = self.cbo_account_type.get()
        acc_cfg = config.ACCOUNT_TYPES_CONFIG.get(acc_type, config.ACCOUNT_TYPES_CONFIG["STANDARD"])
        return acc_cfg["COMMISSION_PER_LOT"]

    def on_tree_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            ticket = int(row_id)
            menu = Menu(self, tearoff=0)
            menu.add_command(label=f"📝 Edit TP/SL (#{ticket})", command=lambda: self.open_edit_popup(ticket))
            menu.add_separator()
            is_tsl = self.trade_mgr.is_tsl_active(ticket)
            tsl_text = "Tắt TSL" if is_tsl else "Bật TSL"
            menu.add_command(label=f"⚙ {tsl_text}", command=lambda: self.trade_mgr.toggle_tsl(ticket))
            menu.add_separator()
            menu.add_command(label="❌ Close Now", command=lambda: self.handle_close_request(ticket))
            menu.post(event.x_root, event.y_root)

    def open_edit_popup(self, ticket):
        positions = self.connector.get_all_open_positions()
        pos = next((p for p in positions if p.ticket == ticket), None)
        if not pos: return

        top = ctk.CTkToplevel(self)
        top.title(f"Edit #{ticket}")
        top.geometry("250x200")
        top.attributes("-topmost", True)

        ctk.CTkLabel(top, text="NEW SL:", font=FONT_BOLD).pack(pady=(15, 5))
        ent_sl = ctk.CTkEntry(top, justify="center"); ent_sl.insert(0, str(pos.sl)); ent_sl.pack()

        ctk.CTkLabel(top, text="NEW TP:", font=FONT_BOLD).pack(pady=(5, 5))
        ent_tp = ctk.CTkEntry(top, justify="center"); ent_tp.insert(0, str(pos.tp)); ent_tp.pack()

        def save():
            try:
                self.connector.modify_position(ticket, float(ent_sl.get()), float(ent_tp.get()))
                top.destroy()
                self.log(f"Đã gửi lệnh sửa #{ticket}")
            except: pass

        ctk.CTkButton(top, text="UPDATE", height=35, fg_color="#2e7d32", command=save).pack(pady=20)

    def open_tsl_popup(self):
        top = ctk.CTkToplevel(self)
        top.title("TSL Config")
        top.geometry("400x550")
        top.attributes("-topmost", True)

        def sec(t):
            l = ctk.CTkLabel(top, text=t, font=("Roboto", 12, "bold"), text_color="#03A9F4")
            l.pack(fill="x", padx=20, pady=(15, 5), anchor="w")
            return ctk.CTkFrame(top, fg_color="transparent")

        f1 = sec("STRATEGY")
        f1.pack(fill="x", padx=20)
        cbo_strat = ctk.CTkOptionMenu(f1, values=["BEST_PRICE", "PRIORITY_PNL", "PRIORITY_BE"])
        cbo_strat.set(config.TSL_CONFIG.get("STRATEGY", "BEST_PRICE"))
        cbo_strat.pack(fill="x")

        f2 = sec("BREAK-EVEN (Dời hòa vốn)")
        f2.pack(fill="x", padx=20)
        cbo_be = ctk.CTkOptionMenu(f2, values=["SOFT", "SMART"])
        cbo_be.set(config.TSL_CONFIG.get("BE_MODE", "SOFT"))
        cbo_be.pack(fill="x")

        f3 = sec("PNL LOCK (% Lãi -> % Lock)")
        f3.pack(fill="x", padx=20)
        entries = []
        cur = config.TSL_CONFIG.get("PNL_LEVELS", [])
        while len(cur) < 3: cur.append([0.0, 0.0])
        for i in range(3):
            r = ctk.CTkFrame(f3, fg_color="transparent"); r.pack(fill="x", pady=2)
            e1 = ctk.CTkEntry(r, width=70); e1.insert(0, str(cur[i][0])); e1.pack(side="left")
            ctk.CTkLabel(r, text="⮕", text_color="gray").pack(side="left", padx=10)
            e2 = ctk.CTkEntry(r, width=70); e2.insert(0, str(cur[i][1])); e2.pack(side="right")
            entries.append((e1, e2))

        def save_cfg():
            config.TSL_CONFIG["STRATEGY"] = cbo_strat.get()
            config.TSL_CONFIG["BE_MODE"] = cbo_be.get()
            nl = []
            for e1, e2 in entries:
                try: nl.append([float(e1.get()), float(e2.get())])
                except: pass
            config.TSL_CONFIG["PNL_LEVELS"] = nl
            self.save_tsl_settings()
            top.destroy()
            self.log("Đã lưu cấu hình TSL.")

        ctk.CTkButton(top, text="LƯU CẤU HÌNH", height=40, font=("Roboto", 13, "bold"), command=save_cfg).pack(pady=30, fill="x", padx=40)

    def log(self, msg, error=False):
        ts = time.strftime("%H:%M:%S")
        txt = f"[{ts}] {msg}\n"
        try:
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", txt)
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        except: pass
    
    def reset_daily_stats(self):
        if messagebox.askyesno("Confirm", "Reset toàn bộ PnL & Lệnh hôm nay?"):
            self.trade_mgr.state["pnl_today"] = 0.0
            self.trade_mgr.state["trades_today_count"] = 0
            self.trade_mgr.state["daily_loss_count"] = 0
            self.trade_mgr.state["daily_history"] = []
            save_state(self.trade_mgr.state)
            self.log("Đã Reset thống kê ngày.", True)

    def bg_update_loop(self):
        while self.running:
            try:
                sym = self.cbo_symbol.get()
                self.trade_mgr.update_running_trades(self.cbo_account_type.get())
                acc = self.connector.get_account_info()
                tick = mt5.symbol_info_tick(sym)
                positions = self.connector.get_all_open_positions()
                my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]
                self.after(0, self.update_ui, acc, self.trade_mgr.state, 
                                self.checklist_mgr.run_pre_trade_checks(acc, self.trade_mgr.state, sym, self.var_strict_mode.get()), 
                                tick, self.cbo_preset.get(), sym, my_pos)
            except Exception as e:
                print(e)
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui(self, acc, state, check_res, tick, preset, sym, positions):
        d = self.seg_direction.get()
        self.var_direction.set(d)

        if acc: 
            self.lbl_equity.configure(text=f"${acc['equity']:,.2f}")
            self.lbl_acc_info.configure(text=f"ID: {acc['login']} | Server: {acc['server']}")

        pnl = state['pnl_today']
        self.lbl_stats.configure(text=f"Today: ${pnl:.2f}", text_color="#00e676" if pnl >= 0 else "#ff5252")
        
        if tick: 
            self.lbl_price.configure(text=f"{tick.ask:.2f}")

        can_trade = check_res["passed"] or self.var_bypass_checklist.get()
        
        for item in check_res["checks"]:
            name, stt, msg = item["name"], item["status"], item["msg"]
            color = "#00e676" if stt == "OK" else ("#FFAB00" if stt == "WARN" else "#ff5252")
            if name in self.check_labels:
                icon = "✔" if stt == "OK" else "✖"
                short_msg = msg.split(':')[0] + "..." if len(msg) > 30 else msg 
                self.check_labels[name].configure(text=f"{icon} {name}: {short_msg}", text_color=color)

        if d == "BUY":
            self.btn_action.configure(text=f"EXECUTE BUY", fg_color="#00C853", hover_color="#009624")
            self.lbl_price.configure(text_color="#00e676")
        else:
            self.btn_action.configure(text=f"EXECUTE SELL", fg_color="#D50000", hover_color="#B71C1C")
            self.lbl_price.configure(text_color="#ff5252")
            
        st = "normal" if can_trade else "disabled"
        if self.btn_action._state != st: self.btn_action.configure(state=st)

        if tick and acc:
            params = config.PRESETS.get(preset)
            try: mlot = float(self.var_manual_lot.get())
            except: mlot = 0.0
            
            contract_size = mt5.symbol_info(sym).trade_contract_size
            entry_price = tick.ask if d == "BUY" else tick.bid
            
            sl_dist = 0
            final_lot = 0
            
            if mlot > 0:
                final_lot = mlot
                try: msl = float(self.var_manual_sl.get())
                except: msl = 0
                if msl > 0: sl_dist = abs(entry_price - msl)
                else: sl_dist = entry_price * (params["SL_PERCENT"]/100)
            else:
                sl_dist = entry_price * (params["SL_PERCENT"]/100)
                risk_usd = acc['equity'] * (config.RISK_PER_TRADE_PERCENT/100)
                if sl_dist > 0 and contract_size > 0:
                    raw = risk_usd / (sl_dist * contract_size)
                    final_lot = round(raw / config.LOT_STEP) * config.LOT_STEP
                    final_lot = max(config.MIN_LOT_SIZE, min(final_lot, config.MAX_LOT_SIZE))
                else: final_lot = 0
            
            lot_txt_color = "white" if mlot == 0 else "#FFD700"
            lot_src = "(MANUAL)" if mlot > 0 else "(AUTO)"
            self.lbl_prev_lot.configure(text=f"{lot_src} LOT: {final_lot}", text_color=lot_txt_color)

            # --- TÍNH PHÍ (ĐÃ SỬA LOGIC LẤY TỪ CONFIG) ---
            comm_per_lot = self.get_fee_config(sym)
            est_comm = comm_per_lot * final_lot
            spread_points = tick.ask - tick.bid
            est_spread_cost = spread_points * final_lot * contract_size
            total_instant_fee = est_comm + est_spread_cost
            
            self.lbl_fee_info.configure(text=f"Fee: -${total_instant_fee:.2f} (Com:{est_comm:.1f}|Spr:{est_spread_cost:.1f})")

            # --- TÍNH TOÁN RISK/REWARD ---
            if sl_dist > 0:
                if d == "BUY":
                    p_sl = entry_price - sl_dist
                    p_tp = entry_price + (sl_dist * params["TP_RR_RATIO"])
                else:
                    p_sl = entry_price + sl_dist
                    p_tp = entry_price - (sl_dist * params["TP_RR_RATIO"])
                
                try: mtp = float(self.var_manual_tp.get())
                except: mtp = 0
                try: msl = float(self.var_manual_sl.get())
                except: msl = 0
                
                if mtp > 0: p_tp = mtp
                if msl > 0: p_sl = msl
                
                # Tính tiền
                risk_dist = abs(entry_price - p_sl)
                rew_dist = abs(p_tp - entry_price)
                risk_money = risk_dist * final_lot * contract_size
                rew_money = rew_dist * final_lot * contract_size

                self.lbl_prev_tp.configure(text=f"{p_tp:.2f}")
                self.lbl_prev_sl.configure(text=f"{p_sl:.2f}")
                self.lbl_prev_risk.configure(text=f"-${risk_money:.2f}")
                self.lbl_prev_rew.configure(text=f"+${rew_money:.2f}")
            else:
                self.lbl_prev_tp.configure(text="---")
                self.lbl_prev_sl.configure(text="---")
                self.lbl_prev_risk.configure(text="---")
                self.lbl_prev_rew.configure(text="---")

        for item in self.tree.get_children(): self.tree.delete(item)
        for p in positions:
            swap_val = getattr(p, 'swap', 0.0)
            swap_str = f"{swap_val:.2f}" if abs(swap_val) > 0.001 else "-"
            # Fix hiển thị Fee trong bảng
            comm_val = self.get_fee_config(p.symbol) * p.volume
            pnl = p.profit + swap_val + getattr(p, 'commission', 0.0)
            
            vals = (
                datetime.fromtimestamp(p.time).strftime("%H:%M"), 
                p.symbol, 
                "BUY" if p.type==0 else "SELL",
                p.volume, 
                f"{p.price_open:.2f}", 
                f"{p.sl:.2f}", 
                f"{p.tp:.2f}", 
                swap_str,              
                f"-${comm_val:.2f}",   
                f"{pnl:.2f}", 
                "❌"
            )
            self.tree.insert("", "end", iid=p.ticket, values=vals)

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            row = self.tree.identify_row(event.y)
            if not row: return
            ticket = int(row)
            if col == "#11": 
                self.handle_close_request(ticket)

    def handle_close_request(self, ticket):
        if self.var_confirm_close.get() and not messagebox.askyesno("Confirm", f"Close #{ticket}?"): return
        threading.Thread(target=lambda: self.connector.close_position(
            next((p for p in self.connector.get_all_open_positions() if p.ticket==ticket), None)
        )).start()
        self.log(f"Đang đóng lệnh #{ticket}...")

    def on_click_trade(self):
        d = self.var_direction.get()
        s, p = self.cbo_symbol.get(), self.cbo_preset.get()
        try: mlot, mtp, msl = float(self.var_manual_lot.get() or 0), float(self.var_manual_tp.get() or 0), float(self.var_manual_sl.get() or 0)
        except: mlot=0
        
        self.log(f"Gửi lệnh {d} {s}...",)
        def run():
            res = self.trade_mgr.execute_manual_trade(d, p, s, self.var_strict_mode.get(), mlot, mtp, msl, self.var_bypass_checklist.get())
            self.after(0, lambda: self.log(f"Kết quả: {res}", error=(res!="SUCCESS")))
        threading.Thread(target=run).start()

    def show_history_popup(self):
        top = ctk.CTkToplevel(self)
        top.title("Session History")
        top.geometry("600x400")
        
        cols = ("Time", "Symbol", "Type", "PnL")
        tr = ttk.Treeview(top, columns=cols, show="headings")
        tr.pack(fill="both", expand=True)
        for c in cols: tr.heading(c, text=c)
        for h in self.trade_mgr.state.get("daily_history", []):
            tr.insert("", "end", values=(h['time'], h['symbol'], h['type'], f"${h['profit']:.2f}"))

if __name__ == "__main__":
    try:
        app = BotUI()
        app.mainloop()
    except KeyboardInterrupt: sys.exit()