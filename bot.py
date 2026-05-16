import asyncio
import logging
import random
import json
import time
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from database import db
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== STATES ====================
class DepositState(StatesGroup):
    waiting_amount = State()
    waiting_currency = State()

class WithdrawState(StatesGroup):
    waiting_amount = State()
    waiting_address = State()

class AdminState(StatesGroup):
    broadcast = State()
    set_commission = State()
    set_win_rate = State()
    add_balance = State()
    ban_user = State()

# ==================== PRICE FETCHER ====================
async def get_ton_price():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                return data.get("the-open-network", {}).get("usd", 3.5)
    except:
        return 3.5

async def get_stars_price():
    # Telegram Stars: 1 Star ≈ $0.013 (Telegram official rate)
    return 0.013

# ==================== WIN RATE CALCULATOR ====================
def calculate_win_rate(user_count: int, base_rate: float = 60.0) -> float:
    """Win rate decreases by 3% per 1000 users"""
    decrease = (user_count // 1000) * 3.0
    min_rate = 20.0  # Minimum 20% win rate
    return max(min_rate, base_rate - decrease)

# ==================== KEYBOARDS ====================
def main_menu_keyboard(lang="uz"):
    texts = {
        "uz": {"games": "🎮 O'yinlar", "balance": "💰 Balans", "deposit": "➕ To'ldirish", 
               "withdraw": "💸 Chiqarish", "profile": "👤 Profil", "referral": "👥 Referal",
               "leaderboard": "🏆 Reyting", "support": "💬 Yordam"},
        "ru": {"games": "🎮 Игры", "balance": "💰 Баланс", "deposit": "➕ Пополнить",
               "withdraw": "💸 Вывод", "profile": "👤 Профиль", "referral": "👥 Реферал",
               "leaderboard": "🏆 Рейтинг", "support": "💬 Поддержка"},
        "en": {"games": "🎮 Games", "balance": "💰 Balance", "deposit": "➕ Deposit",
               "withdraw": "💸 Withdraw", "profile": "👤 Profile", "referral": "👥 Referral",
               "leaderboard": "🏆 Leaderboard", "support": "💬 Support"}
    }
    t = texts.get(lang, texts["uz"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["games"], callback_data="games_menu"),
         InlineKeyboardButton(text=t["balance"], callback_data="my_balance")],
        [InlineKeyboardButton(text=t["deposit"], callback_data="deposit_menu"),
         InlineKeyboardButton(text=t["withdraw"], callback_data="withdraw_menu")],
        [InlineKeyboardButton(text=t["profile"], callback_data="my_profile"),
         InlineKeyboardButton(text=t["referral"], callback_data="referral_info")],
        [InlineKeyboardButton(text=t["leaderboard"], callback_data="leaderboard"),
         InlineKeyboardButton(text=t["support"], callback_data="support")]
    ])
    return kb

