# -*- coding: utf-8 -*-
# FILE: config.py

# === 1. KẾT NỐI & HỆ THỐNG ===
# Danh sách các đồng coin muốn trade (Hiện trên Menu)
COIN_LIST = [
    "BTCUSD", 
    "ETHUSD"
]
DEFAULT_SYMBOL = "ETHUSD"      # Coin mặc định khi mở App
SYMBOL = DEFAULT_SYMBOL        # Biến nội bộ (Bot tự dùng, không cần sửa)

MAGIC_NUMBER = 8888            # Định danh lệnh của Bot
LOOP_SLEEP_SECONDS = 1         # Tốc độ cập nhật (giây)

# [NEW] CẤU HÌNH RESET NGÀY MỚI (QUAN TRỌNG)
# Giờ bắt đầu ngày mới (0-23). Ví dụ: 6 nghĩa là 6:00 sáng mới reset PnL và Rule.
RESET_HOUR = 6

# === CẤU HÌNH AN TOÀN (STRICT MODE - MỚI) ===
STRICT_MODE_DEFAULT = True     # Mặc định bật chế độ an toàn (True/False)
MAX_PING_MS = 150              # Ping > 150ms là báo Lag (FAIL)
MAX_SPREAD_POINTS = 150        # Spread > 150 point là báo Cao (FAIL)

# === 2. QUẢN LÝ VỐN (QUAN TRỌNG) ===
LOT_SIZE_MODE = "DYNAMIC"      # Mode: "FIXED" (Đi lot cố định) hoặc "DYNAMIC" (Tính lot theo % rủi ro)

# [NEW] CẤU HÌNH PHÍ COMMISSION (Dùng để tính điểm hoà vốn Break-Even chuẩn xác)
# Đơn vị: USD trên mỗi 1 Lot (tính cả 2 chiều mở/đóng)
COMMISSION_RATES = {
    #"BTCUSD": 16.0,
    #"ETHUSD": 1.25
    "BTCUSD": 0.0,
    "ETHUSD": 0.0
}

# Cấu hình cho mode FIXED
FIXED_LOT_VOLUME = 0.01        # Nếu mode FIXED: Luôn đi 0.01 lot

# Cấu hình cho mode DYNAMIC (Logic V2 gốc)
RISK_PER_TRADE_PERCENT = 0.30  # Mất tối đa 0.3% vốn/lệnh
RISK_PER_TRADE_USD = 10.0      # (Dự phòng) Mất tối đa 10$/lệnh nếu tính theo USD

# === 3. KỶ LUẬT & KILL SWITCH ===
MAX_DAILY_LOSS_PERCENT = 1.5   # Lỗ quá 1.5% ngày -> KHÓA APP

# [NEW] CHẾ ĐỘ ĐẾM LỆNH THUA (LINH HOẠT)
# "STREAK": Thua 3 lệnh LIÊN TIẾP mới tính (Thắng 1 lệnh ở giữa sẽ reset về 0).
# "TOTAL":  Tổng số lệnh thua trong ngày (Thắng không reset).
LOSS_COUNT_MODE = "TOTAL"      # Boss sửa thành "STREAK" hoặc "TOTAL" tại đây

MAX_LOSING_STREAK = 3          # Giới hạn số lệnh thua (Áp dụng theo mode đã chọn ở trên)
MAX_TRADES_PER_DAY = 15        # Giới hạn số lệnh/ngày
MAX_OPEN_POSITIONS = 2         # Giới hạn số lệnh mở cùng lúc (Để 2 cho linh hoạt)

# === 4. MANUAL TRADE (MỚI - NÂNG CẤP) ===
# Cấu hình hỗ trợ việc nhập lệnh bằng tay từ UI và Force Trade
MANUAL_CONFIG = {
    "BYPASS_CHECKLIST": False, # True: Cho phép vào lệnh kể cả khi vi phạm Checklist (Force Trade)
    "DEFAULT_LOT": 0.0,        # 0.0 nghĩa là để trống (Auto tính), >0 là giá trị mặc định khi mở app
}

# === 5. TSL ADVANCED CONFIG (MỚI - LOGIC TSL 3 LỚP) ===
TSL_CONFIG = {
    # Chiến thuật chọn giá SL: 
    # "BEST_PRICE": So sánh 3 Rule bên dưới, giá nào giữ lãi tốt nhất thì lấy (Mặc định - Khuyên dùng)
    # "PRIORITY_PNL": Ưu tiên chạy theo PnL (Lớp 2)
    # "PRIORITY_BE": Ưu tiên chạy theo Break-Even (Lớp 1)
    "STRATEGY": "BEST_PRICE", 

    # --- RULE 1: BREAK-EVEN (Hoà Vốn) ---
    "BE_ACTIVE": True,         # Bật/Tắt Rule này
    # "HARD":  Dời về Entry (Chấp nhận lỗ phí Spread/Comm - An toàn vốn cứng)
    # "SMART": Dời về Entry + Fees (Bảo toàn vốn tuyệt đối, Net PnL = 0)
    # "SOFT":  Dời về Entry - Fees (Chấp nhận lỗ phí, chỉ cần cắt được lệnh - Như Boss yêu cầu)
    "BE_MODE": "SOFT", 
    "BE_OFFSET_RR": 0.8,       # Khi giá chạy được 0.8R thì kích hoạt BE

    # --- RULE 2: PNL PROTECTION (% Balance) ---
    "PNL_ACTIVE": True,
    # Danh sách các mốc: [Mốc % Lãi, Giữ lại % Lãi]
    # Logic: Lãi đạt bao nhiêu % tài khoản thì khoá lại bấy nhiêu
    "PNL_LEVELS": [
        [0.5, 0.1],  # Lãi 0.5% vốn -> Dời SL để chắc chắn lãi 0.1%
        [1.0, 0.5],  # Lãi 1.0% vốn -> Dời SL để chắc chắn lãi 0.5%
        [2.0, 1.2]   # Lãi 2.0% vốn -> Dời SL để chắc chắn lãi 1.2%
    ],

    # --- RULE 3: STEP R (Gồng Trend - Cũ) ---
    "STEP_ACTIVE": True,
    "STEP_SIZE_RR": 0.5        # Mỗi khi giá chạy thêm 0.5R thì dời SL lên
}

# === 6. CÁC GÓI CHIẾN LƯỢC (PRESETS) ===
DEFAULT_PRESET = "SCALPING"

PRESETS = {
    "SCALPING": {
        "DESC": "Nhanh, SL ngắn, Chốt sớm",
        "SL_PERCENT": 0.4,         # SL các entry 0.4%
        "TP_RR_RATIO": 1.5,        # TP = 1.5 lần SL (R:R 1:1.5)
        "BE_TRIGGER_RR": 0.8,      # (Sẽ dùng Logic TSL_CONFIG ở trên để thay thế nếu active)
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

# === 7. GIỚI HẠN SÀN (EXNESS/MT5) ===
MIN_LOT_SIZE = 0.01        # Lot tối thiểu sàn cho phép
MAX_LOT_SIZE = 200.0       # Lot tối đa
LOT_STEP = 0.01            # Bước nhảy lot
MAX_RISK_ALLOWED = 2.0     # Safety: Không bao giờ cho phép tính ra risk > 2%