# -*- coding: utf-8 -*-
# FILE: config.py

# === 1. KẾT NỐI & HỆ THỐNG ===
# Danh sách các đồng coin muốn trade (Hiện trên Menu)
COIN_LIST = [
    "BTCUSD", 
    "ETHUSD"
]
DEFAULT_SYMBOL = "ETHUSD"      # Coin mặc định khi mở App
SYMBOL = DEFAULT_SYMBOL         # Biến nội bộ (Bot tự dùng, không cần sửa)

MAGIC_NUMBER = 8888             # Định danh lệnh của Bot
LOOP_SLEEP_SECONDS = 1          # Tốc độ cập nhật (giây)

# [NEW] CẤU HÌNH RESET NGÀY MỚI (QUAN TRỌNG)
# Giờ bắt đầu ngày mới (0-23). Ví dụ: 6 nghĩa là 6:00 sáng mới reset PnL và Rule.
RESET_HOUR = 6

# === CẤU HÌNH AN TOÀN (STRICT MODE - MỚI) ===
STRICT_MODE_DEFAULT = True      # Mặc định bật chế độ an toàn (True/False)
MAX_PING_MS = 150               # Ping > 150ms là báo Lag (FAIL)
MAX_SPREAD_POINTS = 150          # Spread > 50 point là báo Cao (FAIL)

# === 2. QUẢN LÝ VỐN (QUAN TRỌNG) ===
LOT_SIZE_MODE = "DYNAMIC"       # Mode: "FIXED" (Đi lot cố định) hoặc "DYNAMIC" (Tính lot theo % rủi ro)

# [NEW] CẤU HÌNH PHÍ COMMISSION (Dùng để tính dự kiến)
# Đơn vị: USD trên mỗi 1 Lot (tính cả 2 chiều mở/đóng)
# Bot sẽ dùng số này cộng với Spread thực tế để hiển thị tổng phí dự kiến.
COMMISSION_RATES = {
    "BTCUSD": 16.0,
    "ETHUSD": 1.25
}

# Cấu hình cho mode FIXED
FIXED_LOT_VOLUME = 0.01         # Nếu mode FIXED: Luôn đi 0.01 lot

# Cấu hình cho mode DYNAMIC (Logic V2 gốc)
RISK_PER_TRADE_PERCENT = 0.30   # Mất tối đa 0.3% vốn/lệnh
RISK_PER_TRADE_USD = 10.0       # (Dự phòng) Mất tối đa 10$/lệnh nếu tính theo USD

# === 3. KỶ LUẬT & KILL SWITCH ===
MAX_DAILY_LOSS_PERCENT = 1.5    # Lỗ quá 1.5% ngày -> KHÓA APP
MAX_LOSING_STREAK = 3           # Thua 3 lệnh thông -> KHÓA APP
MAX_TRADES_PER_DAY = 15         # Giới hạn số lệnh/ngày
MAX_OPEN_POSITIONS = 2          # Giới hạn số lệnh mở cùng lúc

# === 4. CÁC GÓI CHIẾN LƯỢC (PRESETS) ===
DEFAULT_PRESET = "SCALPING"

PRESETS = {
    "SCALPING": {
        "DESC": "Nhanh, SL ngắn, Chốt sớm",
        "SL_PERCENT": 0.4,         # SL các entry 0.4%
        "TP_RR_RATIO": 1.5,        # TP = 1.5 lần SL (R:R 1:1.5)
        "BE_TRIGGER_RR": 0.8,      # Lãi 0.8R -> Dời SL về Entry (Hòa vốn)
        "TRAILING_STEP_RR": 0.5,   # Khi giá chạy thêm 0.5R thì dời SL theo
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