def games_menu_keyboard(lang="uz"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 777 Slot", callback_data="game_777"),
         InlineKeyboardButton(text="🎯 Mergan", callback_data="game_mergan")],
        [InlineKeyboardButton(text="🥁 Multi Baraban", callback_data="game_baraban"),
         InlineKeyboardButton(text="💣 Mina (Skat)", callback_data="game_mina")],
        [InlineKeyboardButton(text="✈️ Aviator", callback_data="game_aviator"),
         InlineKeyboardButton(text="🎲 Dice", callback_data="game_dice")],
        [InlineKeyboardButton(text="🃏 Blackjack", callback_data="game_blackjack"),
         InlineKeyboardButton(text="🎡 Ruletka", callback_data="game_roulette")],
        [InlineKeyboardButton(text="👥 1x1 O'yin", callback_data="pvp_1v1"),
         InlineKeyboardButton(text="👥 4x4 O'yin", callback_data="pvp_4v4")],
        [InlineKeyboardButton(text="👥 10x10 O'yin", callback_data="pvp_10v10")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    return kb

def bet_keyboard(game: str, lang="uz"):
    amounts = [0.1, 0.5, 1, 5, 10, 50]
    rows = []
    for i in range(0, len(amounts), 3):
        row = [InlineKeyboardButton(text=f"⭐{a} Stars", callback_data=f"bet_{game}_{a}_stars") 
               for a in amounts[i:i+3]]
        rows.append(row)
    ton_amounts = [0.01, 0.05, 0.1, 0.5, 1, 5]
    for i in range(0, len(ton_amounts), 3):
        row = [InlineKeyboardButton(text=f"💎{a} TON", callback_data=f"bet_{game}_{a}_ton") 
               for a in ton_amounts[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="games_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def currency_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="currency_stars"),
         InlineKeyboardButton(text="💎 TON", callback_data="currency_ton")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])

def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Komissiya %", callback_data="admin_commission"),
         InlineKeyboardButton(text="🎯 Yutish %", callback_data="admin_winrate")],
        [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
         InlineKeyboardButton(text="💸 Chiqarishlar", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="➕ Balans qo'shish", callback_data="admin_add_balance"),
         InlineKeyboardButton(text="🚫 Ban qilish", callback_data="admin_ban")],
        [InlineKeyboardButton(text="📈 Daromad", callback_data="admin_revenue")]
    ])

# ==================== GAME ENGINES ====================

async def play_777(bet: float, currency: str, user_id: int) -> dict:
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    commission = await db.get_commission()
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
    weights_win = [15, 15, 15, 15, 15, 15, 10]
    weights_lose = [20, 20, 20, 20, 10, 5, 5]
    
    is_win = random.random() < (win_rate / 100)
    
    if is_win:
        sym = random.choices(symbols, weights=weights_win)[0]
        reels = [sym, sym, sym]
        multipliers = {"🍒": 2, "🍋": 2.5, "🍊": 3, "🍇": 3.5, "⭐": 5, "💎": 8, "7️⃣": 10}
        mult = multipliers.get(sym, 2)
        gross_win = bet * mult
        commission_amount = gross_win * (commission / 100)
        net_win = gross_win - commission_amount
        await db.add_commission_revenue(commission_amount, currency)
    else:
        r1 = random.choice(symbols)
        r2 = random.choice([s for s in symbols if s != r1])
        r3 = random.choice(symbols)
        reels = [r1, r2, r3]
        net_win = 0
        commission_amount = 0
    
    return {
        "reels": reels,
        "is_win": is_win,
        "net_win": net_win,
        "commission": commission_amount,
        "win_rate_used": win_rate
    }

async def play_mergan(bet: float, currency: str, user_id: int, shots: int = 3) -> dict:
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    commission = await db.get_commission()
    
    targets = []
    total_score = 0
    for i in range(shots):
        hit = random.random() < (win_rate / 100)
        score = random.randint(50, 100) if hit else random.randint(0, 30)
        targets.append({"hit": hit, "score": score})
        total_score += score
    
    max_score = shots * 100
    is_win = total_score > (max_score * 0.5)
    
    if is_win:
        mult = 1.5 + (total_score / max_score)
        gross_win = bet * mult
        commission_amount = gross_win * (commission / 100)
        net_win = gross_win - commission_amount
        await db.add_commission_revenue(commission_amount, currency)
    else:
        net_win = 0
        commission_amount = 0
    
    return {
        "targets": targets,
        "total_score": total_score,
        "is_win": is_win,
        "net_win": net_win,
        "commission": commission_amount
    }

async def play_baraban(bet: float, currency: str, user_id: int) -> dict:
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    commission = await db.get_commission()
    
    drums = []
    for i in range(5):
        value = random.randint(1, 6)
        drums.append(value)
    
    from collections import Counter
    counts = Counter(drums)
    max_count = max(counts.values())
    
    is_win = random.random() < (win_rate / 100)
    
    if is_win and max_count >= 2:
        multipliers = {2: 1.5, 3: 3, 4: 5, 5: 10}
        mult = multipliers.get(max_count, 1.5)
        gross_win = bet * mult
        commission_amount = gross_win * (commission / 100)
        net_win = gross_win - commission_amount
        await db.add_commission_revenue(commission_amount, currency)
    else:
        net_win = 0
        commission_amount = 0
        is_win = False
    
    drum_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}
    drum_display = [drum_emojis[d] for d in drums]
    
    return {
        "drums": drum_display,
        "counts": dict(counts),
        "is_win": is_win,
        "net_win": net_win,
        "commission": commission_amount
    }

