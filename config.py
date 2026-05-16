class Config:
    # Bot settings
    BOT_TOKEN = "8088872046:AAEAspAH2nI53fuMG2E7z4RKP787DmkX848"
    ADMIN_ID = 8088872046
    ADMIN_USERNAME = "admin"  # @username without @
    
    # Wallet
    TON_WALLET = "YOUR_TON_WALLET_ADDRESS_HERE"  # O'z TON manzilingizni kiriting
    
    # Game settings
    BASE_WIN_RATE = 60.0      # Boshlang'ich yutish foizi (%)
    WIN_RATE_DECREASE = 3.0   # Har 1000 foydalanuvchida kamayish (%)
    MIN_WIN_RATE = 20.0       # Minimal yutish foizi (%)
    DEFAULT_COMMISSION = 5.0  # Standart komissiya (%)
    
    # Limits
    MIN_DEPOSIT_TON = 0.1
    MIN_DEPOSIT_STARS = 10
    MIN_WITHDRAW_TON = 0.5
    MIN_WITHDRAW_STARS = 50
    
    # Referral
    REF_BONUS_TON = 0.01
    REF_DEPOSIT_BONUS = 0.05  # When referral makes first deposit
