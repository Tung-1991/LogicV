# -*- coding: utf-8 -*-
# FILE: config.py
# V3.1.0: Config cleaned up & Added Risk per Preset

# === 1. KẾT NỐI & HỆ THỐNG ===
COIN_LIST = ["BTCUSD", "ETHUSD", "XAUUSD"] # Danh sách coin hiển thị trên UI
DEFAULT_SYMBOL = "ETHUSD"        # Coin mặc định khi mở bot
MAGIC_NUMBER = 8888              # ID nhận diện lệnh của Bot
LOOP_SLEEP_SECONDS = 1           # Tốc độ làm mới vòng lặp (giây)
RESET_HOUR = 6                   # Giờ bắt đầu ngày mới (6h sáng)

# === 1.1 LOẠI TÀI KHOẢN (Tính phí Commission) ===
ACCOUNT_TYPES_CONFIG = {
    "STANDARD": {"DESC": "No Comm", "COMMISSION_PER_LOT": 0.0},
    "PRO":      {"DESC": "No Comm", "COMMISSION_PER_LOT": 0.0},
    "RAW":      {"DESC": "Comm Fix", "COMMISSION_PER_LOT": 7.0},
    "ZERO":     {"DESC": "Comm High", "COMMISSION_PER_LOT": 7.0}
}
DEFAULT_ACCOUNT_TYPE = "STANDARD"

# === 2. AN TOÀN & KẾT NỐI ===
STRICT_MODE_DEFAULT = True       # Mặc định bật chế độ kiểm tra nghiêm ngặt
MAX_PING_MS = 150                # Ping tối đa cho phép (ms)
MAX_SPREAD_POINTS = 150          # Spread tối đa cho phép (Points)

# === 3. QUẢN LÝ VỐN (GLOBAL) ===
LOT_SIZE_MODE = "DYNAMIC"        # "FIXED" (Lot cố định) hoặc "DYNAMIC" (Tính theo Risk)
COMMISSION_RATES = {"BTCUSD": 16.5, "ETHUSD": 1.25} # Phí Comm riêng cho từng Coin (nếu có)
FIXED_LOT_VOLUME = 0.01          # Khối lượng nếu dùng chế độ FIXED
RISK_PER_TRADE_PERCENT = 0.30    # % Rủi ro mặc định (Fallback nếu Preset ko có)
RISK_PER_TRADE_USD = 10.0        # $ Rủi ro tối đa (Dự phòng an toàn)

# === 4. KỶ LUẬT & KILL SWITCH ===
MAX_DAILY_LOSS_PERCENT = 1.5     # % Lỗ tối đa/ngày -> Dừng bot
LOSS_COUNT_MODE = "TOTAL"        # Cách đếm: "TOTAL" (Tổng thua) hoặc "STREAK" (Thua liên tiếp)
MAX_LOSING_STREAK = 3            # Số lệnh thua cho phép (theo mode trên)
MAX_TRADES_PER_DAY = 15          # Tổng số lệnh tối đa/ngày
MAX_OPEN_POSITIONS = 2           # Số lệnh được chạy cùng lúc

# === 5. CẤU HÌNH MANUAL ===
MANUAL_CONFIG = {
    "BYPASS_CHECKLIST": False,   # Mặc định tích ô Force hay không
    "DEFAULT_LOT": 0.0,          # Lot mặc định khi mở app (0 = Auto)
}

# === 6. CHIẾN THUẬT TRAILING STOP (TSL) ===
TSL_CONFIG = {
    # --- RULE 1: BREAK-EVEN (Hoà Vốn) ---
    "BE_MODE": "SOFT",           # "SOFT" (Entry-Fee) hoặc "SMART" (Entry+Fee)
    "BE_OFFSET_RR": 0.8,         # Lãi 0.8R -> Kích hoạt BE
    "BE_OFFSET_POINTS": 0,       # Cộng thêm point an toàn khi dời BE

    # --- RULE 2: PNL LOCK (% Lãi -> % Lock) ---
    "PNL_LEVELS": [
        [0.5, 0.1],              # Lãi 0.5% vốn -> Lock 0.1% vốn
        [1.0, 0.5],              # Lãi 1.0% vốn -> Lock 0.5% vốn
        [2.0, 1.2]               # Lãi 2.0% vốn -> Lock 1.2% vốn
    ],

    # --- RULE 3: STEP R (Nuôi Lệnh) ---
    "STEP_R_SIZE": 1.0,          # Bước nhảy (Ví dụ: mỗi 1R)
    "STEP_R_RATIO": 0.8          # Tỷ lệ giữ lợi nhuận mỗi bước (0.8 = giữ 80%)
}

# === 7. GÓI CÀI ĐẶT (PRESETS) ===
DEFAULT_PRESET = "SCALPING"

PRESETS = {
    "SCALPING": {
        "DESC": "Nhanh, SL ngắn",
        "SL_PERCENT": 0.4,       # Khoảng cách SL (% giá)
        "TP_RR_RATIO": 1.5,      # Tỷ lệ Reward/Risk (TP)
        "RISK_PERCENT": 0.3      # % Vốn rủi ro cho lệnh Scalp
    },
    "SAFE": {
        "DESC": "An toàn",
        "SL_PERCENT": 0.8,       # SL xa hơn
        "TP_RR_RATIO": 1.2,      # TP ngắn hơn
        "RISK_PERCENT": 0.2      # Rủi ro thấp hơn
    },
    "BREAKOUT": {
        "DESC": "Săn trend lớn",
        "SL_PERCENT": 1.0,       # SL rất xa để tránh quét
        "TP_RR_RATIO": 3.0,      # Ăn dày (3R)
        "RISK_PERCENT": 0.5      # Chấp nhận rủi ro cao
    }
}

# === 8. GIỚI HẠN SÀN ===
MIN_LOT_SIZE = 0.01              # Lot tối thiểu sàn cho phép
MAX_LOT_SIZE = 200.0             # Lot tối đa sàn cho phép
LOT_STEP = 0.01                  # Bước nhảy lot
MAX_RISK_ALLOWED = 2.0           # Giới hạn cứng % rủi ro (để tránh nhập nhầm số lớn)