async def play_mina(bet: float, currency: str, user_id: int, mines: int = 3) -> dict:
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    commission = await db.get_commission()
    
    grid_size = 25
    mine_positions = random.sample(range(grid_size), mines)
    safe_positions = [i for i in range(grid_size) if i not in mine_positions]
    
    is_win = random.random() < (win_rate / 100)
    
    if is_win:
        clicks = random.randint(3, min(10, len(safe_positions)))
        clicked = random.sample(safe_positions, clicks)
        mult = 1 + (clicks * mines * 0.1)
        gross_win = bet * mult
        commission_amount = gross_win * (commission / 100)
        net_win = gross_win - commission_amount
        await db.add_commission_revenue(commission_amount, currency)
    else:
        clicked = random.sample(safe_positions, 1) + [random.choice(mine_positions)]
        net_win = 0
        commission_amount = 0
        clicks = len(clicked)
    
    return {
        "mine_positions": mine_positions,
        "clicked": clicked,
        "is_win": is_win,
        "net_win": net_win,
        "commission": commission_amount,
        "mines_count": mines
    }

# ==================== HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    first_name = message.from_user.first_name or "User"
    
    # Check referral
    args = message.text.split()
    ref_id = None
    if len(args) > 1:
        try:
            ref_id = int(args[1])
        except:
            pass
    
    # Register user
    is_new = await db.register_user(user_id, username, first_name, ref_id)
    
    user = await db.get_user(user_id)
    lang = user.get("lang", "uz") if user else "uz"
    
    ton_price = await get_ton_price()
    stars_price = await get_stars_price()
    
    texts = {
        "uz": f"""🎮 *GameBot'ga xush kelibsiz!*

Salom, {first_name}! 

💰 *Joriy kurslar:*
• 💎 1 TON = ${ton_price:.2f}
• ⭐ 1 Star = ${stars_price:.3f}

🎯 *Mavjud o'yinlar:*
• 🎰 777 Slot
• 🎯 Mergan
• 🥁 Multi Baraban  
• 💣 Mina (Skat)
• ✈️ Aviator
• 🎲 Dice
• 🃏 Blackjack
• 🎡 Ruletka
• 👥 PvP (1x1, 4x4, 10x10)

{"🎁 Referal uchun bonus qo'shildi!" if is_new and ref_id else ""}

Boshlash uchun menu dan tanlang 👇""",
        "ru": f"""🎮 *Добро пожаловать в GameBot!*

Привет, {first_name}!

💰 *Текущие курсы:*
• 💎 1 TON = ${ton_price:.2f}
• ⭐ 1 Star = ${stars_price:.3f}

Выберите из меню 👇""",
        "en": f"""🎮 *Welcome to GameBot!*

Hello, {first_name}!

💰 *Current rates:*
• 💎 1 TON = ${ton_price:.2f}
• ⭐ 1 Star = ${stars_price:.3f}

Choose from menu 👇"""
    }
    
    await message.answer(texts.get(lang, texts["uz"]), 
                        reply_markup=main_menu_keyboard(lang),
                        parse_mode="Markdown")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    stats = await db.get_stats()
    commission = await db.get_commission()
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    
    text = f"""👑 *ADMIN PANEL*

📊 *Statistika:*
• 👥 Jami foydalanuvchilar: {stats['total_users']}
• 🟢 Faol (24h): {stats['active_24h']}
• 💰 Jami depozit: {stats['total_deposit']:.2f}
• 💸 Jami chiqarilgan: {stats['total_withdrawn']:.2f}
• 🏆 Jami o'yinlar: {stats['total_games']}

💹 *Moliyaviy:*
• 💵 Komissiya %: {commission}%
• 📈 Jami daromad: {stats['total_revenue']:.4f} TON
• 🎯 Joriy yutish %: {win_rate:.1f}%

Boshqaruv uchun tugmalardan foydalaning 👇"""
    
    await message.answer(text, reply_markup=admin_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get("lang", "uz") if user else "uz"
    await callback.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu_keyboard(lang))

