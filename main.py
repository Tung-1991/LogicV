# -*- coding: utf-8 -*-
# FILE: main.py
# Giao diện điều khiển V2.1 (Execution Tool)

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
        self.root.title("V2.1 EXECUTION TOOL")
        self.root.geometry("360x520")
        self.root.configure(bg="#1e1e1e") # Màu nền tối
        self.root.attributes("-topmost", True) # Luôn hiện trên cùng các cửa sổ khác
        
        # Khóa luồng để tránh xung đột dữ liệu UI
        self.lock = threading.Lock()

        # --- 1. KHỞI TẠO CORE ---
        self.log_buffer = [] # Buffer ghi log tạm thời
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

        # B. Checklist Panel (Traffic Lights)
        self.frm_check = tk.LabelFrame(self.root, text=" PRE-TRADE CHECKLIST ", font=("Arial", 9, "bold"), fg="gray", bg="#1e1e1e")
        self.frm_check.pack(fill="x", padx=10, pady=5)
        
        self.check_labels = {}
        checks = ["Kết nối MT5", "Daily Loss", "Chuỗi Thua", "Số Lệnh/Ngày", "Trạng thái"]
        
        for name in checks:
            lbl = tk.Label(self.frm_check, text=f"• {name}", font=("Consolas", 10), bg="#1e1e1e", fg="gray", anchor="w")
            lbl.pack(fill="x", padx=10, pady=2)
            self.check_labels[name] = lbl

        # C. Buttons Area
        self.frm_btn = tk.Frame(self.root, bg="#1e1e1e")
        self.frm_btn.pack(pady=15)
        
        # Nút LONG (Xanh)
        self.btn_long = tk.Button(self.frm_btn, text="LONG\n(BUY)", font=("Arial", 12, "bold"), 
                                  bg="#2e7d32", fg="white", width=12, height=2,
                                  command=lambda: self.on_click_trade("BUY"))
        self.btn_long.grid(row=0, column=0, padx=5)
        
        # Nút SHORT (Đỏ)
        self.btn_short = tk.Button(self.frm_btn, text="SHORT\n(SELL)", font=("Arial", 12, "bold"), 
                                   bg="#c62828", fg="white", width=12, height=2,
                                   command=lambda: self.on_click_trade("SELL"))
        self.btn_short.grid(row=0, column=1, padx=5)

        # D. Log Panel
        self.lbl_log_title = tk.Label(self.root, text=" SYSTEM LOG:", font=("Arial", 8), fg="gray", bg="#1e1e1e", anchor="w")
        self.lbl_log_title.pack(fill="x", padx=10)
        
        self.txt_log = tk.Text(self.root, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", padx=10, pady=(0, 10))

    def log(self, msg, error=False):
        """Ghi log vào ô text bên dưới"""
        timestamp = time.strftime("%H:%M:%S")
        text = f"[{timestamp}] {msg}\n"
        
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", text)
        if error:
            # Highlight dòng lỗi màu đỏ
            end_index = self.txt_log.index("end-1c")
            start_index = f"{end_index} linestart"
            self.txt_log.tag_add("error", start_index, end_index)
            self.txt_log.tag_config("error", foreground="#ff5252")
            
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def bg_update_loop(self):
        """Vòng lặp chạy ngầm (Background Thread)"""
        while self.running:
            try:
                # 1. Update Logic Trade (Trailing SL, Check PnL...)
                self.trade_mgr.update_running_trades()
                
                # 2. Lấy dữ liệu mới nhất
                acc_info = self.connector.get_account_info()
                current_state = self.trade_mgr.state
                
                # 3. Chạy Checklist
                check_result = self.checklist_mgr.run_pre_trade_checks(acc_info, current_state)
                
                # 4. Đẩy cập nhật sang luồng UI chính
                self.root.after(0, self.update_ui_components, acc_info, current_state, check_result)
                
            except Exception as e:
                print(f"BG Error: {e}")
            
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui_components(self, acc, state, check_res):
        """Cập nhật màu sắc, chữ nghĩa trên UI"""
        # Header
        if acc:
            self.lbl_equity.config(text=f"EQUITY: ${acc['equity']:,.2f}")
        
        pnl = state["pnl_today"]
        streak = state["losing_streak"]
        pnl_color = "#00e676" if pnl >= 0 else "#ff5252"
        self.lbl_pnl.config(text=f"PnL Today: ${pnl:.2f}  |  Streak: {streak}", fg=pnl_color)

        # Checklist
        can_trade = check_res["passed"]
        
        for item in check_res["checks"]:
            name = item["name"]
            status = item["status"]
            msg = item["msg"]
            
            # Chọn màu
            color = "#00e676" if status == "OK" else "#ff5252"
            icon = "✔" if status == "OK" else "✖"
            
            if name in self.check_labels:
                self.check_labels[name].config(text=f"{icon} {name}: {msg}", fg=color)

        # Buttons Enable/Disable
        btn_state = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != btn_state:
            self.btn_long.config(state=btn_state)
            self.btn_short.config(state=btn_state)
            
            if not can_trade:
                self.log("HỆ THỐNG KHÓA: Vi phạm checklist!", error=True)
            else:
                self.log("HỆ THỐNG SẴN SÀNG.")

    def on_click_trade(self, direction):
        """Sự kiện bấm nút"""
        self.log(f"Đang yêu cầu lệnh {direction}...")
        
        # Chạy lệnh trong thread riêng để ko đơ UI
        def run_trade():
            res = self.trade_mgr.execute_manual_trade(direction)
            if res == "SUCCESS":
                self.root.after(0, lambda: self.log(f"✅ ĐÃ KHỚP LỆNH {direction}!"))
            else:
                self.root.after(0, lambda: self.log(f"❌ LỖI: {res}", error=True))
        
        threading.Thread(target=run_trade).start()

# --- ENTRY POINT ---
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("Đang thoát...")
        sys.exit()