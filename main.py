# -*- coding: utf-8 -*-
# FILE: main.py
# V2.2.1: FIXED EXIT LOGIC, PRO FEE CALC & TSL PREVIEW ENHANCED

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
PRESETS_FILE = "data/presets_config.json"

# --- CẤU HÌNH GIAO DIỆN ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Fonts
FONT_MAIN = ("Roboto", 13)
FONT_BOLD = ("Roboto", 13, "bold")
FONT_EQUITY = ("Roboto", 36, "bold")
FONT_PNL = ("Roboto", 18, "bold")
FONT_SECTION = ("Roboto", 12, "bold")
FONT_BIG_VAL = ("Consolas", 20, "bold")
FONT_PRICE = ("Roboto", 32, "bold")
FONT_TREE = ("Roboto", 12) 
FONT_TREE_HEAD = ("Roboto", 12, "bold")
FONT_FEE = ("Roboto", 13, "bold") 

# Colors
COL_GREEN = "#00C853"
COL_RED = "#D50000"
COL_BLUE_ACCENT = "#1565C0"
COL_GRAY_BTN = "#424242"
COL_TEXT_WHITE = "#FFFFFF"
COL_TEXT_GRAY = "#AAAAAA"
COL_WARN = "#FFAB00"

class BotUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PRO SCALPING V2.2.1 - STABLE")
        self.geometry("1450x950")
        
        # --- Variables ---
        self.var_strict_mode = tk.BooleanVar(value=config.STRICT_MODE_DEFAULT)
        self.var_confirm_close = tk.BooleanVar(value=True)
        self.var_account_type = tk.StringVar(value=config.DEFAULT_ACCOUNT_TYPE)
        
        self.var_manual_lot = tk.StringVar(value="")
        self.var_manual_tp = tk.StringVar(value="")
        self.var_manual_sl = tk.StringVar(value="")
        self.var_bypass_checklist = tk.BooleanVar(value=config.MANUAL_CONFIG["BYPASS_CHECKLIST"])
        self.var_direction = tk.StringVar(value="BUY") 
        
        self.tactic_states = {"BE": True, "PNL": False, "STEP_R": True}
        
        self.running = True
        self.tsl_states_map = {} 
        self.last_price_val = 0.0
        self.load_settings()

        self.connector = ExnessConnector()
        self.connector.connect()
        
        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr, log_callback=self.log_message)

        # --- GRID LAYOUT ---
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)

        self.frm_left = ctk.CTkScrollableFrame(self, width=400, corner_radius=0, label_text="")
        self.frm_left.grid(row=0, column=0, sticky="nswe")
        self.frm_left.grid_columnconfigure(0, weight=1)
        self.setup_left_panel(self.frm_left)

        self.frm_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frm_right.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)
        self.setup_right_panel(self.frm_right)

        # Đăng ký sự kiện đóng cửa sổ
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log_message("System V2.2.1 Initialized.")

    def on_closing(self):
        """Hàm xử lý khi đóng ứng dụng để thoát sạch sẽ"""
        self.running = False
        self.log_message("Hệ thống đang dừng...")
        try:
            mt5.shutdown()
        except: pass
        self.destroy()
        sys.exit(0)

    def setup_left_panel(self, parent):
        # 1. HEADER
        f_top = ctk.CTkFrame(parent, fg_color="#1a1a1a", corner_radius=8)
        f_top.pack(fill="x", pady=(5, 10), padx=5)
        
        self.lbl_equity = ctk.CTkLabel(f_top, text="$----", font=FONT_EQUITY, text_color=COL_GREEN)
        self.lbl_equity.pack(pady=(15, 0))
        
        f_pnl = ctk.CTkFrame(f_top, fg_color="transparent")
        f_pnl.pack(pady=(0, 10))
        self.lbl_stats = ctk.CTkLabel(f_pnl, text="Today: $0.00", font=FONT_PNL, text_color="white")
        self.lbl_stats.pack(side="left", padx=5)
        ctk.CTkButton(f_pnl, text="⟳", width=30, height=20, fg_color="#333", hover_color="#444", 
                      command=self.reset_daily_stats).pack(side="left", padx=5)

        self.lbl_acc_info = ctk.CTkLabel(f_top, text="ID: --- | Server: ---", font=("Roboto", 10), text_color="gray")
        self.lbl_acc_info.pack(pady=(0, 5))

        # 2. SETTINGS BLOCK
        f_set = ctk.CTkFrame(parent, fg_color="transparent")
        f_set.pack(fill="x", padx=5, pady=5)
        f_set.columnconfigure(1, weight=1)

        ctk.CTkLabel(f_set, text="COIN:", font=FONT_SECTION, text_color="gray").grid(row=0, column=0, sticky="w")
        f_coin_row = ctk.CTkFrame(f_set, fg_color="transparent")
        f_coin_row.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.cbo_symbol = ctk.CTkOptionMenu(f_coin_row, values=config.COIN_LIST, font=FONT_BOLD, width=120, command=self.on_symbol_change)
        self.cbo_symbol.set(config.DEFAULT_SYMBOL)
        self.cbo_symbol.pack(side="left")
        
        self.chk_force = ctk.CTkCheckBox(f_coin_row, text="Force", variable=self.var_bypass_checklist, 
                                         font=("Roboto", 11, "bold"), text_color=COL_WARN,
                                         width=60, checkbox_width=18, checkbox_height=18)
        self.chk_force.pack(side="right", padx=5)

        ctk.CTkLabel(f_set, text="MODE:", font=FONT_SECTION, text_color="gray").grid(row=1, column=0, sticky="w", pady=5)
        f_mode_row = ctk.CTkFrame(f_set, fg_color="transparent")
        f_mode_row.grid(row=1, column=1, sticky="ew", padx=5)
        
        self.cbo_preset = ctk.CTkOptionMenu(f_mode_row, values=list(config.PRESETS.keys()), font=FONT_MAIN, width=100)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(f_mode_row, text="⚙", width=30, fg_color="#444", hover_color="#666", 
                      command=self.open_preset_config_popup).pack(side="left", padx=(2,0))

        self.cbo_account_type = ctk.CTkOptionMenu(f_mode_row, values=list(config.ACCOUNT_TYPES_CONFIG.keys()), font=FONT_MAIN, width=80)
        self.cbo_account_type.set(config.DEFAULT_ACCOUNT_TYPE)
        self.cbo_account_type.pack(side="right", fill="x", padx=(5,0))

        ctk.CTkLabel(f_set, text="TACTIC:", font=FONT_SECTION, text_color="gray").grid(row=2, column=0, sticky="w", pady=5)
        f_tsl_row = ctk.CTkFrame(f_set, fg_color="transparent")
        f_tsl_row.grid(row=2, column=1, sticky="ew", padx=5)

        self.btn_tactic_be = ctk.CTkButton(f_tsl_row, text="BE", width=50, command=lambda: self.toggle_tactic("BE"))
        self.btn_tactic_be.pack(side="left", padx=2)
        
        self.btn_tactic_pnl = ctk.CTkButton(f_tsl_row, text="PNL", width=50, command=lambda: self.toggle_tactic("PNL"))
        self.btn_tactic_pnl.pack(side="left", padx=2)
        
        self.btn_tactic_step = ctk.CTkButton(f_tsl_row, text="STEP", width=50, command=lambda: self.toggle_tactic("STEP_R"))
        self.btn_tactic_step.pack(side="left", padx=2)

        ctk.CTkButton(f_tsl_row, text="⚙ TSL", width=60, fg_color="#424242", hover_color="#616161",
                      command=self.open_tsl_popup).pack(side="right", padx=(5,0))
        
        self.update_tactic_buttons_ui()

        # 3. MANUAL INPUT
        f_input = ctk.CTkFrame(parent, fg_color="transparent")
        f_input.pack(fill="x", padx=5, pady=5)
        f_input.grid_columnconfigure((0,1,2), weight=1)

        def make_inp(p, t, v, c):
            f = ctk.CTkFrame(p, fg_color="#2b2b2b", corner_radius=6)
            f.grid(row=0, column=c, padx=3, sticky="ew")
            ctk.CTkLabel(f, text=t, font=("Roboto", 10, "bold"), text_color="#aaa").pack(pady=(2,0))
            ctk.CTkEntry(f, textvariable=v, font=("Consolas", 14, "bold"), height=30, justify="center", fg_color="transparent", border_width=0).pack(fill="x")

        make_inp(f_input, "VOL (Lot)", self.var_manual_lot, 0)
        make_inp(f_input, "TP (Price)", self.var_manual_tp, 1)
        make_inp(f_input, "SL (Price)", self.var_manual_sl, 2)

        # 4. DASHBOARD
        f_dashboard = ctk.CTkFrame(parent, fg_color="#252526", corner_radius=8, border_width=1, border_color="#333")
        f_dashboard.pack(fill="x", padx=5, pady=10)
        
        f_head_db = ctk.CTkFrame(f_dashboard, fg_color="transparent")
        f_head_db.pack(fill="x", padx=10, pady=(5,0))
        self.lbl_prev_lot = ctk.CTkLabel(f_head_db, text="LOT: 0.00", font=FONT_BOLD, text_color="#FFD700")
        self.lbl_prev_lot.pack(side="left")
        self.lbl_fee_info = ctk.CTkLabel(f_head_db, text="Fee: $0.00", font=FONT_FEE, text_color="#FFD700")
        self.lbl_fee_info.pack(side="right")
        
        self.lbl_dashboard_price = ctk.CTkLabel(f_dashboard, text="----.--", font=FONT_PRICE, text_color="white")
        self.lbl_dashboard_price.pack(pady=(5, 5))

        ctk.CTkFrame(f_dashboard, height=1, fg_color="#444").pack(fill="x", padx=5)
        f_grid_db = ctk.CTkFrame(f_dashboard, fg_color="transparent")
        f_grid_db.pack(fill="x", padx=5, pady=5)
        f_grid_db.columnconfigure((0,1), weight=1)

        f_rew = ctk.CTkFrame(f_grid_db, fg_color="transparent")
        f_rew.grid(row=0, column=0, sticky="nsew", padx=2)
        ctk.CTkLabel(f_rew, text="TARGET (TP)", font=("Roboto", 10), text_color=COL_GREEN).pack()
        self.lbl_prev_tp = ctk.CTkLabel(f_rew, text="---", font=("Consolas", 14), text_color=COL_GREEN)
        self.lbl_prev_tp.pack()
        self.lbl_prev_rew = ctk.CTkLabel(f_rew, text="+$0.0", font=FONT_BIG_VAL, text_color=COL_GREEN)
        self.lbl_prev_rew.pack()

        f_risk = ctk.CTkFrame(f_grid_db, fg_color="transparent")
        f_risk.grid(row=0, column=1, sticky="nsew", padx=2)
        ctk.CTkLabel(f_risk, text="STOPLOSS (SL)", font=("Roboto", 10), text_color=COL_RED).pack()
        self.lbl_prev_sl = ctk.CTkLabel(f_risk, text="---", font=("Consolas", 14), text_color=COL_RED)
        self.lbl_prev_sl.pack()
        self.lbl_prev_risk = ctk.CTkLabel(f_risk, text="-$0.0", font=FONT_BIG_VAL, text_color=COL_RED)
        self.lbl_prev_risk.pack()

        ctk.CTkFrame(f_dashboard, height=1, fg_color="#444").pack(fill="x", padx=10, pady=(5,0))
        self.lbl_tsl_preview = ctk.CTkLabel(f_dashboard, text="TSL: OFF", font=("Roboto", 13), text_color="#2196F3")
        self.lbl_tsl_preview.pack(pady=(5,5))

        # 5. EXECUTION
        self.seg_direction = ctk.CTkSegmentedButton(parent, values=["BUY", "SELL"], font=("Roboto", 14, "bold"), 
                                                    command=self.on_direction_change, height=32,
                                                    selected_color=COL_GREEN, selected_hover_color="#009624")
        self.seg_direction.set("BUY")
        self.seg_direction.pack(fill="x", padx=10, pady=(10, 5))

        self.btn_action = ctk.CTkButton(parent, text="EXECUTE BUY", font=("Roboto", 16, "bold"), height=45, 
                                        fg_color=COL_GREEN, hover_color="#009624", command=self.on_click_trade)
        self.btn_action.pack(fill="x", padx=10, pady=(0, 10))

        # 6. CHECKS
        f_sys = ctk.CTkFrame(parent, fg_color="#1a1a1a")
        f_sys.pack(fill="x", padx=5, pady=(10, 20))
        ctk.CTkLabel(f_sys, text=" SYSTEM HEALTH", font=("Roboto", 11, "bold"), text_color="gray").pack(anchor="w", padx=5, pady=(5,0))
        
        self.check_labels = {}
        checks = ["Mạng/Spread", "Daily Loss", "Số Lệnh Thua", "Số Lệnh", "Trạng thái"]
        for name in checks:
            l = ctk.CTkLabel(f_sys, text=f"• {name}", font=("Roboto", 12), text_color="gray", anchor="w")
            l.pack(fill="x", padx=10)
            self.check_labels[name] = l

    def setup_right_panel(self, parent):
        f_head = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        f_head.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(f_head, text="RUNNING TRADES", font=("Roboto", 16, "bold")).pack(side="left")
        ctk.CTkButton(f_head, text="History", width=80, height=24, command=self.show_history_popup, fg_color="#444").pack(side="right")

        f_tree_container = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        f_tree_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=35, font=FONT_TREE)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", font=FONT_TREE_HEAD, relief="flat")
        style.map("Treeview", background=[('selected', '#3949ab')])

        cols = ("Time", "Symbol", "Type", "Vol", "Entry", "SL", "TP", "PnL", "Status", "X")
        self.tree = ttk.Treeview(f_tree_container, columns=cols, show="headings", style="Treeview")
        
        headers = ["Time", "Coin", "Type", "Vol", "Entry", "SL", "TP", "PnL", "Status", "✖"]
        widths = [70, 60, 40, 50, 80, 70, 70, 70, 200, 30] 
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="center")

        sb = ttk.Scrollbar(f_tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", padx=2, pady=2)

        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.on_tree_right_click)

        f_log = ctk.CTkFrame(parent, height=380, fg_color="#1e1e1e")
        f_log.pack(fill="x", pady=(10, 0))
        f_log.pack_propagate(False)

        f_log_head = ctk.CTkFrame(f_log, fg_color="transparent", height=25)
        f_log_head.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f_log_head, text="SYSTEM LOG", font=("Roboto", 12, "bold"), text_color="#aaa").pack(side="left")
        ctk.CTkCheckBox(f_log_head, text="Safe Close", variable=self.var_confirm_close, font=("Roboto", 11), checkbox_width=16, checkbox_height=16).pack(side="right")

        self.txt_log = tk.Text(f_log, font=("Consolas", 12), bg="#121212", fg="#e0e0e0", 
                               bd=0, highlightthickness=0, state="disabled", wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=(0,5))
        
        self.txt_log.tag_config("INFO", foreground="#b0bec5")
        self.txt_log.tag_config("SUCCESS", foreground=COL_GREEN) 
        self.txt_log.tag_config("ERROR", foreground=COL_RED)   
        self.txt_log.tag_config("WARN", foreground=COL_WARN)    
        self.txt_log.tag_config("BLUE", foreground="#29B6F6")

    def toggle_tactic(self, mode):
        self.tactic_states[mode] = not self.tactic_states[mode]
        self.update_tactic_buttons_ui()
        
    def update_tactic_buttons_ui(self):
        def set_btn(btn, is_active):
            btn.configure(fg_color=COL_BLUE_ACCENT if is_active else COL_GRAY_BTN)
        set_btn(self.btn_tactic_be, self.tactic_states["BE"])
        set_btn(self.btn_tactic_pnl, self.tactic_states["PNL"])
        set_btn(self.btn_tactic_step, self.tactic_states["STEP_R"])

    def get_current_tactic_string(self):
        active = [k for k, v in self.tactic_states.items() if v]
        return "+".join(active) if active else "OFF"

    def log_message(self, msg, error=False):
        ts = time.strftime("%H:%M:%S")
        txt = f"[{ts}] {msg}\n"
        tag = "INFO"
        if error or "ERR" in msg or "FAIL" in msg or "PnL: -" in msg: tag = "ERROR"
        elif "SUCCESS" in msg or "Húp" in msg: tag = "SUCCESS"
        elif "WARN" in msg or "[FORCE]" in msg: tag = "WARN"
        elif "Exec" in msg or "[TSL]" in msg: tag = "BLUE"
        def _write():
            try:
                self.txt_log.configure(state="normal")
                self.txt_log.insert("end", txt, tag)
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
            except: pass
        self.after(0, _write)

    def get_fee_config(self, symbol):
        """Hàm tính Fee đã sửa lỗi tài khoản PRO/STANDARD"""
        acc_type = self.cbo_account_type.get()
        # Ưu tiên loại tài khoản: PRO/STANDARD không phí
        if acc_type in ["PRO", "STANDARD"]:
            return 0.0
        
        # Nếu là RAW/ZERO mới xét phí cụ thể theo coin hoặc phí mặc định
        specific_rate = config.COMMISSION_RATES.get(symbol, 0.0)
        if specific_rate > 0: 
            return specific_rate
            
        acc_cfg = config.ACCOUNT_TYPES_CONFIG.get(acc_type, config.ACCOUNT_TYPES_CONFIG["STANDARD"])
        return acc_cfg.get("COMMISSION_PER_LOT", 0.0)

    def on_symbol_change(self, new_symbol):
        self.lbl_dashboard_price.configure(text="Loading...", text_color="gray")
        threading.Thread(target=lambda: mt5.symbol_select(new_symbol, True)).start()

    def on_direction_change(self, value):
        self.var_direction.set(value)
        sym = self.cbo_symbol.get()
        if value == "BUY":
            self.btn_action.configure(text=f"BUY {sym}", fg_color=COL_GREEN, hover_color="#009624")
        else:
            self.btn_action.configure(text=f"SELL {sym}", fg_color=COL_RED, hover_color="#B71C1C")

    def load_settings(self):
        if os.path.exists(TSL_SETTINGS_FILE):
            try:
                with open(TSL_SETTINGS_FILE, "r") as f: config.TSL_CONFIG.update(json.load(f))
            except: pass
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r") as f: config.PRESETS.update(json.load(f))
            except: pass

    def save_settings(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(TSL_SETTINGS_FILE, "w") as f: json.dump(config.TSL_CONFIG, f, indent=4)
            with open(PRESETS_FILE, "w") as f: json.dump(config.PRESETS, f, indent=4)
        except: pass

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            row = self.tree.identify_row(event.y)
            if row and col == "#10": self.handle_close_request(int(row))

    def on_tree_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            ticket = int(row_id)
            menu = Menu(self, tearoff=0)
            menu.add_command(label=f"📝 Edit #{ticket}", command=lambda: self.open_edit_popup(ticket))
            menu.add_separator()
            menu.add_command(label="❌ Close Now", command=lambda: self.handle_close_request(ticket))
            menu.post(event.x_root, event.y_root)

    def open_edit_popup(self, ticket):
        positions = self.connector.get_all_open_positions()
        pos = next((p for p in positions if p.ticket == ticket), None)
        if not pos: return
        
        top = ctk.CTkToplevel(self)
        top.title(f"Edit #{ticket}")
        top.geometry("320x350")
        top.attributes("-topmost", True)
        
        ctk.CTkLabel(top, text="NEW SL:", font=FONT_BOLD).pack(pady=(10, 2))
        ent_sl = ctk.CTkEntry(top, justify="center"); ent_sl.insert(0, str(pos.sl)); ent_sl.pack()
        ctk.CTkLabel(top, text="NEW TP:", font=FONT_BOLD).pack(pady=(5, 2))
        ent_tp = ctk.CTkEntry(top, justify="center"); ent_tp.insert(0, str(pos.tp)); ent_tp.pack()
        
        ctk.CTkLabel(top, text="TACTIC OVERRIDE:", font=FONT_BOLD, text_color="#2196F3").pack(pady=(15, 5))
        f_btns = ctk.CTkFrame(top, fg_color="transparent")
        f_btns.pack()
        
        cur_tstr = self.trade_mgr.get_trade_tactic(ticket)
        p_states = {"BE": "BE" in cur_tstr, "PNL": "PNL" in cur_tstr, "STEP_R": "STEP_R" in cur_tstr}
        
        def update_pbtns():
            b_be.configure(fg_color=COL_BLUE_ACCENT if p_states["BE"] else COL_GRAY_BTN)
            b_pnl.configure(fg_color=COL_BLUE_ACCENT if p_states["PNL"] else COL_GRAY_BTN)
            b_step.configure(fg_color=COL_BLUE_ACCENT if p_states["STEP_R"] else COL_GRAY_BTN)

        def tog(k):
            p_states[k] = not p_states[k]
            update_pbtns()

        b_be = ctk.CTkButton(f_btns, text="BE", width=50, command=lambda: tog("BE"))
        b_be.pack(side="left", padx=2)
        b_pnl = ctk.CTkButton(f_btns, text="PNL", width=50, command=lambda: tog("PNL"))
        b_pnl.pack(side="left", padx=2)
        b_step = ctk.CTkButton(f_btns, text="STEP", width=50, command=lambda: tog("STEP_R"))
        b_step.pack(side="left", padx=2)
        update_pbtns()

        def save():
            try:
                self.connector.modify_position(ticket, float(ent_sl.get()), float(ent_tp.get()))
                act = [k for k,v in p_states.items() if v]
                new_t = "+".join(act) if act else "OFF"
                self.trade_mgr.update_trade_tactic(ticket, new_t)
                top.destroy()
                self.log_message(f"Updated #{ticket} [{new_t}]")
            except: pass
        ctk.CTkButton(top, text="UPDATE NOW", height=40, fg_color="#2e7d32", command=save).pack(pady=20, fill="x", padx=30)

    def open_preset_config_popup(self):
        p_name = self.cbo_preset.get()
        data = config.PRESETS.get(p_name, {})
        top = ctk.CTkToplevel(self)
        top.title(f"Config: {p_name}")
        top.geometry("300x250")
        top.attributes("-topmost", True)
        ctk.CTkLabel(top, text=f"PRESET: {p_name}", font=FONT_BOLD).pack(pady=10)
        ctk.CTkLabel(top, text="SL (%)").pack()
        e_sl = ctk.CTkEntry(top, justify="center"); e_sl.insert(0, str(data.get("SL_PERCENT", 0.5))); e_sl.pack()
        ctk.CTkLabel(top, text="TP (R)").pack()
        e_tp = ctk.CTkEntry(top, justify="center"); e_tp.insert(0, str(data.get("TP_RR_RATIO", 2.0))); e_tp.pack()
        def save():
            config.PRESETS[p_name]["SL_PERCENT"] = float(e_sl.get())
            config.PRESETS[p_name]["TP_RR_RATIO"] = float(e_tp.get())
            self.save_settings(); top.destroy()
        ctk.CTkButton(top, text="SAVE", command=save, fg_color=COL_GREEN).pack(pady=20, fill="x", padx=30)

    def open_tsl_popup(self):
        top = ctk.CTkToplevel(self)
        top.title("TSL Config V2.2")
        top.geometry("420x650") 
        top.attributes("-topmost", True)

        def sec(t):
            ctk.CTkLabel(top, text=t, font=("Roboto", 12, "bold"), text_color="#03A9F4").pack(fill="x", padx=20, pady=(15, 5), anchor="w")
            return ctk.CTkFrame(top, fg_color="transparent")

        f2 = sec("1. BREAK-EVEN (BE)")
        f2.pack(fill="x", padx=20)
        cbo_be = ctk.CTkOptionMenu(f2, values=["SOFT", "SMART"])
        cbo_be.set(config.TSL_CONFIG.get("BE_MODE", "SOFT")); cbo_be.pack(fill="x")
        f_be_off = ctk.CTkFrame(f2, fg_color="transparent"); f_be_off.pack(fill="x", pady=(5,0))
        ctk.CTkLabel(f_be_off, text="Offset (Points):").pack(side="left")
        e_be_pts = ctk.CTkEntry(f_be_off, width=60); e_be_pts.insert(0, str(config.TSL_CONFIG.get("BE_OFFSET_POINTS", 0))); e_be_pts.pack(side="right")

        f3 = sec("2. PNL LOCK (Levels)")
        f3.pack(fill="both", expand=True, padx=20)
        f_pnl_scroll = ctk.CTkScrollableFrame(f3, height=150); f_pnl_scroll.pack(fill="both", expand=True)
        pnl_entries = []
        def add_pnl_row(v1=0.0, v2=0.0):
            r = ctk.CTkFrame(f_pnl_scroll, fg_color="transparent"); r.pack(fill="x", pady=2)
            e1 = ctk.CTkEntry(r, width=70); e1.insert(0, str(v1)); e1.pack(side="left")
            ctk.CTkLabel(r, text="% Profit -> Lock %", text_color="gray").pack(side="left", padx=10)
            e2 = ctk.CTkEntry(r, width=70); e2.insert(0, str(v2)); e2.pack(side="right")
            pnl_entries.append((r, e1, e2))
        for lvl in config.TSL_CONFIG.get("PNL_LEVELS", []): add_pnl_row(lvl[0], lvl[1])
        f_pbtns = ctk.CTkFrame(f3, fg_color="transparent"); f_pbtns.pack(fill="x", pady=5)
        ctk.CTkButton(f_pbtns, text="+ Add", width=60, command=lambda: add_pnl_row(0.0, 0.0)).pack(side="left", padx=5)
        ctk.CTkButton(f_pbtns, text="- Del", width=60, command=lambda: pnl_entries.pop()[0].destroy() if pnl_entries else None).pack(side="right", padx=5)

        f4 = sec("3. STEP R (Nuôi Lệnh)")
        f4.pack(fill="x", padx=20)
        r_s1 = ctk.CTkFrame(f4, fg_color="transparent"); r_s1.pack(fill="x", pady=2)
        ctk.CTkLabel(r_s1, text="Step Size (R):").pack(side="left")
        e_step_size = ctk.CTkEntry(r_s1, width=80); e_step_size.insert(0, str(config.TSL_CONFIG.get("STEP_R_SIZE", 1.0))); e_step_size.pack(side="right")
        r_s2 = ctk.CTkFrame(f4, fg_color="transparent"); r_s2.pack(fill="x", pady=2)
        ctk.CTkLabel(r_s2, text="Lock Ratio (0-1):").pack(side="left")
        e_step_ratio = ctk.CTkEntry(r_s2, width=80); e_step_ratio.insert(0, str(config.TSL_CONFIG.get("STEP_R_RATIO", 0.8))); e_step_ratio.pack(side="right")

        def save_cfg():
            config.TSL_CONFIG["BE_MODE"] = cbo_be.get()
            config.TSL_CONFIG["BE_OFFSET_POINTS"] = float(e_be_pts.get() or 0)
            config.TSL_CONFIG["PNL_LEVELS"] = sorted([[float(e1.get()), float(e2.get())] for r,e1,e2 in pnl_entries if e1.get()], key=lambda x:x[0])
            config.TSL_CONFIG["STEP_R_SIZE"] = float(e_step_size.get() or 1.0)
            config.TSL_CONFIG["STEP_R_RATIO"] = float(e_step_ratio.get() or 0.8)
            self.save_settings(); top.destroy()
        ctk.CTkButton(top, text="SAVE CONFIG", height=40, font=("Roboto", 13, "bold"), command=save_cfg).pack(pady=20, fill="x", padx=40)

    def reset_daily_stats(self):
        if messagebox.askyesno("Confirm", "Reset Daily Stats?"):
            self.trade_mgr.state.update({"pnl_today": 0.0, "trades_today_count": 0, "daily_loss_count": 0, "daily_history": []})
            save_state(self.trade_mgr.state)

    def bg_update_loop(self):
        while self.running:
            try:
                sym = self.cbo_symbol.get()
                new_map = self.trade_mgr.update_running_trades(self.cbo_account_type.get())
                self.tsl_states_map.update(new_map)
                acc = self.connector.get_account_info()
                tick = mt5.symbol_info_tick(sym)
                pos = [p for p in self.connector.get_all_open_positions() if p.magic == config.MAGIC_NUMBER]
                self.after(0, self.update_ui, acc, self.trade_mgr.state, 
                                self.checklist_mgr.run_pre_trade_checks(acc, self.trade_mgr.state, sym, self.var_strict_mode.get()), 
                                tick, self.cbo_preset.get(), sym, pos)
            except: pass
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui(self, acc, state, check_res, tick, preset, sym, positions):
        d = self.seg_direction.get()
        self.var_direction.set(d)
        cur_tactic_str = self.get_current_tactic_string()

        if acc: 
            self.lbl_equity.configure(text=f"${acc['equity']:,.2f}")
            self.lbl_acc_info.configure(text=f"ID: {acc['login']} | Server: {acc['server']}")
        pnl = state['pnl_today']
        self.lbl_stats.configure(text=f"Today: ${pnl:.2f}", text_color=COL_GREEN if pnl >= 0 else COL_RED)
        
        cur_price, c_size, point = 0.0, 1.0, 0.00001
        if tick: 
            cur_price = tick.ask if d == "BUY" else tick.bid
            self.lbl_dashboard_price.configure(text=f"{cur_price:.2f}", text_color=COL_GREEN if cur_price >= self.last_price_val else COL_RED)
            self.last_price_val = cur_price
            s_info = mt5.symbol_info(sym)
            if s_info: c_size, point = s_info.trade_contract_size, s_info.point

        for item in check_res["checks"]:
            name, stt, msg = item["name"], item["status"], item["msg"]
            if name in self.check_labels:
                self.check_labels[name].configure(text=f"{'✔' if stt=='OK' else '✖'} {name}: {msg}", 
                                                   text_color=COL_GREEN if stt=="OK" else (COL_WARN if stt=="WARN" else COL_RED))

        if tick and acc:
            params = config.PRESETS.get(preset, config.PRESETS["SCALPING"])
            try: mlot = float(self.var_manual_lot.get() or 0)
            except: mlot = 0.0
            
            f_lot = mlot if mlot > 0 else 0
            if f_lot == 0:
                risk_usd = acc['equity'] * (config.RISK_PER_TRADE_PERCENT/100)
                sl_dist = cur_price * (params["SL_PERCENT"]/100)
                if sl_dist > 0: f_lot = max(config.MIN_LOT_SIZE, min(round((risk_usd / (sl_dist * c_size)) / config.LOT_STEP) * config.LOT_STEP, config.MAX_LOT_SIZE))

            self.lbl_prev_lot.configure(text=f"{'(MANUAL)' if mlot>0 else '(AUTO)'} LOT: {f_lot:.2f}", text_color="white" if mlot==0 else "#FFD700")
            
            # --- FIX FEE CALCULATION ---
            comm_rate = self.get_fee_config(sym)
            comm_total = comm_rate * f_lot
            spread_cost = (tick.ask - tick.bid) * f_lot * c_size
            self.lbl_fee_info.configure(text=f"Fee: -${(comm_total + spread_cost):.2f} (Com:{comm_total:.1f}|Spr:{spread_cost:.1f})")

            try: msl, mtp = float(self.var_manual_sl.get() or 0), float(self.var_manual_tp.get() or 0)
            except: msl, mtp = 0, 0
            
            auto_sl_dist = cur_price * (params["SL_PERCENT"]/100)
            p_sl = msl if msl > 0 else (cur_price - auto_sl_dist if d=="BUY" else cur_price + auto_sl_dist)
            p_tp = mtp if mtp > 0 else (cur_price + abs(cur_price - p_sl) * params["TP_RR_RATIO"] if d=="BUY" else cur_price - abs(cur_price - p_sl) * params["TP_RR_RATIO"])
            
            self.lbl_prev_sl.configure(text=f"{p_sl:.2f}"); self.lbl_prev_risk.configure(text=f"-${(abs(cur_price-p_sl)*f_lot*c_size):.2f}")
            self.lbl_prev_tp.configure(text=f"{p_tp:.2f}"); self.lbl_prev_rew.configure(text=f"+${(abs(p_tp-cur_price)*f_lot*c_size):.2f}")

            # --- V2.2.1 TSL PREVIEW ENHANCED ---
            tsl_previews = []
            one_r = abs(cur_price - p_sl)
            t_cfg = config.TSL_CONFIG
            is_buy = (d == "BUY")

            # 1. BE Logic Preview
            if "BE" in cur_tactic_str:
                mode = t_cfg.get("BE_MODE", "SOFT")
                be_pts = t_cfg.get("BE_OFFSET_POINTS", 0)
                trig_be = cur_price + (one_r * t_cfg.get("BE_OFFSET_RR", 0.8)) if is_buy else cur_price - (one_r * t_cfg.get("BE_OFFSET_RR", 0.8))
                fee_d = (comm_total + spread_cost) / (f_lot * c_size) if (f_lot * c_size) > 0 else 0
                base_be = cur_price - fee_d if (is_buy and mode=="SOFT") else (cur_price + fee_d if (is_buy and mode=="SMART") else cur_price)
                if not is_buy: base_be = cur_price + fee_d if mode=="SOFT" else (cur_price - fee_d if mode=="SMART" else cur_price)
                sl_be = base_be + (be_pts * point) if is_buy else base_be - (be_pts * point)
                tsl_previews.append({"name": f"BE ({mode})", "trig": trig_be, "sl": sl_be, "prio": 1})

            # 2. STEP Logic Preview
            if "STEP_R" in cur_tactic_str:
                sz, rt = t_cfg.get("STEP_R_SIZE", 1.0), t_cfg.get("STEP_R_RATIO", 0.8)
                trig_s1 = cur_price + (sz * one_r) if is_buy else cur_price - (sz * one_r)
                sl_s1 = cur_price + (sz * one_r * rt) if is_buy else cur_price - (sz * one_r * rt)
                tsl_previews.append({"name": f"STEP 1", "trig": trig_s1, "sl": sl_s1, "prio": 3})

            # 3. PNL Logic Preview
            if "PNL" in cur_tactic_str and t_cfg.get("PNL_LEVELS"):
                lvl = t_cfg["PNL_LEVELS"][0]
                target_money = acc['balance'] * (lvl[0]/100.0)
                req_d = target_money / (f_lot * c_size) if (f_lot * c_size) > 0 else 0
                trig_p = cur_price + req_d if is_buy else cur_price - req_d
                lock_p = cur_price + (req_d * (lvl[1]/lvl[0])) if is_buy and lvl[0]>0 else cur_price
                tsl_previews.append({"name": f"PNL {lvl[0]}%", "trig": trig_p, "sl": lock_p, "prio": 2})

            if not tsl_previews:
                self.lbl_tsl_preview.configure(text="TSL: OFF")
            else:
                # Chọn cái ưu tiên hiển thị cao nhất (STEP > PNL > BE)
                best = sorted(tsl_previews, key=lambda x: x['prio'], reverse=True)[0]
                self.lbl_tsl_preview.configure(text=f"Mục tiêu: [{best['name']}] {best['trig']:.2f} ➔ SL: {best['sl']:.2f}")

        # Update Table
        for item in self.tree.get_children(): self.tree.delete(item)
        for p in positions:
            pnl_val = p.profit + getattr(p, 'swap', 0) + getattr(p, 'commission', 0)
            stt_txt = self.tsl_states_map.get(p.ticket, "Running")
            self.tree.insert("", "end", iid=p.ticket, values=(
                datetime.fromtimestamp(p.time).strftime("%d/%m %H:%M"), p.symbol, "BUY" if p.type==0 else "SELL", p.volume, 
                f"{p.price_open:.2f}", f"{p.sl:.2f}", f"{p.tp:.2f}", f"{pnl_val:.2f}", stt_txt, "❌"
            ))

    def handle_close_request(self, ticket):
        if self.var_confirm_close.get() and not messagebox.askyesno("Confirm", f"Close #{ticket}?"): return
        threading.Thread(target=lambda: self.connector.close_position(next((p for p in self.connector.get_all_open_positions() if p.ticket==ticket), None))).start()

    def on_click_trade(self):
        d, s, p, t = self.seg_direction.get(), self.cbo_symbol.get(), self.cbo_preset.get(), self.get_current_tactic_string()
        try: ml, mt, ms = float(self.var_manual_lot.get() or 0), float(self.var_manual_tp.get() or 0), float(self.var_manual_sl.get() or 0)
        except: ml=0
        self.log_message(f"Exec {d} {s} | TSL: [{t}]...")
        threading.Thread(target=lambda: self.trade_mgr.execute_manual_trade(d, p, s, self.var_strict_mode.get(), ml, mt, ms, self.var_bypass_checklist.get(), t)).start()

    def show_history_popup(self):
        top = ctk.CTkToplevel(self); top.title("History"); top.geometry("700x450")
        tr = ttk.Treeview(top, columns=("Time", "Sym", "Type", "PnL", "Reason"), show="headings"); tr.pack(fill="both", expand=True)
        for c in tr["columns"]: tr.heading(c, text=c)
        for h in self.trade_mgr.state.get("daily_history", []): tr.insert("", "end", values=(h['time'], h['symbol'], h['type'], f"${h['profit']:.2f}", h.get('reason','')))

if __name__ == "__main__":
    try:
        app = BotUI()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Đang đóng ứng dụng từ Terminal...")
        sys.exit(0)