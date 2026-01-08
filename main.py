# -*- coding: utf-8 -*-
# FILE: main.py
# Giao diện điều khiển V2.2 (Hỗ trợ chọn Preset & Fixed Lot)

import tkinter as tk
from tkinter import ttk
import threading
import time
import sys

# Import các module cốt lõi
import config
from core.exness_connector import ExnessConnector
from core.checklist_manager import ChecklistManager
from core.trade_manager import TradeManager
from core.storage_manager import load_state

class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("V2.2 EXECUTION TOOL")
        self.root.geometry("380x600") # Tăng chiều cao lên chút để chứa thêm nút
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-topmost", True)
        
        self.lock = threading.Lock()

        # --- 1. KHỞI TẠO CORE ---
        self.log_buffer = []
        print(">>> Đang kết nối MT5...")
        
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> Kết nối MT5 THÀNH CÔNG!")
        else:
            print(">>> LỖI KẾT NỐI MT5! Vui lòng kiểm tra.")

        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)
        
        # --- 2. XÂY DỰNG GIAO DIỆN ---
        self.setup_ui()

        # --- 3. CHẠY BACKGROUND THREAD ---
        self.running = True
        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()

    def setup_ui(self):
        # A. Header (Equity & PnL)
        self.frm_head = tk.Frame(self.root, bg="#1e1e1e")
        self.frm_head.pack(fill="x", pady=10)
        
        self.lbl_equity = tk.Label(self.frm_head, text="EQUITY: $----", font=("Arial", 16, "bold"), fg="#00e676", bg="#1e1e1e")
        self.lbl_equity.pack()
        
        self.lbl_pnl = tk.Label(self.frm_head, text="PnL Today: $0.00", font=("Arial", 11), fg="white", bg="#1e1e1e")
        self.lbl_pnl.pack()

        # === B. STRATEGY SELECTOR (MỚI) ===
        self.frm_strat = tk.LabelFrame(self.root, text=" STRATEGY & RISK ", font=("Arial", 9, "bold"), fg="#FFD700", bg="#1e1e1e")
        self.frm_strat.pack(fill="x", padx=10, pady=5)
        
        # Dòng 1: Chọn Preset
        self.lbl_mode = tk.Label(self.frm_strat, text="Preset:", font=("Arial", 9), fg="white", bg="#1e1e1e")
        self.lbl_mode.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # Combobox chọn chiến lược
        preset_names = list(config.PRESETS.keys())
        self.cbo_preset = ttk.Combobox(self.frm_strat, values=preset_names, state="readonly", width=15)
        self.cbo_preset.set(config.DEFAULT_PRESET) # Mặc định là SCALPING
        self.cbo_preset.grid(row=0, column=1, padx=5, pady=5)
        self.cbo_preset.bind("<<ComboboxSelected>>", self.on_preset_change)

        # Dòng 2: Mô tả Preset
        self.lbl_desc = tk.Label(self.frm_strat, text="...", font=("Arial", 8, "italic"), fg="gray", bg="#1e1e1e")
        self.lbl_desc.grid(row=1, column=0, columnspan=2, padx=5, sticky="w")
        
        # Dòng 3: Hiển thị Mode Lot (Fixed/Dynamic)
        lot_info = f"MODE: {config.LOT_SIZE_MODE}"
        if config.LOT_SIZE_MODE == "FIXED":
            lot_info += f" ({config.FIXED_LOT_VOLUME} lot)"
        
        self.lbl_risk_info = tk.Label(self.frm_strat, text=lot_info, font=("Consolas", 9, "bold"), fg="#00bcd4", bg="#1e1e1e")
        self.lbl_risk_info.grid(row=2, column=0, columnspan=2, padx=5, pady=(0,5), sticky="w")

        # Gọi hàm cập nhật mô tả lần đầu
        self.on_preset_change(None)

        # C. Checklist Panel
        self.frm_check = tk.LabelFrame(self.root, text=" PRE-TRADE CHECKLIST ", font=("Arial", 9, "bold"), fg="gray", bg="#1e1e1e")
        self.frm_check.pack(fill="x", padx=10, pady=5)
        
        self.check_labels = {}
        checks = ["Kết nối MT5", "Daily Loss", "Chuỗi Thua", "Số Lệnh/Ngày", "Trạng thái"]
        
        for name in checks:
            lbl = tk.Label(self.frm_check, text=f"• {name}", font=("Consolas", 10), bg="#1e1e1e", fg="gray", anchor="w")
            lbl.pack(fill="x", padx=10, pady=2)
            self.check_labels[name] = lbl

        # D. Buttons Area
        self.frm_btn = tk.Frame(self.root, bg="#1e1e1e")
        self.frm_btn.pack(pady=15)
        
        self.btn_long = tk.Button(self.frm_btn, text="LONG\n(BUY)", font=("Arial", 12, "bold"), 
                                  bg="#2e7d32", fg="white", width=12, height=2,
                                  command=lambda: self.on_click_trade("BUY"))
        self.btn_long.grid(row=0, column=0, padx=5)
        
        self.btn_short = tk.Button(self.frm_btn, text="SHORT\n(SELL)", font=("Arial", 12, "bold"), 
                                   bg="#c62828", fg="white", width=12, height=2,
                                   command=lambda: self.on_click_trade("SELL"))
        self.btn_short.grid(row=0, column=1, padx=5)

        # E. Log Panel
        self.lbl_log_title = tk.Label(self.root, text=" SYSTEM LOG:", font=("Arial", 8), fg="gray", bg="#1e1e1e", anchor="w")
        self.lbl_log_title.pack(fill="x", padx=10)
        
        self.txt_log = tk.Text(self.root, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", padx=10, pady=(0, 10))

    def on_preset_change(self, event):
        """Khi chọn dropdown, cập nhật dòng mô tả"""
        selected = self.cbo_preset.get()
        if selected in config.PRESETS:
            desc = config.PRESETS[selected]["DESC"]
            self.lbl_desc.config(text=f"Info: {desc}")
        
    def log(self, msg, error=False):
        timestamp = time.strftime("%H:%M:%S")
        text = f"[{timestamp}] {msg}\n"
        
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", text)
        if error:
            end_index = self.txt_log.index("end-1c")
            start_index = f"{end_index} linestart"
            self.txt_log.tag_add("error", start_index, end_index)
            self.txt_log.tag_config("error", foreground="#ff5252")
            
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def bg_update_loop(self):
        while self.running:
            try:
                self.trade_mgr.update_running_trades()
                acc_info = self.connector.get_account_info()
                current_state = self.trade_mgr.state
                check_result = self.checklist_mgr.run_pre_trade_checks(acc_info, current_state)
                
                self.root.after(0, self.update_ui_components, acc_info, current_state, check_result)
            except Exception as e:
                print(f"BG Error: {e}")
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui_components(self, acc, state, check_res):
        if acc:
            self.lbl_equity.config(text=f"EQUITY: ${acc['equity']:,.2f}")
        
        pnl = state["pnl_today"]
        streak = state["losing_streak"]
        pnl_color = "#00e676" if pnl >= 0 else "#ff5252"
        self.lbl_pnl.config(text=f"PnL Today: ${pnl:.2f}  |  Streak: {streak}", fg=pnl_color)

        can_trade = check_res["passed"]
        
        for item in check_res["checks"]:
            name = item["name"]
            status = item["status"]
            msg = item["msg"]
            color = "#00e676" if status == "OK" else "#ff5252"
            icon = "✔" if status == "OK" else "✖"
            
            if name in self.check_labels:
                self.check_labels[name].config(text=f"{icon} {name}: {msg}", fg=color)

        btn_state = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != btn_state:
            self.btn_long.config(state=btn_state)
            self.btn_short.config(state=btn_state)
            if not can_trade:
                self.log("CHECKLIST: BỊ KHÓA DO VI PHẠM!", error=True)
            else:
                self.log("CHECKLIST: SẴN SÀNG.")

    def on_click_trade(self, direction):
        # Lấy preset hiện tại đang chọn ở Dropdown
        selected_preset = self.cbo_preset.get()
        self.log(f"Yêu cầu {direction} ({selected_preset})...")
        
        def run_trade():
            # Truyền thêm preset_name vào hàm xử lý
            res = self.trade_mgr.execute_manual_trade(direction, selected_preset)
            if res == "SUCCESS":
                self.root.after(0, lambda: self.log(f"✅ ĐÃ KHỚP LỆNH {direction}!"))
            else:
                self.root.after(0, lambda: self.log(f"❌ LỖI: {res}", error=True))
        
        threading.Thread(target=run_trade).start()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit()