# -*- coding: utf-8 -*-
# FILE: main.py
# V3.1: Final Stable (Fix Crash Commission + Restore System Log)

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sys
import MetaTrader5 as mt5

import config
from core.exness_connector import ExnessConnector
from core.checklist_manager import ChecklistManager
from core.trade_manager import TradeManager
from core.storage_manager import load_state

class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PRO SCALPING V3.1 (STABLE)")
        self.root.geometry("800x650") # Tăng chiều cao/rộng để chứa đủ cả Log và Table
        self.root.configure(bg="#121212")
        self.root.attributes("-topmost", True)
        
        self.var_strict_mode = tk.BooleanVar(value=config.STRICT_MODE_DEFAULT)
        self.running = True

        # --- CORE INIT ---
        print(">>> Đang kết nối MT5...")
        self.connector = ExnessConnector()
        if self.connector.connect():
            print(">>> MT5 CONNECTED.")
        
        self.checklist_mgr = ChecklistManager(self.connector)
        self.trade_mgr = TradeManager(self.connector, self.checklist_mgr)

        # --- UI LAYOUT ---
        # Chia làm 2 cột: Left (Control + Log) - Right (Running Trades)
        self.main_paned = tk.PanedWindow(root, orient="horizontal", bg="#121212")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        self.frm_left = tk.Frame(self.main_paned, bg="#1e1e1e", width=350)
        self.frm_right = tk.Frame(self.main_paned, bg="#252526", width=450)
        
        self.main_paned.add(self.frm_left)
        self.main_paned.add(self.frm_right)

        self.setup_left_panel()
        self.setup_right_panel()

        # Thread Update
        self.thread = threading.Thread(target=self.bg_update_loop, daemon=True)
        self.thread.start()
        
        self.log("Hệ thống đã khởi động. Sẵn sàng chiến đấu!")

    def setup_left_panel(self):
        # 1. HEADER (Equity)
        self.lbl_equity = tk.Label(self.frm_left, text="$----", font=("Impact", 22), fg="#00e676", bg="#1e1e1e")
        self.lbl_equity.pack(pady=(10, 0))
        self.lbl_stats = tk.Label(self.frm_left, text="PnL: $0.00 | Streak: 0", font=("Arial", 10), fg="white", bg="#1e1e1e")
        self.lbl_stats.pack(pady=(0, 10))

        # 2. SETUP BOX
        frm_setup = tk.LabelFrame(self.frm_left, text=" SETUP ", font=("Arial", 9, "bold"), fg="#FFD700", bg="#1e1e1e")
        frm_setup.pack(fill="x", padx=10, pady=5)

        # Chọn Coin & Preset
        f1 = tk.Frame(frm_setup, bg="#1e1e1e")
        f1.pack(fill="x", pady=5)
        self.cbo_symbol = ttk.Combobox(f1, values=config.COIN_LIST, state="readonly", width=12)
        self.cbo_symbol.set(config.DEFAULT_SYMBOL)
        self.cbo_symbol.pack(side="left", padx=5)
        
        self.cbo_preset = ttk.Combobox(f1, values=list(config.PRESETS.keys()), state="readonly", width=10)
        self.cbo_preset.set(config.DEFAULT_PRESET)
        self.cbo_preset.pack(side="left", padx=5)

        # Strict Mode
        tk.Checkbutton(frm_setup, text="Strict Mode (Lag check)", variable=self.var_strict_mode, 
                       bg="#1e1e1e", fg="gray", selectcolor="#1e1e1e", activebackground="#1e1e1e").pack(anchor="w", padx=5)

        # 3. LIVE PREVIEW
        frm_preview = tk.LabelFrame(self.frm_left, text=" PREVIEW (Dự kiến) ", font=("Arial", 9, "bold"), fg="#03A9F4", bg="#1e1e1e")
        frm_preview.pack(fill="x", padx=10, pady=5)
        
        self.lbl_preview_lot = tk.Label(frm_preview, text="Lot: ---", font=("Consolas", 11, "bold"), fg="white", bg="#1e1e1e")
        self.lbl_preview_lot.pack(anchor="w", padx=10)
        
        self.lbl_preview_risk = tk.Label(frm_preview, text="Risk: $---", font=("Consolas", 11, "bold"), fg="#ff5252", bg="#1e1e1e")
        self.lbl_preview_risk.pack(anchor="w", padx=10)
        
        self.lbl_preview_sl = tk.Label(frm_preview, text="SL Dist: ---", font=("Consolas", 9), fg="gray", bg="#1e1e1e")
        self.lbl_preview_sl.pack(anchor="w", padx=10)

        # 4. CHECKLIST
        frm_check = tk.LabelFrame(self.frm_left, text=" CHECKLIST ", fg="gray", bg="#1e1e1e")
        frm_check.pack(fill="x", padx=10, pady=5)
        self.check_labels = {}
        for name in ["Mạng/Spread", "Daily Loss", "Chuỗi Thua", "Số Lệnh", "Trạng thái"]:
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

        # 6. SYSTEM LOG (KHÔI PHỤC LẠI Ở ĐÂY)
        tk.Label(self.frm_left, text="SYSTEM LOG:", font=("Arial", 8, "bold"), fg="gray", bg="#1e1e1e", anchor="w").pack(fill="x", padx=10)
        self.txt_log = tk.Text(self.frm_left, height=8, bg="black", fg="#00e676", font=("Consolas", 8), state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def setup_right_panel(self):
        # Header
        tk.Label(self.frm_right, text="RUNNING TRADES", font=("Arial", 10, "bold"), fg="white", bg="#252526").pack(pady=10)
        
        # Table
        cols = ("Ticket", "Symbol", "Type", "Lot", "PnL")
        self.tree = ttk.Treeview(self.frm_right, columns=cols, show="headings", height=20)
        
        self.tree.heading("Ticket", text="#")
        self.tree.column("Ticket", width=70)
        self.tree.heading("Symbol", text="Coin")
        self.tree.column("Symbol", width=70)
        self.tree.heading("Type", text="Type")
        self.tree.column("Type", width=50)
        self.tree.heading("Lot", text="Vol")
        self.tree.column("Lot", width=60)
        self.tree.heading("PnL", text="Profit ($)")
        self.tree.column("PnL", width=80)
        
        self.tree.pack(fill="both", expand=True, padx=5)

        # Close Button
        tk.Button(self.frm_right, text="❌ ĐÓNG LỆNH ĐANG CHỌN", bg="#424242", fg="white", font=("Arial", 10),
                  command=self.close_selected_trade).pack(pady=10, fill="x", padx=5)

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
                
                # Run Checks
                check_res = self.checklist_mgr.run_pre_trade_checks(acc, state, sym, strict)
                
                # Get Market Data for Preview
                tick = mt5.symbol_info_tick(sym)
                
                # Get Running Trades
                positions = self.connector.get_all_open_positions()
                my_pos = [p for p in positions if p.magic == config.MAGIC_NUMBER]

                self.root.after(0, self.update_ui, acc, state, check_res, tick, preset, sym, my_pos)

            except Exception as e:
                print(e)
            time.sleep(config.LOOP_SLEEP_SECONDS)

    def update_ui(self, acc, state, check_res, tick, preset, sym, positions):
        # 1. Stats
        if acc: self.lbl_equity.config(text=f"${acc['equity']:,.2f}")
        pnl_color = "#00e676" if state["pnl_today"] >= 0 else "#ff5252"
        self.lbl_stats.config(text=f"PnL: ${state['pnl_today']:.2f} | Streak: {state['losing_streak']}", fg=pnl_color)

        # 2. Checklist
        can_trade = check_res["passed"]
        for item in check_res["checks"]:
            name = item["name"]
            stt = item["status"]
            ui_name = name if name != "Mạng & Spread" else "Mạng/Spread"
            
            color = "#00e676" if stt == "OK" else ("#FFA500" if stt == "WARN" else "#ff5252")
            if ui_name in self.check_labels:
                self.check_labels[ui_name].config(text=f"{'✔' if stt=='OK' else '✖'} {name}: {item['msg']}", fg=color)

        state_btn = "normal" if can_trade else "disabled"
        if self.btn_long["state"] != state_btn:
            self.btn_long.config(state=state_btn)
            self.btn_short.config(state=state_btn)
            if not can_trade:
                # Log lý do khóa nút (chỉ log 1 lần nếu cần thiết, ở đây tạm thời chưa log để đỡ spam)
                pass

        # 3. LIVE PREVIEW
        if tick and acc:
            params = config.PRESETS.get(preset)
            sl_pct = params["SL_PERCENT"] / 100.0
            price = tick.ask
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
                
                self.lbl_preview_lot.config(text=f"Lot: {lot:.2f}")
                self.lbl_preview_risk.config(text=f"Risk: ${real_risk:.2f}")
                self.lbl_preview_sl.config(text=f"SL Dist: {sl_dist:.2f}")
            else:
                self.lbl_preview_lot.config(text="Lot: ???")

        # 4. Running Trades Table
        # Xóa cũ
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Thêm mới (FIX CRASH Ở ĐÂY)
        for p in positions:
            p_type = "BUY" if p.type == 0 else "SELL"
            
            # --- SAFE GET ATTRIBUTES ---
            # Dùng getattr để tránh lỗi nếu mt5 object thiếu thuộc tính
            swap = getattr(p, 'swap', 0.0)
            commission = getattr(p, 'commission', 0.0)
            profit = p.profit
            
            total_profit = profit + swap + commission
            # ---------------------------

            self.tree.insert("", "end", values=(p.ticket, p.symbol, p_type, p.volume, f"{total_profit:.2f}"))

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
                # Xử lý confirm nếu cần
                pass 
            else:
                self.root.after(0, lambda: self.log(f"❌ LỖI: {res}", True))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Lỗi: {res}"))
                
        threading.Thread(target=run).start()

    def close_selected_trade(self):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        ticket = item['values'][0]
        
        positions = self.connector.get_all_open_positions()
        target = next((p for p in positions if p.ticket == ticket), None)
        
        if target:
            if messagebox.askyesno("Confirm", f"Đóng lệnh #{ticket}?"):
                self.log(f"Đang đóng lệnh #{ticket}...")
                self.connector.close_position(target)
        else:
            self.log(f"Lệnh #{ticket} không tồn tại!", True)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BotUI(root)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit()