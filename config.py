# -*- coding: utf-8 -*-
# FILE: config.py
# Cấu hình chuẩn Logic V2.1 (Execution-based Scalping)

# === 1. KẾT NỐI & HỆ THỐNG ===
SYMBOL = "BTCUSD"           # Cặp tiền trade (Nhớ đổi đúng tên trên MT5, ví dụ: BTCUSDm)
MAGIC_NUMBER = 8888         # Định danh để phân biệt lệnh của Tool này
LOOP_SLEEP_SECONDS = 1      # Tốc độ cập nhật UI (giây)

# === 2. QUẢN LÝ VỐN (RULE 2 - CỐT LÕI) ===
RISK_MODE = "PERCENT"       # "PERCENT" (Risk theo % vốn) hoặc "FIXED_USD"
RISK_PER_TRADE_PERCENT = 0.30  # Chuẩn V2.1: 0.3% Equity mỗi lệnh
RISK_PER_TRADE_USD = 10.0      # Dùng nếu để mode FIXED_USD

# === 3. GIỚI HẠN KỶ LUẬT (THE SHIELD) ===
MAX_DAILY_LOSS_PERCENT = 1.5   # Rule 3: Lỗ quá 1.5% ngày -> KHÓA APP
MAX_LOSING_STREAK = 3          # Rule 4: Thua 3 lệnh liên tiếp -> KHÓA APP
MAX_TRADES_PER_DAY = 15        # Rule 5: Giới hạn số lệnh/ngày
MAX_RISK_ALLOWED = 2.0         # Safety: Không bao giờ cho phép tính ra risk > 2%

# === 4. PRESET SCALPING (CHIẾN LƯỢC) ===
# Cấu hình mặc định cho nút bấm
PRESET_SCALPING_FAST = {
    "SL_MODE": "PERCENT",      # Cách tính SL: "PERCENT" (theo giá) hoặc "ATR"
    "TP_MODE": "RR",           # Cách tính TP: "RR" (Risk:Reward) hoặc "PERCENT"
    
    "SL_PERCENT": 0.4,         # Stoploss: 0.4% giá trị (Ví dụ BTC 50k -> SL 200$)
    "TP_RR_RATIO": 1.5,        # TP = 1.5 lần Risk (RR 1:1.5)
    
    "BE_TRIGGER_RR": 0.8,      # Dời về hòa vốn khi lãi chạy được 0.8R
    "TRAILING_MODE": "ATR",    # Trailing Stop theo ATR
    "ATR_PERIOD": 14,
    "ATR_MULTIPLIER": 2.0      # Khoảng cách Trailing (2 x ATR)
}

# === 5. GIỚI HẠN SÀN (EXNESS) ===
MIN_LOT_SIZE = 0.01        # Lot tối thiểu
MAX_LOT_SIZE = 200.0       # Lot tối đa
LOT_STEP = 0.01            # Bước nhảy lot