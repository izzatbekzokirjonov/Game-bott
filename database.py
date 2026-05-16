import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict

class Database:
    def __init__(self, db_path: str = "gamebot.db"):
        self.db_path = db_path
    
    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    lang TEXT DEFAULT 'uz',
                    stars_balance REAL DEFAULT 0,
                    ton_balance REAL DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_won REAL DEFAULT 0,
                    referral_count INTEGER DEFAULT 0,
                    ref_earned REAL DEFAULT 0,
                    referred_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_active TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            """)
            
            # Deposits table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Withdrawals table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    address TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Games history
            await db.execute("""
                CREATE TABLE IF NOT EXISTS game_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_type TEXT,
                    bet_amount REAL,
                    currency TEXT,
                    result TEXT,
                    win_amount REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Settings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Commission revenue
            await db.execute("""
                CREATE TABLE IF NOT EXISTS revenue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL,
                    currency TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # PVP rooms
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT,
                    creator_id INTEGER,
                    bet_amount REAL,
                    currency TEXT,
                    players_count INTEGER DEFAULT 1,
                    max_players INTEGER,
                    status TEXT DEFAULT 'waiting',
                    winner_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # PVP participants
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_players (
                    room_id INTEGER,
                    user_id INTEGER,
                    score REAL DEFAULT 0,
                    PRIMARY KEY (room_id, user_id)
                )
            """)
            
            # Default settings
            await db.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES 
                ('commission', '5'),
                ('base_win_rate', '60'),
                ('ton_wallet', 'YOUR_TON_WALLET_HERE'),
                ('maintenance', '0')
            """)
            
            await db.commit()
    
    async def register_user(self, user_id: int, username: str, first_name: str, 
                           ref_id: Optional[int] = None) -> bool:
        """Returns True if new user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            existing = await cursor.fetchone()
            
            if existing:
                await db.execute(
                    "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return False
            
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, referred_by) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, username, first_name, ref_id)
            )
            
            # Referral bonus
            if ref_id and ref_id != user_id:
                cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (ref_id,))
                ref_exists = await cursor.fetchone()
                if ref_exists:
                    await db.execute(
                        """UPDATE users SET referral_count = referral_count + 1, 
                           ref_earned = ref_earned + 0.01,
                           ton_balance = ton_balance + 0.01 WHERE user_id = ?""",
                        (ref_id,)
                    )
            
            await db.commit()
            return True
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def update_balance(self, user_id: int, currency: str, amount: float):
        col = f"{currency}_balance"
        if col not in ["stars_balance", "ton_balance"]:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()
    
    async def increment_games(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET total_games = total_games + 1, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
    
    async def increment_wins(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET wins = wins + 1, total_won = total_won + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()
    
    async def increment_losses(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET losses = losses + 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
    
    async def get_commission(self) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'commission'")
            row = await cursor.fetchone()
            return float(row[0]) if row else 5.0
    
    async def set_commission(self, value: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE settings SET value = ? WHERE key = 'commission'", (str(value),))
            await db.commit()
    
    async def get_base_win_rate(self) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'base_win_rate'")
            row = await cursor.fetchone()
            return float(row[0]) if row else 60.0
    
    async def set_base_win_rate(self, value: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE settings SET value = ? WHERE key = 'base_win_rate'", (str(value),))
            await db.commit()
    
    async def add_commission_revenue(self, amount: float, currency: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO revenue (amount, currency) VALUES (?, ?)",
                (amount, currency)
            )
            await db.commit()
    
    async def get_total_users(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def get_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-24 hours')"
            )
            stats['active_24h'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM game_history")
            stats['total_games'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE status = 'approved'")
            stats['total_deposit'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE status = 'approved'")
            stats['total_withdrawn'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM revenue")
            stats['total_revenue'] = (await cursor.fetchone())[0]
            
            return stats
    
    async def get_detailed_stats(self) -> Dict:
        stats = await self.get_stats()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-24 hours')"
            )
            stats['today_users'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-7 days')"
            )
            stats['active_7d'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM game_history WHERE created_at > datetime('now', '-24 hours')"
            )
            stats['today_games'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM game_history WHERE result = 'win'")
            stats['total_wins'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM game_history WHERE result = 'lose'")
            stats['total_losses'] = (await cursor.fetchone())[0]
        
        return stats
    
    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users ORDER BY total_won DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def create_deposit(self, user_id: int, amount: float, currency: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO deposits (user_id, amount, currency) VALUES (?, ?, ?)",
                (user_id, amount, currency)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def create_withdrawal(self, user_id: int, amount: float, 
                                currency: str, address: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO withdrawals (user_id, amount, currency, address) VALUES (?, ?, ?, ?)",
                (user_id, amount, currency, address)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_pending_withdrawals(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def get_withdrawal(self, withdraw_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM withdrawals WHERE id = ?", (withdraw_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def approve_withdrawal(self, withdraw_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE withdrawals SET status = 'approved' WHERE id = ?",
                (withdraw_id,)
            )
            await db.commit()
    
    async def get_all_user_ids(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
    
    async def set_lang(self, user_id: int, lang: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
            await db.commit()
    
    async def get_active_pvp_rooms(self, mode: str) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM pvp_rooms WHERE mode = ? AND status = 'waiting' ORDER BY created_at DESC LIMIT 10",
                (mode,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def ban_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
    
    async def add_balance_admin(self, user_id: int, currency: str, amount: float):
        await self.update_balance(user_id, currency, amount)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO deposits (user_id, amount, currency, status) VALUES (?, ?, ?, 'approved')",
                (user_id, amount, currency)
            )
            await db.commit()

db = Database()