@dp.callback_query(F.data == "games_menu")
async def cb_games_menu(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get("lang", "uz") if user else "uz"
    
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    
    text = f"🎮 *O'yinlar*\n\n🎯 Joriy yutish ehtimoli: {win_rate:.1f}%\n\nO'yin tanlang:"
    await callback.message.edit_text(text, reply_markup=games_menu_keyboard(lang), parse_mode="Markdown")

@dp.callback_query(F.data == "my_balance")
async def cb_balance(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Xatolik!")
        return
    
    ton_price = await get_ton_price()
    stars_price = await get_stars_price()
    
    stars_bal = user.get("stars_balance", 0)
    ton_bal = user.get("ton_balance", 0)
    
    stars_usd = stars_bal * stars_price
    ton_usd = ton_bal * ton_price
    
    text = f"""💰 *Sizning balansingiz*

⭐ Stars: {stars_bal:.1f} (≈ ${stars_usd:.2f})
💎 TON: {ton_bal:.4f} (≈ ${ton_usd:.2f})

📊 *Statistika:*
• 🎮 Jami o'yinlar: {user.get('total_games', 0)}
• 🏆 Yutganlar: {user.get('wins', 0)}
• 💸 Yutqazganlar: {user.get('losses', 0)}
• 💵 Jami yutgan: {user.get('total_won', 0):.4f}"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ To'ldirish", callback_data="deposit_menu"),
         InlineKeyboardButton(text="💸 Chiqarish", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("game_"))
async def cb_game_select(callback: types.CallbackQuery):
    game = callback.data.replace("game_", "")
    game_names = {
        "777": "🎰 777 Slot",
        "mergan": "🎯 Mergan",
        "baraban": "🥁 Multi Baraban",
        "mina": "💣 Mina (Skat)",
        "aviator": "✈️ Aviator",
        "dice": "🎲 Dice",
        "blackjack": "🃏 Blackjack",
        "roulette": "🎡 Ruletka"
    }
    name = game_names.get(game, game)
    text = f"{name}\n\n💰 Stavka miqdorini tanlang:"
    await callback.message.edit_text(text, reply_markup=bet_keyboard(game))

@dp.callback_query(F.data.startswith("bet_"))
async def cb_place_bet(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    game = parts[1]
    amount = float(parts[2])
    currency = parts[3]  # stars or ton
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Xatolik! /start buyrug'ini yuboring")
        return
    
    bal_key = f"{currency}_balance"
    balance = user.get(bal_key, 0)
    
    if balance < amount:
        curr_name = "Stars" if currency == "stars" else "TON"
        await callback.answer(f"❌ Balans yetarli emas! Sizda {balance:.4f} {curr_name} bor", show_alert=True)
        return
    
    # Deduct bet
    await db.update_balance(user_id, currency, -amount)
    await db.increment_games(user_id)
    
    # Play game
    result = None
    if game == "777":
        result = await play_777(amount, currency, user_id)
        reels = " | ".join(result["reels"])
        status = "🎉 YUTDINGIZ!" if result["is_win"] else "😔 Yutqazdingiz"
        text = f"""🎰 *777 SLOT*

┌─────────────────┐
│  {reels}  │
└─────────────────┘

{status}
💰 Stavka: {amount} {currency.upper()}
{"🏆 Yutgan: " + f"{result['net_win']:.4f} {currency.upper()}" if result['is_win'] else ""}
"""
    elif game == "mergan":
        result = await play_mergan(amount, currency, user_id)
        targets_display = ""
        for i, t in enumerate(result["targets"]):
            emoji = "🎯" if t["hit"] else "💨"
            targets_display += f"  {emoji} Nishon {i+1}: {t['score']} ball\n"
        status = "🎉 YUTDINGIZ!" if result["is_win"] else "😔 Yutqazdingiz"
        text = f"""🎯 *MERGAN O'YINI*

{targets_display}
📊 Jami ball: {result['total_score']}/300

{status}
💰 Stavka: {amount} {currency.upper()}
{"🏆 Yutgan: " + f"{result['net_win']:.4f} {currency.upper()}" if result['is_win'] else ""}
"""
    elif game == "baraban":
        result = await play_baraban(amount, currency, user_id)
        drums = " ".join(result["drums"])
        status = "🎉 YUTDINGIZ!" if result["is_win"] else "😔 Yutqazdingiz"
        text = f"""🥁 *MULTI BARABAN*

🎰 {drums}

{status}
💰 Stavka: {amount} {currency.upper()}
{"🏆 Yutgan: " + f"{result['net_win']:.4f} {currency.upper()}" if result['is_win'] else ""}
"""
    elif game == "mina":
        result = await play_mina(amount, currency, user_id)
        status = "🎉 YUTDINGIZ!" if result["is_win"] else "💥 MINA! Yutqazdingiz"
        text = f"""💣 *MINA (SKAT)*

Minalar soni: {result['mines_count']}
Ochilgan kataklar: {len(result['clicked'])}

{status}
💰 Stavka: {amount} {currency.upper()}
{"🏆 Yutgan: " + f"{result['net_win']:.4f} {currency.upper()}" if result['is_win'] else ""}
"""
    else:
        # Generic game
        user_count = await db.get_total_users()
        win_rate = calculate_win_rate(user_count)
        commission = await db.get_commission()
        is_win = random.random() < (win_rate / 100)
        
        if is_win:
            mult = random.uniform(1.5, 3.0)
            gross = amount * mult
            comm_amount = gross * (commission / 100)
            net_win = gross - comm_amount
            await db.add_commission_revenue(comm_amount, currency)
        else:
            net_win = 0
        
        result = {"is_win": is_win, "net_win": net_win}
        status = "🎉 YUTDINGIZ!" if is_win else "😔 Yutqazdingiz"
        text = f"""🎮 *{game.upper()} O'YINI*

{status}
💰 Stavka: {amount} {currency.upper()}
{"🏆 Yutgan: " + f'{net_win:.4f} {currency.upper()}' if is_win else ""}
"""
    
    # Add winnings
    if result and result["is_win"] and result["net_win"] > 0:
        await db.update_balance(user_id, currency, result["net_win"])
        await db.increment_wins(user_id, result["net_win"])
    else:
        await db.increment_losses(user_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Qayta o'ynash", callback_data=f"game_{game}"),
         InlineKeyboardButton(text="🎮 O'yinlar", callback_data="games_menu")],
        [InlineKeyboardButton(text="💰 Balans", callback_data="my_balance")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "deposit_menu")
async def cb_deposit(callback: types.CallbackQuery):
    ton_price = await get_ton_price()
    stars_price = await get_stars_price()
    
    text = f"""➕ *Balans to'ldirish*

💰 *Joriy kurslar:*
• 💎 1 TON = ${ton_price:.2f}
• ⭐ 1 Star = ${stars_price:.3f}

Valyuta tanlang:"""
    await callback.message.edit_text(text, reply_markup=currency_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("currency_"))
async def cb_currency_select(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("currency_", "")
    await state.update_data(currency=currency)
    await state.set_state(DepositState.waiting_amount)
    
    if currency == "stars":
        text = "⭐ Stars miqdorini kiriting (min: 10 Stars):"
    else:
        text = "💎 TON miqdorini kiriting (min: 0.1 TON):"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="deposit_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.message(DepositState.waiting_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        currency = data.get("currency", "ton")
        
        if currency == "stars" and amount < 10:
            await message.answer("❌ Minimal depozit: 10 Stars")
            return
        if currency == "ton" and amount < 0.1:
            await message.answer("❌ Minimal depozit: 0.1 TON")
            return
        
        await state.clear()
        
        # Create deposit request
        deposit_id = await db.create_deposit(message.from_user.id, amount, currency)
        
        if currency == "stars":
            text = f"""⭐ *Stars orqali to'ldirish*

Miqdor: {amount} Stars
ID: #{deposit_id}

📱 To'lov qilish uchun admin bilan bog'laning:
@admin_username

Yoki quyidagi tugmani bosing:"""
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Admin bilan bog'lanish", url=f"https://t.me/{Config.ADMIN_USERNAME}")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
            ])
        else:
            text = f"""💎 *TON orqali to'ldirish*

Miqdor: {amount} TON
ID: #{deposit_id}

📍 TON manzili:
`{Config.TON_WALLET}`

⚠️ To'lov izohiga ID ni yozing: #{deposit_id}
Admin tasdiqlashidan so'ng balans qo'shiladi."""
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ To'ladim", callback_data=f"confirm_deposit_{deposit_id}")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
            ])
        
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Raqam kiriting:")

@dp.callback_query(F.data == "my_profile")
async def cb_profile(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Xatolik!")
        return
    
    total_games = user.get("total_games", 0)
    wins = user.get("wins", 0)
    losses = user.get("losses", 0)
    win_pct = (wins / total_games * 100) if total_games > 0 else 0
    
    text = f"""👤 *Profil*

🆔 ID: {callback.from_user.id}
👤 Ism: {callback.from_user.first_name}
📅 Ro'yxatdan: {user.get('created_at', 'N/A')}

💰 *Balans:*
• ⭐ Stars: {user.get('stars_balance', 0):.1f}
• 💎 TON: {user.get('ton_balance', 0):.4f}

🎮 *O'yin statistikasi:*
• Jami: {total_games}
• Yutgan: {wins} ({win_pct:.1f}%)
• Yutqazgan: {losses}
• 💰 Jami yutgan: {user.get('total_won', 0):.4f}

👥 Referal: {user.get('referral_count', 0)} kishi"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Til o'zgartirish", callback_data="change_lang")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "change_lang")
async def cb_change_lang(callback: types.CallbackQuery):
    await callback.message.edit_text("🌐 Til tanlang:", reply_markup=lang_keyboard())

