# -*- coding: utf-8 -*-
# FILE: main.py
# Giao diện điều khiển V2.4 (Full UI: Symbol Select, Strict Mode, Popup Confirm)
# Đã nâng cấp: Dynamic Coin List & Configurable Strict Mode

import tkinter as tk
from tkinter import ttk, messagebox
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
        self.root.title("V2.4 EXECUTION TOOL")
        self.root.geometry("380x680") # Tăng chiều cao chút để chứa đủ nút
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-topmost", True)
        
        # --- 1. KHỞI TẠO BIẾN TRẠNG THÁI ---
        # Biến lưu trạng thái Strict Mode (Lấy mặc định từ Config)
        try:
            default_strict = config.STRICT_MODE_DEFAULT
        except AttributeError:
            default_strict = True # Fallback nếu config chưa có
            
        self.var_strict_mode = tk.BooleanVar(value=default_strict)

        self.lock = threading.Lock()

        # --- 2. KHỞI TẠO CORE ---
        self.log_buffer = []
        print(">>> Đang kết nối MT5...")
        
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> Kết nối MT5 THÀNH CÔNG!")
        else:
            print(">>> LỖI KẾT NỐI MT5! Vui lòng kiểm tra.")

        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)
        
        # --- 3. XÂY DỰNG GIAO DIỆN ---
        self.setup_ui()

        # --- 4. CHẠY BACKGROUND THREAD ---
        self.running = True
        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()

    def setup_ui(self):
        # A. Header
        self.frm_head = tk.Frame(self.root, bg="#1e1e1e")
        self.frm_head.pack(fill="x", pady=10)
        
        self.lbl_equity = tk.Label(self.frm_head, text="EQUITY: $----", font=("Arial", 16, "bold"), fg="#00e676", bg="#1e1e1e")
        self.lbl_equity.pack()
        
        self.lbl_pnl = tk.Label(self.frm_head, text="PnL Today: $0.00", font=("Arial", 11), fg="white", bg="#1e1e1e")
        self.lbl_pnl.pack()

        # === B. SETUP PANEL (Chọn Coin, Preset, Mode) ===
        self.frm_strat = tk.LabelFrame(self.root, text=" SETUP ", font=("Arial", 9, "bold"), fg="#FFD700", bg="#1e1e1e")
        self.frm_strat.pack(fill="x", padx=10, pady=5)
        
        # Hàng 1: Chọn Coin & Preset
        tk.Label(self.frm_strat, text="Coin:", fg="white", bg="#1e1e1e").grid(row=0, column=0, padx=5, sticky="w")
        
        # --- CẬP NHẬT: Lấy danh sách coin từ Config ---
        try:
            coin_values = config.COIN_LIST
            default_sym = config.DEFAULT_SYMBOL
        except AttributeError:
            coin_values = ["BTCUSDm", "ETHUSDm", "XAUUSDm"] # Fallback
            default_sym = "BTCUSDm"

        self.cbo_symbol = ttk.Combobox(self.frm_strat, values=coin_values, state="normal", width=10)
        self.cbo_symbol.set(default_sym)
        self.cbo_symbol.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self.frm_strat, text="Pre:", fg="white", bg="#1e1e1e").grid(row=0, column=2, padx=5, sticky="w")
        self.cbo_preset = ttk.Combobox(self.frm_strat, values=list(config.PRESETS.keys()), state="readonly", width=8)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.grid(row=0, column=3, padx=5, pady=5)

        # Hàng 2: Checkbox Strict Mode
        # Biến self.var_strict_mode đã được khởi tạo trong __init__ với giá trị từ config
        self.chk_strict = tk.Checkbutton(self.frm_strat, text="Chặn trade nếu Lag/Spread cao", variable=self.var_strict_mode, 
                                         bg="#1e1e1e", fg="orange", selectcolor="#1e1e1e", activebackground="#1e1e1e")
        self.chk_strict.grid(row=1, column=0, columnspan=4, sticky="w", padx=5)

        # Hàng 3: Info Lot
        lot_info = f"MODE: {config.LOT_SIZE_MODE}"
        if config.LOT_SIZE_MODE == "FIXED":
            lot_info += f" ({config.FIXED_LOT_VOLUME} lot)"
        else:
            lot_info += f" (Risk {config.RISK_PER_TRADE_PERCENT}%)"
        
        tk.Label(self.frm_strat, text=lot_info, font=("Consolas", 9, "bold"), fg="#00bcd4", bg="#1e1e1e").grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=5)

        # C. Checklist Panel
        self.frm_check = tk.LabelFrame(self.root, text=" CHECKLIST ", font=("Arial", 9, "bold"), fg="gray", bg="#1e1e1e")
        self.frm_check.pack(fill="x", padx=10, pady=5)
        
        self.check_labels = {}
        # Thêm mục "Mạng & Spread" vào danh sách hiển thị
        checks = ["Mạng & Spread", "Daily Loss", "Chuỗi Thua", "Số Lệnh", "Trạng thái"]
        
        for name in checks:
            lbl = tk.Label(self.frm_check, text=f"• {name}", font=("Consolas", 10), bg="#1e1e1e", fg="gray", anchor="w")
            lbl.pack(fill="x", padx=10, pady=2)
            self.check_labels[name] = lbl

        # D. Buttons
        self.frm_btn = tk.Frame(self.root, bg="#1e1e1e")
        self.frm_btn.pack(pady=10)
        
        self.btn_long = tk.Button(self.frm_btn, text="LONG\n(BUY)", font=("Arial", 12, "bold"), 
                                  bg="#2e7d32", fg="white", width=12, height=2,
                                  command=lambda: self.on_click_trade("BUY"))
        self.btn_long.grid(row=0, column=0, padx=5)
        
        self.btn_short = tk.Button(self.frm_btn, text="SHORT\n(SELL)", font=("Arial", 12, "bold"), 
                                   bg="#c62828", fg="white", width=12, height=2,
                                   command=lambda: self.on_click_trade("SELL"))
        self.btn_short.grid(row=0, column=1, padx=5)

        # E. Log
        self.lbl_log_title = tk.Label(self.root, text=" SYSTEM LOG:", font=("Arial", 8), fg="gray", bg="#1e1e1e", anchor="w")
        self.lbl_log_title.pack(fill="x", padx=10)
        
        self.txt_log = tk.Text(self.root, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", padx=10, pady=(0, 10))

    def log(self, msg, error=False):
        timestamp = time.strftime("%H:%M:%S")
        text = f"[{timestamp}] {msg}\n"
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", text)
        if error:
            self.txt_log.tag_add("err", "end-2l", "end-1c")
            self.txt_log.tag_config("err", foreground="#ff5252")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def bg_update_loop(self):
        while self.running:
            try:
                # 1. Lấy thông tin realtime từ UI (Symbol & Strict Mode)
                current_symbol = self.cbo_symbol.get()
                is_strict = self.var_strict_mode.get()

                # 2. Update logic
                self.trade_mgr.update_running_trades()
                acc_info = self.connector.get_account_info()
                current_state = self.trade_mgr.state
                
                # 3. Chạy Checklist với thông tin mới nhất
                # Truyền symbol và strict mode vào để check spread/ping
                check_result = self.checklist_mgr.run_pre_trade_checks(acc_info, current_state, current_symbol, is_strict)
                
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
        self.lbl_pnl.config(text=f"PnL: ${pnl:.2f} | Streak: {streak}", fg=pnl_color)

        can_trade = check_res["passed"]
        
        for item in check_res["checks"]:
            name = item["name"]
            status = item["status"]
            msg = item["msg"]
            color = "#00e676" if status == "OK" else ("#FFA500" if status == "WARN" else "#ff5252")
            icon = "✔" if status == "OK" else "✖"
            if name in self.check_labels:
                self.check_labels[name].config(text=f"{icon} {name}: {msg}", fg=color)

        btn_state = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != btn_state:
            self.btn_long.config(state=btn_state)
            self.btn_short.config(state=btn_state)
            if not can_trade:
                self.log("CHECKLIST: BỊ KHÓA (Vi phạm Rule)", error=True)
            else:
                self.log("CHECKLIST: SẴN SÀNG.")

    def on_click_trade(self, direction):
        # Lấy toàn bộ tham số từ UI
        selected_preset = self.cbo_preset.get()
        selected_symbol = self.cbo_symbol.get()
        is_strict = self.var_strict_mode.get()
        
        # Gán ngược vào config để đồng bộ (nếu cần dùng ở chỗ khác)
        config.SYMBOL = selected_symbol
        
        self.log(f"Yêu cầu {direction} {selected_symbol} ({selected_preset})...")
        
        def run_trade_thread(force_min=False):
            # Gọi execute với đủ tham số mới
            res = self.trade_mgr.execute_manual_trade(
                direction, selected_preset, selected_symbol, is_strict, accept_min_lot=force_min
            )
            self.root.after(0, lambda: self.handle_trade_result(res, direction, selected_preset, selected_symbol, is_strict))
        
        threading.Thread(target=run_trade_thread).start()

    def handle_trade_result(self, res, direction, preset, symbol, strict):
        if res == "SUCCESS":
            self.log(f"✅ ĐÃ KHỚP LỆNH {direction}!")
            return

        # Xử lý Popup xác nhận vốn nhỏ
        if res.startswith("CONFIRM_LOW_CAP"):
            _, min_lot, risk_usd = res.split("|")
            msg = (f"⚠️ CẢNH BÁO VỐN NHỎ\n\n"
                   f"Theo rủi ro tính toán, lot quá nhỏ (< {min_lot}).\n"
                   f"Nếu đánh {min_lot} Lot, rủi ro lệnh này là: ~${risk_usd}.\n\n"
                   f"Bạn có CHẤP NHẬN vào lệnh không?")
            
            choice = messagebox.askyesno("Xác nhận ngoại lệ", msg)
            if choice:
                self.log(f"User chấp nhận rủi ro ${risk_usd}. Đang vào lại...")
                # Gọi lại thread với force_min=True
                threading.Thread(target=lambda: self.trade_mgr.execute_manual_trade(
                    direction, preset, symbol, strict, accept_min_lot=True
                )).start()
            else:
                self.log("❌ Đã hủy lệnh do rủi ro cao.")
        else:
            self.log(f"❌ LỖI: {res}", error=True)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit()