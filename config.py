# -*- coding: utf-8 -*-
# FILE: config.py
# V8.1: Added BE_OFFSET_POINTS for Advanced Break-Even

# === 1. KẾT NỐI & HỆ THỐNG ===
COIN_LIST = [
    "BTCUSD", 
    "ETHUSD",
    "XAUUSD"
]
DEFAULT_SYMBOL = "ETHUSD"      
SYMBOL = DEFAULT_SYMBOL        

MAGIC_NUMBER = 8888            
LOOP_SLEEP_SECONDS = 1         

# Cấu hình Reset ngày mới (Giờ Server/Máy tính)
RESET_HOUR = 6

# === 1.1 CẤU HÌNH LOẠI TÀI KHOẢN ===
ACCOUNT_TYPES_CONFIG = {
    "STANDARD": {
        "DESC": "Spread cao, Không phí Comm",
        "COMMISSION_PER_LOT": 0.0
    },
    "PRO": {
        "DESC": "Spread thấp, Không phí Comm",
        "COMMISSION_PER_LOT": 0.0
    },
    "RAW": {
        "DESC": "Spread cực thấp, Phí Comm cố định",
        "COMMISSION_PER_LOT": 7.0  
    },
    "ZERO": {
        "DESC": "Spread bằng 0, Phí Comm cao",
        "COMMISSION_PER_LOT": 7.0  
    }
}
DEFAULT_ACCOUNT_TYPE = "STANDARD"

# === CẤU HÌNH AN TOÀN ===
STRICT_MODE_DEFAULT = True     
MAX_PING_MS = 150              
MAX_SPREAD_POINTS = 150        

# === 2. QUẢN LÝ VỐN ===
LOT_SIZE_MODE = "DYNAMIC"      # "FIXED" hoặc "DYNAMIC"

COMMISSION_RATES = {
    "BTCUSD": 16.5,  
    "ETHUSD": 1.25   
}

FIXED_LOT_VOLUME = 0.01        
RISK_PER_TRADE_PERCENT = 0.30  
RISK_PER_TRADE_USD = 10.0      

# === 3. KỶ LUẬT & KILL SWITCH ===
MAX_DAILY_LOSS_PERCENT = 1.5   
LOSS_COUNT_MODE = "TOTAL"      # "STREAK" hoặc "TOTAL"
MAX_LOSING_STREAK = 3          
MAX_TRADES_PER_DAY = 15        
MAX_OPEN_POSITIONS = 2         

# === 4. MANUAL TRADE ===
MANUAL_CONFIG = {
    "BYPASS_CHECKLIST": False, 
    "DEFAULT_LOT": 0.0,        
}

# === 5. TSL ADVANCED CONFIG (V8.1) ===
TSL_CONFIG = {
    # --- RULE 1: BREAK-EVEN (Hoà Vốn - Chỉ nhảy 1 lần) ---
    # "SOFT":  Dời về Entry - Fees (Chấp nhận lỗ phí để thoát nhanh)
    # "SMART": Dời về Entry + Fees (Hoà cả phí)
    "BE_MODE": "SOFT", 
    "BE_OFFSET_RR": 0.8,       # Khi lãi 0.8R -> Kích hoạt BE
    "BE_OFFSET_POINTS": 0,     # (NEW V8.1) Cộng thêm points khi dời BE (Ví dụ: +10 points để an toàn hơn)

    # --- RULE 2: PNL LOCK (% Lãi -> % Lock) ---
    "PNL_LEVELS": [
        [0.5, 0.1],  # Lãi 0.5% vốn -> Lock 0.1%
        [1.0, 0.5],  # Lãi 1.0% vốn -> Lock 0.5%
        [2.0, 1.2]   # Lãi 2.0% vốn -> Lock 1.2%
    ],

    # --- RULE 3: STEP R (Nuôi Lệnh - Nhảy liên tục) ---
    # Công thức: SL = Entry + (Số Bước * 1R * Ratio)
    "STEP_R_SIZE": 1.0,        # Bước nhảy (Ví dụ: 1R)
    "STEP_R_RATIO": 0.8        # Tỷ lệ giữ (Ví dụ: 0.8 -> Giữ lại 80% lợi nhuận của bước đó)
}

# === 6. CÁC GÓI CHIẾN LƯỢC (PRESETS) ===
DEFAULT_PRESET = "SCALPING"

PRESETS = {
    "SCALPING": {
        "DESC": "Nhanh, SL ngắn, Chốt sớm",
        "SL_PERCENT": 0.4,         
        "TP_RR_RATIO": 1.5,        
    },
    "SAFE": {
        "DESC": "An toàn, SL xa hơn",
        "SL_PERCENT": 0.8,         
        "TP_RR_RATIO": 1.2,        
    },
    "BREAKOUT": {
        "DESC": "Săn trend lớn",
        "SL_PERCENT": 1.0,         
        "TP_RR_RATIO": 3.0,        
    }
}

# === 7. GIỚI HẠN SÀN ===
MIN_LOT_SIZE = 0.01        
MAX_LOT_SIZE = 200.0       
LOT_STEP = 0.01            
MAX_RISK_ALLOWED = 2.0