@dp.callback_query(F.data.startswith("lang_"))
async def cb_set_lang(callback: types.CallbackQuery):
    lang = callback.data.replace("lang_", "")
    await db.set_lang(callback.from_user.id, lang)
    
    names = {"uz": "O'zbek", "ru": "Русский", "en": "English"}
    await callback.answer(f"✅ Til o'zgartirildi: {names.get(lang, lang)}")
    await callback.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu_keyboard(lang))

@dp.callback_query(F.data == "referral_info")
async def cb_referral(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    ref_count = user.get("referral_count", 0) if user else 0
    ref_earned = user.get("ref_earned", 0) if user else 0
    
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={callback.from_user.id}"
    
    text = f"""👥 *Referal tizimi*

🔗 Sizning havolangiz:
`{ref_link}`

📊 *Statistika:*
• 👥 Taklif qilinganlar: {ref_count}
• 💰 Referal daromad: {ref_earned:.4f} TON

💡 *Shartlar:*
• Har bir referal uchun 0.01 TON bonus
• Do'stingiz 1 TON depozit qilsa +0.05 TON"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Ulashish", 
                             url=f"https://t.me/share/url?url={ref_link}&text=🎮 GameBot - real pul bilan o'ynang!")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "leaderboard")
async def cb_leaderboard(callback: types.CallbackQuery):
    top_users = await db.get_leaderboard(10)
    
    text = "🏆 *TOP 10 O'yinchilar*\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    
    for i, user in enumerate(top_users):
        text += f"{medals[i]} {user.get('first_name', 'User')} — {user.get('total_won', 0):.4f} TON\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery):
    text = f"""💬 *Yordam markazi*

❓ Savol yoki muammo bo'lsa:
👨‍💼 Admin: @{Config.ADMIN_USERNAME}

⏰ Ish vaqti: 24/7

📋 *Ko'p so'raladigan savollar:*
• Depozit qachon tushadi? - 15 daqiqa ichida
• Chiqarish qancha vaqt oladi? - 1-24 soat
• Minimal chiqarish? - 0.5 TON / 50 Stars"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Adminga yozish", url=f"https://t.me/{Config.ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# ==================== ADMIN HANDLERS ====================

@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    stats = await db.get_detailed_stats()
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    
    text = f"""📊 *Batafsil statistika*

👥 Foydalanuvchilar:
• Jami: {stats['total_users']}
• Bugun: {stats['today_users']}
• Faol (24h): {stats['active_24h']}
• Faol (7 kun): {stats['active_7d']}

💰 Moliya:
• Depozitlar: {stats['total_deposit']:.4f} TON
• Chiqarishlar: {stats['total_withdrawn']:.4f} TON
• Daromad: {stats['total_revenue']:.4f} TON
• Balans farqi: {stats['total_deposit'] - stats['total_withdrawn']:.4f} TON

🎮 O'yinlar:
• Jami: {stats['total_games']}
• Bugun: {stats['today_games']}
• Yutganlar: {stats['total_wins']}
• Yutqazganlar: {stats['total_losses']}

🎯 Yutish %: {win_rate:.1f}%"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_commission")
async def cb_admin_commission(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    current = await db.get_commission()
    await state.set_state(AdminState.set_commission)
    
    text = f"💰 *Komissiya foizi*\n\nJoriy: {current}%\n\nYangi foizni kiriting (0-50):"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(AdminState.set_commission)
async def process_commission(message: types.Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    try:
        commission = float(message.text)
        if 0 <= commission <= 50:
            await db.set_commission(commission)
            await state.clear()
            await message.answer(f"✅ Komissiya {commission}% ga o'zgartirildi!", reply_markup=admin_keyboard())
        else:
            await message.answer("❌ 0-50 oralig'ida kiriting!")
    except ValueError:
        await message.answer("❌ Noto'g'ri format!")

@dp.callback_query(F.data == "admin_winrate")
async def cb_admin_winrate(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    user_count = await db.get_total_users()
    current_wr = calculate_win_rate(user_count)
    await state.set_state(AdminState.set_win_rate)
    
    text = f"""🎯 *Yutish foizi sozlamalari*

Joriy foydalanuvchilar: {user_count}
Joriy yutish %: {current_wr:.1f}%

Tizim: 1000 foydalanuvchiga 3% kamayadi
Bazaviy foizni kiriting (default: 60):"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(AdminState.set_win_rate)
async def process_winrate(message: types.Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    try:
        wr = float(message.text)
        if 20 <= wr <= 90:
            await db.set_base_win_rate(wr)
            await state.clear()
            await message.answer(f"✅ Bazaviy yutish foizi {wr}% ga o'zgartirildi!", reply_markup=admin_keyboard())
        else:
            await message.answer("❌ 20-90 oralig'ida kiriting!")
    except ValueError:
        await message.answer("❌ Noto'g'ri format!")

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    await state.set_state(AdminState.broadcast)
    text = "📢 *Xabar yuborish*\n\nBarcha foydalanuvchilarga yuboriladigan xabarni yozing:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(AdminState.broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    await state.clear()
    users = await db.get_all_user_ids()
    
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Yuborilmoqda... 0/{len(users)}")
    
    for i, uid in enumerate(users):
        try:
            await bot.send_message(uid, f"📢 *E'lon*\n\n{message.text}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
        
        if i % 50 == 0:
            try:
                await status_msg.edit_text(f"📤 Yuborilmoqda... {i}/{len(users)}")
            except:
                pass
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")

@dp.callback_query(F.data == "admin_withdrawals")
async def cb_admin_withdrawals(callback: types.CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    pending = await db.get_pending_withdrawals()
    
    if not pending:
        await callback.answer("Kutayotgan chiqarishlar yo'q!", show_alert=True)
        return
    
    text = f"💸 *Kutayotgan chiqarishlar: {len(pending)}*\n\n"
    buttons = []
    
    for w in pending[:5]:
        text += f"#{w['id']} | {w['amount']} {w['currency']} | {w.get('address', 'N/A')[:20]}\n"
        buttons.append([
            InlineKeyboardButton(text=f"✅ #{w['id']}", callback_data=f"approve_withdraw_{w['id']}"),
            InlineKeyboardButton(text=f"❌ #{w['id']}", callback_data=f"reject_withdraw_{w['id']}")
        ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")])
    
    await callback.message.edit_text(text, 
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                                      parse_mode="Markdown")

@dp.callback_query(F.data.startswith("approve_withdraw_"))
async def cb_approve_withdraw(callback: types.CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    withdraw_id = int(callback.data.split("_")[-1])
    withdrawal = await db.get_withdrawal(withdraw_id)
    
    if withdrawal:
        await db.approve_withdrawal(withdraw_id)
        try:
            await bot.send_message(
                withdrawal['user_id'],
                f"✅ *Chiqarishingiz tasdiqlandi!*\n\nMiqdor: {withdrawal['amount']} {withdrawal['currency']}\n\nTez orada hisobingizga tushadi.",
                parse_mode="Markdown"
            )
        except:
            pass
        await callback.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data == "back_admin")
async def cb_back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    stats = await db.get_stats()
    commission = await db.get_commission()
    user_count = await db.get_total_users()
    win_rate = calculate_win_rate(user_count)
    
    text = f"""👑 *ADMIN PANEL*

👥 Foydalanuvchilar: {stats['total_users']}
💰 Komissiya: {commission}%
🎯 Yutish %: {win_rate:.1f}%
📈 Daromad: {stats['total_revenue']:.4f} TON"""
    
    await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="Markdown")

# PVP Games
@dp.callback_query(F.data.startswith("pvp_"))
async def cb_pvp(callback: types.CallbackQuery):
    mode = callback.data.replace("pvp_", "")
    mode_names = {"1v1": "1 ga 1", "4v4": "4 ga 4", "10v10": "10 ga 10"}
    mode_players = {"1v1": 2, "4v4": 4, "10v10": 10}
    
    name = mode_names.get(mode, mode)
    players_needed = mode_players.get(mode, 2)
    
    # Check active rooms
    rooms = await db.get_active_pvp_rooms(mode)
    
    text = f"""👥 *{name} O'YINI*

Faol xonalar: {len(rooms)}

Yangi xona yaratish yoki mavjudga qo'shilish:"""
    
    buttons = []
    for room in rooms[:3]:
        players_in = room.get('players_count', 0)
        bet = room.get('bet_amount', 0)
        curr = room.get('currency', 'ton')
        buttons.append([InlineKeyboardButton(
            text=f"🚪 Xona #{room['id']} | {players_in}/{players_needed} | {bet} {curr.upper()}",
            callback_data=f"join_pvp_{room['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="➕ Yangi xona", callback_data=f"create_pvp_{mode}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="games_menu")])
    
    await callback.message.edit_text(text, 
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                                      parse_mode="Markdown")

@dp.callback_query(F.data == "withdraw_menu")
async def cb_withdraw(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    text = f"""💸 *Chiqarish*

💰 Sizning balansingiz:
• ⭐ Stars: {user.get('stars_balance', 0):.1f}
• 💎 TON: {user.get('ton_balance', 0):.4f}

Minimal chiqarish:
• Stars: 50 Stars
• TON: 0.5 TON

Valyuta tanlang:"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars chiqarish", callback_data="withdraw_stars"),
         InlineKeyboardButton(text="💎 TON chiqarish", callback_data="withdraw_ton")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# ==================== MAIN ====================
async def main():
    await db.init()
    logger.info("Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
