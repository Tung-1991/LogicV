# -*- coding: utf-8 -*-
# FILE: config.py
# Cấu hình chuẩn Logic V2.2 (Hỗ trợ Presets & Fixed Lot)

# === 1. KẾT NỐI & HỆ THỐNG ===
SYMBOL = "BTCUSD"           # Cặp tiền trade (Ví dụ: BTCUSDm, XAUUSD...)
MAGIC_NUMBER = 8888         # Định danh lệnh của Bot
LOOP_SLEEP_SECONDS = 1      # Tốc độ cập nhật (giây)

# === 2. QUẢN LÝ VỐN (QUAN TRỌNG) ===
# Mode: "FIXED" (Đi lot cố định) hoặc "DYNAMIC" (Tính lot theo % rủi ro)
LOT_SIZE_MODE = "FIXED"     

# Cấu hình cho mode FIXED
FIXED_LOT_VOLUME = 0.01     # Nếu mode FIXED: Luôn đi 0.01 lot

# Cấu hình cho mode DYNAMIC (Logic V2 gốc)
RISK_PER_TRADE_PERCENT = 0.30  # Mất tối đa 0.3% vốn/lệnh
RISK_PER_TRADE_USD = 10.0      # (Dự phòng) Mất tối đa 10$/lệnh nếu tính theo USD

# === 3. KỶ LUẬT & KILL SWITCH ===
MAX_DAILY_LOSS_PERCENT = 1.5   # Lỗ quá 1.5% ngày -> KHÓA APP
MAX_LOSING_STREAK = 3          # Thua 3 lệnh thông -> KHÓA APP
MAX_TRADES_PER_DAY = 15        # Giới hạn số lệnh/ngày

# === 4. CÁC GÓI CHIẾN LƯỢC (PRESETS) ===
# Định nghĩa các kiểu đánh để chọn nhanh trên UI
DEFAULT_PRESET = "SCALPING"

PRESETS = {
    "SCALPING": {
        "DESC": "Nhanh, SL ngắn, Chốt sớm",
        "SL_PERCENT": 0.4,         # SL các entry 0.4%
        "TP_RR_RATIO": 1.5,        # TP = 1.5 lần SL (R:R 1:1.5)
        "BE_TRIGGER_RR": 0.8,      # Lãi 0.8R -> Dời SL về Entry (Hòa vốn)
        "TRAILING_STEP_RR": 0.5,   # (MỚI) Khi giá chạy thêm 0.5R thì dời SL theo
    },
    "SAFE": {
        "DESC": "An toàn, SL xa hơn, Giữ vốn",
        "SL_PERCENT": 0.8,         # SL rộng hơn (0.8%) để tránh quét
        "TP_RR_RATIO": 1.2,        # TP ngắn hơn để dễ khớp
        "BE_TRIGGER_RR": 0.6,      # Dời hòa vốn cực sớm
        "TRAILING_STEP_RR": 0.3,   # Trailing chặt để khóa lãi
    },
    "BREAKOUT": {
        "DESC": "Săn trend lớn, Trailing dài",
        "SL_PERCENT": 1.0,         # SL rất rộng
        "TP_RR_RATIO": 3.0,        # Ăn dày (R:R 1:3)
        "BE_TRIGGER_RR": 1.2,      # Chỉ dời hòa vốn khi lãi đã khá
        "TRAILING_STEP_RR": 1.0,   # Bước nhảy lớn để gồng lời
    }
}

# === 5. GIỚI HẠN SÀN (EXNESS/MT5) ===
MIN_LOT_SIZE = 0.01        # Lot tối thiểu sàn cho phép
MAX_LOT_SIZE = 200.0       # Lot tối đa
LOT_STEP = 0.01            # Bước nhảy lot
MAX_RISK_ALLOWED = 2.0     # Safety: Không bao giờ cho phép tính ra risk > 2%