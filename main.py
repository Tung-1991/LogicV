# -*- coding: utf-8 -*-
# FILE: main.py
# V3.2.5: FIX SCROLLBAR & SMART UI UPDATE

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
FONT_TREE = ("Consolas", 11) 
FONT_TREE_HEAD = ("Roboto", 11, "bold")
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
        
        self.title("PRO SCALPING V3.2.5 - FIXED UI")
        # TĂNG SIZE CỬA SỔ ĐỂ ĐỦ CHỖ HIỂN THỊ
        self.geometry("1600x950")
        
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

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log_message("System V3.2.5 Layout Fix Initialized.")

    def on_closing(self):
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
        # HEADER
        f_head = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        f_head.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(f_head, text="RUNNING TRADES (Realtime)", font=("Roboto", 16, "bold")).pack(side="left")
        ctk.CTkButton(f_head, text="History", width=80, height=24, command=self.show_history_popup, fg_color="#444").pack(side="right")

        f_tree_container = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        f_tree_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        # Rowheight 35, Font Consolas
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", 
                        rowheight=35, font=("Consolas", 11)) 
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="#e0e0e0", font=("Roboto", 10, "bold"), relief="flat")
        style.map("Treeview", background=[('selected', '#3949ab')])

        # --- SETUP CỘT CHO BẢNG ---
        cols = ("Time", "Order", "Targets", "Fee", "RR", "PnL", "Status", "X")
        self.tree = ttk.Treeview(f_tree_container, columns=cols, show="headings", style="Treeview")
        
        headers = ["Time", "Order Info (@Entry)", "Targets (SL | TP)", "Fee | Swap", "Risk | Reward (%)", "PnL", "Status", "✖"]
        
        # --- FIXED LAYOUT: Đã thêm stretch=False và tăng Width ---
        # Tổng width ~ 1300px, đủ để thanh scrollbar hiện ra nếu màn hình bé
        widths = [110, 280, 180, 200, 250, 120, 150, 40]
        anchors= ["center", "w", "center", "center", "center", "center", "w", "center"]

        for c, h, w, a in zip(cols, headers, widths, anchors):
            self.tree.heading(c, text=h)
            # QUAN TRỌNG: stretch=False giúp cột không bị tự co lại, cho phép kéo giãn & cuộn ngang
            self.tree.column(c, width=w, anchor=a, minwidth=w, stretch=False)

        sb = ttk.Scrollbar(f_tree_container, orient="vertical", command=self.tree.yview)
        # SCROLLBAR NGANG
        sb_x = ttk.Scrollbar(f_tree_container, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscroll=sb.set, xscroll=sb_x.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        
        f_tree_container.grid_rowconfigure(0, weight=1)
        f_tree_container.grid_columnconfigure(0, weight=1)

        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.on_tree_right_click)

        # LOGGING SECTION
        f_log = ctk.CTkFrame(parent, height=350, fg_color="#1e1e1e")
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
        acc_type = self.cbo_account_type.get()
        if acc_type in ["PRO", "STANDARD"]:
            return 0.0
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
            row_id = self.tree.identify_row(event.y)
            # Cột X là cột số 8 (#8)
            # row_id bây giờ là ticket dạng string
            if row_id and col == "#8": self.handle_close_request(int(row_id))

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
        top.geometry("300x320")
        top.attributes("-topmost", True)
        
        ctk.CTkLabel(top, text=f"PRESET: {p_name}", font=FONT_BOLD).pack(pady=10)
        
        ctk.CTkLabel(top, text="Risk per Trade (%)").pack()
        e_risk = ctk.CTkEntry(top, justify="center")
        current_risk = data.get("RISK_PERCENT", config.RISK_PER_TRADE_PERCENT)
        e_risk.insert(0, str(current_risk))
        e_risk.pack()

        ctk.CTkLabel(top, text="SL (%)").pack()
        e_sl = ctk.CTkEntry(top, justify="center")
        e_sl.insert(0, str(data.get("SL_PERCENT", 0.5)))
        e_sl.pack()
        
        ctk.CTkLabel(top, text="TP (R)").pack()
        e_tp = ctk.CTkEntry(top, justify="center")
        e_tp.insert(0, str(data.get("TP_RR_RATIO", 2.0)))
        e_tp.pack()
        
        def save():
            try:
                config.PRESETS[p_name]["RISK_PERCENT"] = float(e_risk.get())
                config.PRESETS[p_name]["SL_PERCENT"] = float(e_sl.get())
                config.PRESETS[p_name]["TP_RR_RATIO"] = float(e_tp.get())
                self.save_settings()
                top.destroy()
                self.log_message(f"Updated Preset {p_name}: Risk {e_risk.get()}%")
            except Exception as e:
                messagebox.showerror("Error", f"Invalid input: {e}")

        ctk.CTkButton(top, text="SAVE", command=save, fg_color=COL_GREEN).pack(pady=20, fill="x", padx=30)

    def open_tsl_popup(self):
        top = ctk.CTkToplevel(self)
        top.title("TSL Config V3.2")
        top.geometry("400x520") 
        top.attributes("-topmost", True)

        def sec(t):
            ctk.CTkLabel(top, text=t, font=("Roboto", 12, "bold"), text_color="#03A9F4").pack(fill="x", padx=15, pady=(10, 2), anchor="w")
            return ctk.CTkFrame(top, fg_color="transparent")

        # --- 1. BREAK-EVEN (BE) ---
        f2 = sec("1. BREAK-EVEN (BE)")
        f2.pack(fill="x", padx=15)
        
        r1 = ctk.CTkFrame(f2, fg_color="transparent"); r1.pack(fill="x", pady=2)
        ctk.CTkLabel(r1, text="Mode:").pack(side="left")
        cbo_be = ctk.CTkOptionMenu(r1, values=["SOFT", "SMART"], width=100)
        cbo_be.set(config.TSL_CONFIG.get("BE_MODE", "SOFT")); cbo_be.pack(side="right")
        
        r2 = ctk.CTkFrame(f2, fg_color="transparent"); r2.pack(fill="x", pady=2)
        ctk.CTkLabel(r2, text="Trigger(R):").pack(side="left")
        e_be_rr = ctk.CTkEntry(r2, width=50)
        e_be_rr.insert(0, str(config.TSL_CONFIG.get("BE_OFFSET_RR", 0.8))); e_be_rr.pack(side="left", padx=(5,10))
        
        e_be_pts = ctk.CTkEntry(r2, width=50); 
        e_be_pts.insert(0, str(config.TSL_CONFIG.get("BE_OFFSET_POINTS", 0))); e_be_pts.pack(side="right")
        ctk.CTkLabel(r2, text="Offset(Pts):").pack(side="right", padx=5)

        # --- 2. PNL LOCK --- 
        f3 = sec("2. PNL LOCK (Levels)")
        f3.pack(fill="both", expand=True, padx=15)
        
        f_pnl_scroll = ctk.CTkScrollableFrame(f3, height=100); f_pnl_scroll.pack(fill="both", expand=True)
        pnl_entries = []
        def add_pnl_row(v1=0.0, v2=0.0):
            r = ctk.CTkFrame(f_pnl_scroll, fg_color="transparent"); r.pack(fill="x", pady=2)
            e1 = ctk.CTkEntry(r, width=60); e1.insert(0, str(v1)); e1.pack(side="left")
            ctk.CTkLabel(r, text="% Win -> Lock %", text_color="gray", font=("Roboto",11)).pack(side="left", padx=5)
            e2 = ctk.CTkEntry(r, width=60); e2.insert(0, str(v2)); e2.pack(side="right")
            pnl_entries.append((r, e1, e2))
        for lvl in config.TSL_CONFIG.get("PNL_LEVELS", []): add_pnl_row(lvl[0], lvl[1])
        
        f_pbtns = ctk.CTkFrame(f3, fg_color="transparent"); f_pbtns.pack(fill="x", pady=2)
        ctk.CTkButton(f_pbtns, text="+", width=40, command=lambda: add_pnl_row(0.0, 0.0)).pack(side="left", padx=5)
        ctk.CTkButton(f_pbtns, text="-", width=40, command=lambda: pnl_entries.pop()[0].destroy() if pnl_entries else None).pack(side="right", padx=5)

        # --- 3. STEP R --- 
        f4 = sec("3. STEP R (Nuôi Lệnh)")
        f4.pack(fill="x", padx=15)
        r_step = ctk.CTkFrame(f4, fg_color="transparent"); r_step.pack(fill="x", pady=2)
        
        ctk.CTkLabel(r_step, text="Size(R):").pack(side="left")
        e_step_size = ctk.CTkEntry(r_step, width=50); e_step_size.insert(0, str(config.TSL_CONFIG.get("STEP_R_SIZE", 1.0))); e_step_size.pack(side="left", padx=(5,10))
        
        e_step_ratio = ctk.CTkEntry(r_step, width=50); e_step_ratio.insert(0, str(config.TSL_CONFIG.get("STEP_R_RATIO", 0.8))); e_step_ratio.pack(side="right")
        ctk.CTkLabel(r_step, text="Lock(0-1):").pack(side="right", padx=5)

        def save_cfg():
            config.TSL_CONFIG["BE_MODE"] = cbo_be.get()
            config.TSL_CONFIG["BE_OFFSET_RR"] = float(e_be_rr.get() or 0.8) 
            config.TSL_CONFIG["BE_OFFSET_POINTS"] = float(e_be_pts.get() or 0)
            config.TSL_CONFIG["PNL_LEVELS"] = sorted([[float(e1.get()), float(e2.get())] for r,e1,e2 in pnl_entries if e1.get()], key=lambda x:x[0])
            config.TSL_CONFIG["STEP_R_SIZE"] = float(e_step_size.get() or 1.0)
            config.TSL_CONFIG["STEP_R_RATIO"] = float(e_step_ratio.get() or 0.8)
            self.save_settings()
            top.destroy()
            self.log_message("Đã cập nhật cấu hình TSL.")

        ctk.CTkButton(top, text="SAVE CONFIG", height=35, font=("Roboto", 13, "bold"), command=save_cfg, fg_color=COL_GREEN).pack(pady=15, fill="x", padx=40)

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

        # Biến số dư để tính %
        balance = acc['balance'] if acc else 1.0
        if balance == 0: balance = 1.0

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
            
            current_risk_pct = params.get("RISK_PERCENT", config.RISK_PER_TRADE_PERCENT)
            
            try: mlot = float(self.var_manual_lot.get() or 0)
            except: mlot = 0.0
            
            f_lot = mlot if mlot > 0 else 0
            if f_lot == 0:
                risk_usd = acc['equity'] * (current_risk_pct/100)
                sl_dist = cur_price * (params["SL_PERCENT"]/100)
                if sl_dist > 0: f_lot = max(config.MIN_LOT_SIZE, min(round((risk_usd / (sl_dist * c_size)) / config.LOT_STEP) * config.LOT_STEP, config.MAX_LOT_SIZE))

            # FORMAT LOT SIZE
            self.lbl_prev_lot.configure(text=f"{'(MANUAL)' if mlot>0 else '(AUTO)'} LOT: {f_lot:.2f}", text_color="white" if mlot==0 else "#FFD700")
            
            comm_rate = self.get_fee_config(sym)
            comm_total = comm_rate * f_lot
            spread_cost = (tick.ask - tick.bid) * f_lot * c_size
            self.lbl_fee_info.configure(text=f"Fee: -${(comm_total + spread_cost):.2f} (Com:{comm_total:.1f}|Spr:{spread_cost:.1f})")

            try: msl, mtp = float(self.var_manual_sl.get() or 0), float(self.var_manual_tp.get() or 0)
            except: msl, mtp = 0, 0
            
            auto_sl_dist = cur_price * (params["SL_PERCENT"]/100)
            p_sl = msl if msl > 0 else (cur_price - auto_sl_dist if d=="BUY" else cur_price + auto_sl_dist)
            p_tp = mtp if mtp > 0 else (cur_price + abs(cur_price - p_sl) * params["TP_RR_RATIO"] if d=="BUY" else cur_price - abs(cur_price - p_sl) * params["TP_RR_RATIO"])
            
            # 1. Check SL Logic & DISPLAY %
            is_valid_sl = True
            if d == "BUY" and p_sl >= cur_price: is_valid_sl = False
            if d == "SELL" and p_sl <= cur_price: is_valid_sl = False
            
            if is_valid_sl:
                self.lbl_prev_sl.configure(text=f"{p_sl:.2f}", text_color=COL_RED)
                loss_dist = abs(cur_price - p_sl) 
                loss_val = loss_dist * f_lot * c_size
                loss_pct = (loss_val / balance) * 100
                self.lbl_prev_risk.configure(text=f"-${loss_val:.2f} ({loss_pct:.2f}%)", text_color=COL_RED)
            else:
                self.lbl_prev_sl.configure(text="INVALID", text_color=COL_WARN)
                self.lbl_prev_risk.configure(text="$ ---", text_color=COL_WARN)

            # 2. Check TP Logic & DISPLAY %
            is_valid_tp = True
            if d == "BUY" and p_tp <= cur_price: is_valid_tp = False
            if d == "SELL" and p_tp >= cur_price: is_valid_tp = False
            
            if is_valid_tp:
                self.lbl_prev_tp.configure(text=f"{p_tp:.2f}", text_color=COL_GREEN)
                prof_dist = abs(p_tp - cur_price)
                prof_val = prof_dist * f_lot * c_size
                prof_pct = (prof_val / balance) * 100
                self.lbl_prev_rew.configure(text=f"+${prof_val:.2f} ({prof_pct:.2f}%)", text_color=COL_GREEN)
            else:
                self.lbl_prev_tp.configure(text="INVALID", text_color=COL_WARN)
                self.lbl_prev_rew.configure(text="$ ---", text_color=COL_WARN)

            # --- CẬP NHẬT TSL PREVIEW (NEXT MILESTONE) ---
            if cur_tactic_str == "OFF":
                self.lbl_tsl_preview.configure(text="TSL: OFF")
            else:
                milestones = []
                one_r_dist = abs(cur_price - p_sl)
                is_buy = (d == "BUY")
                t_cfg = config.TSL_CONFIG
                
                if "BE" in cur_tactic_str and one_r_dist > 0:
                    trig_r = t_cfg.get("BE_OFFSET_RR", 0.8)
                    trig_p = cur_price + (one_r_dist * trig_r) if is_buy else cur_price - (one_r_dist * trig_r)
                    fee_d = (comm_total + spread_cost) / (f_lot * c_size) if (f_lot * c_size) > 0 else 0
                    mode = t_cfg.get("BE_MODE", "SOFT")
                    base = cur_price - fee_d if (is_buy and mode=="SOFT") else (cur_price + fee_d if (is_buy and mode=="SMART") else cur_price)
                    if not is_buy: base = cur_price + fee_d if mode=="SOFT" else (cur_price - fee_d if mode=="SMART" else cur_price)
                    be_sl = base + (t_cfg.get("BE_OFFSET_POINTS", 0) * point) if is_buy else base - (t_cfg.get("BE_OFFSET_POINTS", 0) * point)
                    milestones.append((abs(cur_price - trig_p), f"BE | {trig_p:.2f} -> {be_sl:.2f}"))

                if "STEP_R" in cur_tactic_str and one_r_dist > 0:
                    sz, rt = t_cfg.get("STEP_R_SIZE", 1.0), t_cfg.get("STEP_R_RATIO", 0.8)
                    n_trig = cur_price + (sz * one_r_dist) if is_buy else cur_price - (sz * one_r_dist)
                    n_sl = cur_price + (sz * one_r_dist * rt) if is_buy else cur_price - (sz * one_r_dist * rt)
                    milestones.append((abs(cur_price - n_trig), f"Step 1 | {n_trig:.2f} -> {n_sl:.2f}"))

                if "PNL" in cur_tactic_str and t_cfg.get("PNL_LEVELS") and acc:
                    lvl = t_cfg["PNL_LEVELS"][0]
                    req_profit_usd = acc['balance'] * (lvl[0]/100.0)
                    trig_p = cur_price + (req_profit_usd / (f_lot * c_size)) if is_buy else \
                             cur_price - (req_profit_usd / (f_lot * c_size))
                    milestones.append((abs(cur_price - trig_p), f"PnL {lvl[0]}% | {trig_p:.2f}"))

                if milestones:
                    closest = sorted(milestones, key=lambda x: x[0])[0][1]
                    self.lbl_tsl_preview.configure(text=f"Mục tiêu: {closest}")
                else:
                    self.lbl_tsl_preview.configure(text="TSL: Monitoring...")

        # --- LOGIC UPDATE UI MỚI (SMART UPDATE - CHỐNG GIẬT) ---
        existing_items = self.tree.get_children() # List of IDs (tickets)
        current_tickets_on_chart = []
        
        for p in positions:
            ticket_str = str(p.ticket)
            current_tickets_on_chart.append(ticket_str)

            p_tick = mt5.symbol_info_tick(p.symbol)
            p_sym_info = mt5.symbol_info(p.symbol)
            p_c_size = p_sym_info.trade_contract_size if p_sym_info else 1.0
            
            comm_val = getattr(p, 'commission', 0.0)
            swap_val = getattr(p, 'swap', 0.0)
            
            # Tính Spread Cost
            current_spread = (p_tick.ask - p_tick.bid) if p_tick else 0.0
            spread_cost_usd = current_spread * p.volume * p_c_size
            
            entry_fee = comm_val - spread_cost_usd 
            fee_str = f"Fee: ${entry_fee:.2f} | Sw: ${swap_val:.2f}"
            
            time_str = datetime.fromtimestamp(p.time).strftime("%d/%m %H:%M")

            is_buy = (p.type == mt5.ORDER_TYPE_BUY)
            icon = "🟢" if is_buy else "🔴"
            side_txt = "BUY" if is_buy else "SELL"
            
            order_str = f"{icon} {side_txt} {p.volume:.2f} {p.symbol} @ {p.price_open:.2f}"
            sl_txt = f"{p.sl:.2f}" if p.sl > 0 else "---"
            tp_txt = f"{p.tp:.2f}" if p.tp > 0 else "---"
            targets_str = f"{sl_txt}  |  {tp_txt}"

            risk_usd = abs(p.price_open - p.sl) * p.volume * p_c_size if p.sl > 0 else 0
            rew_usd = abs(p.price_open - p.tp) * p.volume * p_c_size if p.tp > 0 else 0
            
            risk_pct = (risk_usd / balance * 100) if balance > 0 else 0
            rew_pct = (rew_usd / balance * 100) if balance > 0 else 0
            
            is_sl_in_profit = False
            if is_buy and p.sl > p.price_open: is_sl_in_profit = True
            if not is_buy and p.sl > 0 and p.sl < p.price_open: is_sl_in_profit = True
            
            if p.sl == 0:
                risk_str = "No SL"
            elif is_sl_in_profit:
                risk_str = f"+${risk_usd:.1f} ({risk_pct:.1f}%)" 
            else:
                risk_str = f"-${risk_usd:.1f} ({risk_pct:.1f}%)"

            rew_str = f"+${rew_usd:.1f} ({rew_pct:.1f}%)" if p.tp > 0 else "No TP"
            rr_str = f"{risk_str}  |  {rew_str}"

            stt_txt = self.tsl_states_map.get(p.ticket, "Running")

            # Data row
            values_data = (
                time_str,
                order_str,
                targets_str,
                fee_str,
                rr_str,
                f"${p.profit:.2f}",
                stt_txt,
                "❌"
            )

            # NẾU TICKET ĐÃ CÓ TRÊN BẢNG -> CHỈ CẬP NHẬT (KHÔNG INSERT LẠI)
            if ticket_str in existing_items:
                self.tree.item(ticket_str, values=values_data)
            else:
                self.tree.insert("", "end", iid=ticket_str, values=values_data)

        # XÓA CÁC DÒNG KHÔNG CÒN TỒN TẠI (ĐÃ ĐÓNG LỆNH)
        for item in existing_items:
            if item not in current_tickets_on_chart:
                self.tree.delete(item)

    def handle_close_request(self, ticket):
        if self.var_confirm_close.get() and not messagebox.askyesno("Confirm", f"Close #{ticket}?"): return
        threading.Thread(target=lambda: self.connector.close_position(next((p for p in self.connector.get_all_open_positions() if p.ticket==ticket), None))).start()

    def on_click_trade(self):
        d, s, p, t = self.seg_direction.get(), self.cbo_symbol.get(), self.cbo_preset.get(), self.get_current_tactic_string()
        try: ml, mt, ms = float(self.var_manual_lot.get() or 0), float(self.var_manual_tp.get() or 0), float(self.var_manual_sl.get() or 0)
        except: ml=0
        
        self.log_message(f"Exec {d} {s} | TSL: [{t}]...")
        
        def run_trade_thread():
            result = self.trade_mgr.execute_manual_trade(d, p, s, self.var_strict_mode.get(), ml, mt, ms, self.var_bypass_checklist.get(), t)
            if "SUCCESS" not in result:
                self.log_message(f"❌ EXEC FAILED: {result}", error=True)

        threading.Thread(target=run_trade_thread).start()

    def show_history_popup(self):
        top = ctk.CTkToplevel(self); top.title("History"); top.geometry("700x450")
        tr = ttk.Treeview(top, columns=("Time", "Sym", "Type", "PnL", "Reason"), show="headings"); tr.pack(fill="both", expand=True)
        for c in tr["columns"]: tr.heading(c, text=c)
        for h in self.trade_mgr.state.get("daily_history", []): 
            tr.insert("", "end", values=(h['time'], h['symbol'], h['type'], f"${h['profit']:.2f}", h.get('reason','')))

if __name__ == "__main__":
    try:
        app = BotUI()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Đang đóng ứng dụng từ Terminal...")
        sys.exit(0)