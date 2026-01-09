# -*- coding: utf-8 -*-
# FILE: main.py
# V4.1: Ultimate UI + Manual Reset + Smart Color Checklist

import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import threading
import time
import sys
from datetime import datetime
import MetaTrader5 as mt5

import config
from core.exness_connector import ExnessConnector
from core.checklist_manager import ChecklistManager
from core.trade_manager import TradeManager
# [MOD] Import thêm save_state để dùng cho nút Reset
from core.storage_manager import load_state, save_state

class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PRO SCALPING V4.0 (ULTIMATE)")
        self.root.geometry("1100x700") # Mở rộng chiều ngang để chứa bảng to
        self.root.configure(bg="#121212")
        self.root.attributes("-topmost", True)
        
        self.var_strict_mode = tk.BooleanVar(value=config.STRICT_MODE_DEFAULT)
        self.var_confirm_close = tk.BooleanVar(value=True) # Mặc định hỏi trước khi đóng
        self.running = True

        # --- CORE INIT ---
        print(">>> Đang kết nối MT5...")
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> MT5 CONNECTED.")
        
        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)

        # --- UI LAYOUT ---
        self.main_paned = tk.PanedWindow(root, orient="horizontal", bg="#121212")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        self.frm_left = tk.Frame(self.main_paned, bg="#1e1e1e", width=380) # Tăng width bên trái chút
        self.frm_right = tk.Frame(self.main_paned, bg="#252526", width=700)
        
        self.main_paned.add(self.frm_left)
        self.main_paned.add(self.frm_right)

        self.setup_left_panel()
        self.setup_right_panel()

        # Thread Update
        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log("Hệ thống V4.0 đã khởi động. Sẵn sàng chiến đấu!")

    def setup_left_panel(self):
        # 1. HEADER (Equity)
        self.lbl_equity = tk.Label(self.frm_left, text="$----", font=("Impact", 24), fg="#00e676", bg="#1e1e1e")
        self.lbl_equity.pack(pady=(15, 0))
        self.lbl_stats = tk.Label(self.frm_left, text="PnL: $0.00 | Streak: 0", font=("Arial", 11), fg="white", bg="#1e1e1e")
        self.lbl_stats.pack(pady=(0, 5)) # Giảm padding dưới để nhét nút Reset

        # [NEW] NÚT RESET STATS
        btn_reset = tk.Button(self.frm_left, text="🔄 Reset Daily Stats", font=("Arial", 8), 
                              bg="#333333", fg="gray", bd=0, activebackground="#444", activeforeground="white",
                              command=self.reset_daily_stats)
        btn_reset.pack(pady=(0, 15))

        # 2. SETUP BOX
        frm_setup = tk.LabelFrame(self.frm_left, text=" SETUP ", font=("Arial", 9, "bold"), fg="#FFD700", bg="#1e1e1e")
        frm_setup.pack(fill="x", padx=10, pady=5)

        # Chọn Coin & Preset
        f1 = tk.Frame(frm_setup, bg="#1e1e1e")
        f1.pack(fill="x", pady=5)
        
        self.cbo_symbol = ttk.Combobox(f1, values=config.COIN_LIST, state="readonly", width=10)
        self.cbo_symbol.set(config.DEFAULT_SYMBOL)
        self.cbo_symbol.pack(side="left", padx=5)
        
        self.cbo_preset = ttk.Combobox(f1, values=list(config.PRESETS.keys()), state="readonly", width=10)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.pack(side="left", padx=5)
        
        # [NEW] HIỆN GIÁ REALTIME
        self.lbl_price = tk.Label(f1, text="0.00", font=("Consolas", 12, "bold"), fg="#00e676", bg="#1e1e1e")
        self.lbl_price.pack(side="right", padx=10)

        # Strict Mode
        tk.Checkbutton(frm_setup, text="Strict Mode (Check Lag)", variable=self.var_strict_mode, 
                       bg="#1e1e1e", fg="gray", selectcolor="#1e1e1e", activebackground="#1e1e1e").pack(anchor="w", padx=5)

        # 3. LIVE PREVIEW (Chi tiết hơn)
        frm_preview = tk.LabelFrame(self.frm_left, text=" PREVIEW (Dự kiến) ", font=("Arial", 9, "bold"), fg="#03A9F4", bg="#1e1e1e")
        frm_preview.pack(fill="x", padx=10, pady=5)
        
        # Dòng 1: Lot & Risk
        fp1 = tk.Frame(frm_preview, bg="#1e1e1e")
        fp1.pack(fill="x", padx=5, pady=2)
        self.lbl_preview_lot = tk.Label(fp1, text="Lot: ---", font=("Consolas", 11, "bold"), fg="white", bg="#1e1e1e")
        self.lbl_preview_lot.pack(side="left")
        self.lbl_preview_risk = tk.Label(fp1, text="Risk: $---", font=("Consolas", 11, "bold"), fg="#ff5252", bg="#1e1e1e")
        self.lbl_preview_risk.pack(side="right")
        
        # Dòng 2: TP / SL
        fp2 = tk.Frame(frm_preview, bg="#1e1e1e")
        fp2.pack(fill="x", padx=5, pady=2)
        self.lbl_preview_tp = tk.Label(fp2, text="TP: ---", font=("Consolas", 9), fg="#00e676", bg="#1e1e1e")
        self.lbl_preview_tp.pack(side="left")
        self.lbl_preview_sl = tk.Label(fp2, text="SL: ---", font=("Consolas", 9), fg="#ff5252", bg="#1e1e1e")
        self.lbl_preview_sl.pack(side="right")

        # Dòng 3: TSL Trigger
        self.lbl_preview_tsl = tk.Label(frm_preview, text="TSL Start @: ---", font=("Consolas", 9, "italic"), fg="gray", bg="#1e1e1e")
        self.lbl_preview_tsl.pack(anchor="w", padx=5, pady=(0,5))

        # 4. CHECKLIST (Màu sắc)
        frm_check = tk.LabelFrame(self.frm_left, text=" CHECKLIST ", fg="gray", bg="#1e1e1e")
        frm_check.pack(fill="x", padx=10, pady=5)
        self.check_labels = {}
        # Danh sách key phải khớp với checklist_manager
        check_keys = ["Mạng/Spread", "Daily Loss", "Chuỗi Thua", "Số Lệnh", "Trạng thái"]
        for name in check_keys:
            l = tk.Label(frm_check, text=f"• {name}", font=("Arial", 9), bg="#1e1e1e", fg="gray", anchor="w")
            l.pack(fill="x", padx=5)
            self.check_labels[name] = l

        # 5. BUTTONS
        f_btn = tk.Frame(self.frm_left, bg="#1e1e1e")
        f_btn.pack(pady=10)
        self.btn_long = tk.Button(f_btn, text="LONG", bg="#2e7d32", fg="white", font=("Arial", 12, "bold"), width=12, height=2,
                                  command=lambda: self.on_click_trade("BUY"))
        self.btn_long.grid(row=0, column=0, padx=5)
        
        self.btn_short = tk.Button(f_btn, text="SHORT", bg="#c62828", fg="white", font=("Arial", 12, "bold"), width=12, height=2,
                                   command=lambda: self.on_click_trade("SELL"))
        self.btn_short.grid(row=0, column=1, padx=5)

        # 6. SYSTEM LOG
        tk.Label(self.frm_left, text="SYSTEM LOG:", font=("Arial", 8, "bold"), fg="gray", bg="#1e1e1e", anchor="w").pack(fill="x", padx=10)
        self.txt_log = tk.Text(self.frm_left, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def setup_right_panel(self):
        # Header + History Button
        h_frame = tk.Frame(self.frm_right, bg="#252526")
        h_frame.pack(fill="x", pady=10, padx=5)
        
        tk.Label(h_frame, text="RUNNING TRADES", font=("Arial", 11, "bold"), fg="white", bg="#252526").pack(side="left")
        
        # [NEW] Nút Lịch sử
        tk.Button(h_frame, text="📜 LỊCH SỬ HÔM NAY", bg="#424242", fg="white", font=("Arial", 8),
                  command=self.show_history_popup).pack(side="right")

        # Table (Enhanced)
        cols = ("Ticket", "Time", "Symbol", "Type", "Vol", "TP", "SL", "TSL", "PnL", "Close")
        self.tree = ttk.Treeview(self.frm_right, columns=cols, show="headings", height=22)
        
        # Config Columns
        self.tree.heading("Ticket", text="#")
        self.tree.column("Ticket", width=60, anchor="center")
        
        self.tree.heading("Time", text="Time")
        self.tree.column("Time", width=60, anchor="center")

        self.tree.heading("Symbol", text="Coin")
        self.tree.column("Symbol", width=60, anchor="center")
        
        self.tree.heading("Type", text="Type")
        self.tree.column("Type", width=40, anchor="center")
        
        self.tree.heading("Vol", text="Vol")
        self.tree.column("Vol", width=40, anchor="center")

        self.tree.heading("TP", text="TP")
        self.tree.column("TP", width=60, anchor="center")

        self.tree.heading("SL", text="SL")
        self.tree.column("SL", width=60, anchor="center")

        self.tree.heading("TSL", text="TSL")
        self.tree.column("TSL", width=40, anchor="center") # Checkbox style

        self.tree.heading("PnL", text="PnL ($)")
        self.tree.column("PnL", width=60, anchor="center")

        self.tree.heading("Close", text="X")
        self.tree.column("Close", width=30, anchor="center") # Button style
        
        self.tree.pack(fill="both", expand=True, padx=5)

        # Bắt sự kiện Click vào bảng (Để xử lý nút TSL và Close)
        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)

        # Footer Checkbox
        f_foot = tk.Frame(self.frm_right, bg="#252526")
        f_foot.pack(fill="x", pady=5, padx=5)
        
        tk.Checkbutton(f_foot, text="Hỏi xác nhận trước khi đóng lệnh (Safety)", variable=self.var_confirm_close,
                       bg="#252526", fg="white", selectcolor="#252526", activebackground="#252526").pack(anchor="w")

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
        except:
            pass
    
    # [NEW] HÀM RESET THỦ CÔNG
    def reset_daily_stats(self):
        if messagebox.askyesno("Xác nhận", "Bạn muốn xóa toàn bộ Lãi/Lỗ và bộ đếm hôm nay về 0?"):
            self.trade_mgr.state["pnl_today"] = 0.0
            self.trade_mgr.state["trades_today_count"] = 0
            self.trade_mgr.state["losing_streak"] = 0
            # Lưu ý: Không reset active_trades để tránh lỗi lệnh treo
            self.trade_mgr.state["daily_history"] = []
            
            save_state(self.trade_mgr.state)
            self.log(">>> Đã Reset thủ công thống kê ngày!", True)

    # --- LOGIC UPDATE ---
    def bg_update_loop(self):
        while self.running:
            try:
                sym = self.cbo_symbol.get()
                preset = self.cbo_preset.get()
                strict = self.var_strict_mode.get()

                # Update Logic
                self.trade_mgr.update_running_trades()
                acc = self.connector.get_account_info()
                state = self.trade_mgr.state
                
                # Run Checks (Nội dung checks giờ đã chi tiết hơn từ checklist_manager mới)
                check_res = self.checklist_mgr.run_pre_trade_checks(acc, state, sym, strict)
                
                # Get Market Data
                tick = mt5.symbol_info_tick(sym)
                
                # Get Running Trades
                positions = self.connector.get_all_open_positions()
                my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]

                self.root.after(0, self.update_ui, acc, state, check_res, tick, preset, sym, my_pos)

            except Exception as e:
                print(e)
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui(self, acc, state, check_res, tick, preset, sym, positions):
        # 1. Stats & Price
        if acc: self.lbl_equity.config(text=f"${acc['equity']:,.2f}")
        
        pnl_color = "#00e676" if state["pnl_today"] >= 0 else "#ff5252"
        self.lbl_stats.config(text=f"PnL: ${state['pnl_today']:.2f} | Streak: {state['losing_streak']}", fg=pnl_color)
        
        if tick:
            # Hiện giá Bid/Ask trung bình hoặc Ask để tham khảo
            self.lbl_price.config(text=f"{tick.ask:.2f}")

        # 2. Checklist (Màu sắc theo Status)
        can_trade = check_res["passed"]
        for item in check_res["checks"]:
            name = item["name"]
            stt = item["status"]
            msg = item["msg"]
            
            # [MOD] Chọn màu chuẩn (Cập nhật logic màu Cam)
            if stt == "OK": 
                color = "#00e676"     # Green (Mặc định)
                
                # Nếu là mục Daily Loss mà thấy số âm (nhưng vẫn OK) -> Chuyển màu Cam cảnh báo
                if name == "Daily Loss" and "-" in msg:
                    color = "#ff9800" # Orange
                    
            elif stt == "WARN": color = "#FFD700" # Gold
            else: color = "#ff5252"               # Red
            
            if name in self.check_labels:
                icon = "✔" if stt == "OK" else ("!" if stt == "WARN" else "✖")
                self.check_labels[name].config(text=f"{icon} {name}: {msg}", fg=color)

        state_btn = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != state_btn:
            self.btn_long.config(state=state_btn)
            self.btn_short.config(state=state_btn)

        # 3. LIVE PREVIEW (TP/SL Calculation)
        if tick and acc:
            params = config.PRESETS.get(preset)
            sl_pct = params["SL_PERCENT"] / 100.0
            rr_ratio = params["TP_RR_RATIO"]
            be_rr = params["BE_TRIGGER_RR"]
            
            price = tick.ask # Lấy giá Ask làm chuẩn để tính preview Long
            equity = acc['equity']
            sl_dist = price * sl_pct
            
            contract_size = 1.0 
            sym_info = mt5.symbol_info(sym)
            if sym_info: contract_size = sym_info.trade_contract_size
            
            risk_usd = equity * (config.RISK_PER_TRADE_PERCENT / 100.0)
            
            if sl_dist > 0:
                raw_lot = risk_usd / (sl_dist * contract_size)
                lot = max(config.MIN_LOT_SIZE, round(raw_lot / config.LOT_STEP) * config.LOT_STEP)
                lot = min(lot, config.MAX_LOT_SIZE)
                real_risk = lot * sl_dist * contract_size
                
                # Tính các mốc giá (Ví dụ cho lệnh LONG)
                p_tp = price + (sl_dist * rr_ratio)
                p_sl = price - sl_dist
                p_tsl_start = price + (sl_dist * be_rr) # Giá kích hoạt BE
                
                self.lbl_preview_lot.config(text=f"Lot: {lot:.2f}")
                self.lbl_preview_risk.config(text=f"Risk: ${real_risk:.2f}")
                
                self.lbl_preview_tp.config(text=f"TP: {p_tp:.2f}")
                self.lbl_preview_sl.config(text=f"SL: {p_sl:.2f}")
                self.lbl_preview_tsl.config(text=f"TSL Start @: {p_tsl_start:.2f} (Est)")
            else:
                self.lbl_preview_lot.config(text="Lot: ???")

        # 4. Running Trades Table
        # Lưu lại selection hiện tại (nếu có) để không bị mất khi refresh
        # (Ở đây làm đơn giản là clear/redraw để cập nhật TSL status realtime)
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for p in positions:
            p_type = "BUY" if p.type == 0 else "SELL"
            
            # Time format
            time_str = datetime.fromtimestamp(p.time).strftime("%H:%M:%S")
            
            # PnL
            swap = getattr(p, 'swap', 0.0)
            commission = getattr(p, 'commission', 0.0)
            total_profit = p.profit + swap + commission
            
            # TSL Status Check
            is_tsl_on = self.trade_mgr.is_tsl_active(p.ticket)
            tsl_icon = "[ ☑ ]" if is_tsl_on else "[ ☐ ]"
            
            # Insert Row
            self.tree.insert("", "end", values=(
                p.ticket, 
                time_str,
                p.symbol, 
                p_type, 
                p.volume,
                f"{p.tp:.2f}",
                f"{p.sl:.2f}",
                tsl_icon,        # Cột TSL
                f"{total_profit:.2f}",
                "[ ❌ ]"         # Cột Close
            ))

    def on_tree_click(self, event):
        """Xử lý sự kiện click vào cột TSL hoặc cột Close"""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            # Xác định hàng và cột được click
            row_id = self.tree.identify_row(event.y)
            col_id = self.tree.identify_column(event.x)
            
            if not row_id: return
            
            item = self.tree.item(row_id)
            values = item['values']
            ticket = values[0]
            
            # Cột #8 là TSL (Vì index bắt đầu từ #1 trong Treeview logic cột)
            # col_id trả về dạng '#1', '#2'...
            
            # Mapping cột:
            # #1:Ticket, #2:Time, #3:Symbol, #4:Type, #5:Vol, #6:TP, #7:SL, #8:TSL, #9:PnL, #10:Close
            
            if col_id == "#8": # Click vào TSL
                new_state = self.trade_mgr.toggle_tsl(ticket)
                state_str = "BẬT" if new_state else "TẮT"
                self.log(f"Đã {state_str} TSL cho lệnh #{ticket}")
                # UI sẽ tự update ở nhịp tiếp theo
                
            elif col_id == "#10": # Click vào Close [X]
                self.handle_close_request(ticket)

    def handle_close_request(self, ticket):
        # Tìm position object
        positions = self.connector.get_all_open_positions()
        target = next((p for p in positions if p.ticket == ticket), None)
        
        if not target:
            self.log("Lệnh không còn tồn tại.", True)
            return

        # Check confirm
        if self.var_confirm_close.get():
            if not messagebox.askyesno("Xác nhận", f"Bạn chắc chắn muốn đóng lệnh #{ticket}?"):
                return
        
        # Đóng lệnh
        self.log(f"Đang đóng lệnh #{ticket}...")
        threading.Thread(target=lambda: self.connector.close_position(target)).start()

    def on_click_trade(self, direction):
        s = self.cbo_symbol.get()
        p = self.cbo_preset.get()
        strict = self.var_strict_mode.get()
        
        self.log(f"Đang gửi lệnh {direction} {s} ({p})...")
        
        def run():
            res = self.trade_mgr.execute_manual_trade(direction, p, s, strict)
            if res == "SUCCESS":
                self.root.after(0, lambda: self.log(f"✅ Đã khớp lệnh {direction} {s}!", False))
            elif res.startswith("CONFIRM"):
                # Có thể mở rộng popup confirm vốn nhỏ ở đây sau
                self.root.after(0, lambda: self.log(f"⚠️ Cảnh báo vốn nhỏ: {res}", True))
            else:
                self.root.after(0, lambda: self.log(f"❌ LỖI: {res}", True))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Lỗi: {res}"))
                
        threading.Thread(target=run).start()

    def show_history_popup(self):
        """Hiển thị cửa sổ lịch sử giao dịch trong ngày"""
        top = Toplevel(self.root)
        top.title("Lịch Sử Giao Dịch Hôm Nay")
        top.geometry("600x400")
        top.configure(bg="#1e1e1e")
        
        # Header
        lbl_title = tk.Label(top, text=f"BÁO CÁO NGÀY: {self.trade_mgr.state.get('date', 'N/A')}", 
                             font=("Arial", 12, "bold"), fg="#FFD700", bg="#1e1e1e")
        lbl_title.pack(pady=10)
        
        # Summary Info
        state = self.trade_mgr.state
        lbl_sum = tk.Label(top, text=f"Tổng Lãi/Lỗ: ${state['pnl_today']:.2f}\nSố lệnh: {state['trades_today_count']}\nChuỗi thua hiện tại: {state['losing_streak']}",
                           font=("Consolas", 10), fg="white", bg="#1e1e1e", justify="center")
        lbl_sum.pack(pady=5)
        
        tk.Label(top, text="(Chi tiết lệnh vui lòng xem trong MT5 History)", fg="gray", bg="#1e1e1e").pack(pady=20)
        
        btn_close = tk.Button(top, text="Đóng", command=top.destroy, bg="#424242", fg="white")
        btn_close.pack(pady=10)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit()