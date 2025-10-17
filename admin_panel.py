import asyncio
import logging
import os
import json
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from database_adapter import (
    get_all_users, get_user_by_tg_id, get_user_statistics, 
    get_user_balance, update_user_balance, deduct_user_balance,
    get_referral_stats, add_transaction, log_action,
    get_referral_rewards, update_referral_rewards
)

# .env faylini yuklash
load_dotenv()

# Bot tokenini environment variabledan olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variablesi topilmadi!")

# Admin ID larini environment variabledan olish
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Admin states
from enum import Enum

class AdminStates(Enum):
    MENU = "admin_menu"
    BROADCAST_MESSAGE = "broadcast_message"
    SEND_TO_USER = "send_to_user"
    USER_ID_INPUT = "user_id_input"
    USER_MESSAGE = "user_message"
    BALANCE_MANAGEMENT = "balance_management"
    USER_BALANCE_ID = "user_balance_id"
    BALANCE_AMOUNT = "balance_amount"
    REFERRAL_SETTINGS = "referral_settings"
    REFERRAL_REWARD = "referral_reward"
    REFERRAL_REWARD_INPUT = "referral_reward_input"

# Admin klaviaturalari
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Admin asosiy klaviaturasi"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📢 Ommaviy xabar"))
    builder.row(KeyboardButton(text="💬 Bir kishiga xabar"))
    builder.row(KeyboardButton(text="📊 Statistika"))
    builder.row(KeyboardButton(text="💰 Balans boshqarish"))
    builder.row(KeyboardButton(text="⚙️ Referral sozlamalari"))
    builder.row(KeyboardButton(text="🏠 Asosiy menyu"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Ommaviy xabar klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Oddiy matn", callback_data="broadcast_text"))
    builder.row(InlineKeyboardButton(text="🖼️ Rasm bilan", callback_data="broadcast_photo"))
    builder.row(InlineKeyboardButton(text="📄 Hujjat bilan", callback_data="broadcast_document"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin_menu"))
    return builder.as_markup()

def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Statistika klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Umumiy statistika", callback_data="stats_general"))
    builder.row(InlineKeyboardButton(text="📈 Faol foydalanuvchilar", callback_data="stats_active"))
    builder.row(InlineKeyboardButton(text="🚫 Blok qilinganlar", callback_data="stats_blocked"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin_menu"))
    return builder.as_markup()

def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Balans boshqarish klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Balans qo'shish", callback_data="balance_add"))
    builder.row(InlineKeyboardButton(text="➖ Balans ayirish", callback_data="balance_subtract"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin_menu"))
    return builder.as_markup()

def get_referral_settings_keyboard() -> InlineKeyboardMarkup:
    """Referral sozlamalari klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Taklif qilgan uchun bonus", callback_data="referral_referrer_reward"))
    builder.row(InlineKeyboardButton(text="🎁 Taklif qilingan uchun bonus", callback_data="referral_referred_reward"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin_menu"))
    return builder.as_markup()

# Admin tekshirish funksiyasi
async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id in ADMIN_IDS

# Admin panel start handler
@dp.message(Command("admin"))
async def admin_panel_start(message: types.Message, state: FSMContext):
    """Admin panel boshlash"""
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return
    
    await message.answer(
        "🔧 **Admin Panel**\n\n"
        "Quyidagi funksiyalardan birini tanlang:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.MENU)

# Ommaviy xabar yuborish
@dp.message(StateFilter(AdminStates.MENU), F.text == "📢 Ommaviy xabar")
async def broadcast_menu(message: types.Message):
    """Ommaviy xabar menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📢 **Ommaviy xabar yuborish**\n\n"
        "Qanday turdagi xabar yubormoqchisiz?",
        reply_markup=get_broadcast_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "broadcast_text")
async def broadcast_text_handler(callback: types.CallbackQuery, state: FSMContext):
    """Oddiy matn xabar yuborish"""
    await callback.answer("📝 Oddiy matn...")
    
    await callback.message.edit_text(
        "📝 **Oddiy matn xabar**\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring:",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.BROADCAST_MESSAGE)
    await state.update_data(broadcast_type="text")

@dp.callback_query(F.data == "broadcast_photo")
async def broadcast_photo_handler(callback: types.CallbackQuery, state: FSMContext):
    """Rasm bilan xabar yuborish"""
    await callback.answer("🖼️ Rasm bilan...")
    
    await callback.message.edit_text(
        "🖼️ **Rasm bilan xabar**\n\n"
        "Yubormoqchi bo'lgan rasmingizni yuboring:",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.BROADCAST_MESSAGE)
    await state.update_data(broadcast_type="photo")

@dp.callback_query(F.data == "broadcast_document")
async def broadcast_document_handler(callback: types.CallbackQuery, state: FSMContext):
    """Hujjat bilan xabar yuborish"""
    await callback.answer("📄 Hujjat bilan...")
    
    await callback.message.edit_text(
        "📄 **Hujjat bilan xabar**\n\n"
        "Yubormoqchi bo'lgan hujjatingizni yuboring:",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.BROADCAST_MESSAGE)
    await state.update_data(broadcast_type="document")

# Ommaviy xabar bekor qilish
@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Ommaviy xabar yuborishni bekor qilish"""
    if not await is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "❌ Ommaviy xabar yuborish bekor qilindi!",
        reply_markup=None
    )
    
    await callback.answer("Ommaviy xabar bekor qilindi!")
    await state.set_state(AdminStates.MENU)

@dp.message(StateFilter(AdminStates.BROADCAST_MESSAGE))
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Ommaviy xabarni qayta ishlash"""
    if not await is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    broadcast_type = data.get('broadcast_type', 'text')
    
    if broadcast_type == "text":
        # Barcha foydalanuvchilarni olish
        users = await get_all_users()
        success_count = 0
        failed_count = 0
        
        # Boshlash xabarini yuborish
        total_users = len(users)
        progress_msg = await message.answer(
            f"📢 **Ommaviy xabar yuborilmoqda...**\n\n"
            f"📊 Jami foydalanuvchilar: {total_users} ta\n"
            f"✅ Yuborildi: 0 ta\n"
            f"❌ Xatolik: 0 ta\n"
            f"⏳ Qoldi: {total_users} ta",
            parse_mode="Markdown"
        )
        
        # Xabarni yuborish
        for i, user in enumerate(users, 1):
            try:
                await bot.send_message(
                    chat_id=int(user['user_id']),
                    text=message.text,
                    parse_mode="Markdown" if "**" in message.text else None
                )
                success_count += 1
                
                # Har 10 ta xabardan keyin progress yangilash
                if i % 10 == 0 or i == total_users:
                    remaining = total_users - i
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_msg.message_id,
                        text=f"📢 **Ommaviy xabar yuborilmoqda...**\n\n"
                             f"📊 Jami foydalanuvchilar: {total_users} ta\n"
                             f"✅ Yuborildi: {success_count} ta\n"
                             f"❌ Xatolik: {failed_count} ta\n"
                             f"⏳ Qoldi: {remaining} ta",
                        parse_mode="Markdown"
                    )
                
                await asyncio.sleep(0.1)  # Rate limiting uchun
            except (TelegramBadRequest, Exception) as e:
                failed_count += 1
                # Faqat muhim xatoliklarni log qilish
                error_msg = str(e).lower()
                if "blocked" not in error_msg and "deactivated" not in error_msg:
                    logging.error(f"Xabar yuborishda xatolik {user['user_id']}: {e}")
                else:
                    # Bloklangan yoki deaktivatsiya qilingan foydalanuvchilar uchun faqat debug
                    logging.debug(f"Foydalanuvchi bloklagan yoki deaktivatsiya qilingan: {user['user_id']}")
        
        # Yakuniy natijani ko'rsatish
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=progress_msg.message_id,
            text=f"📢 **Ommaviy xabar yuborildi!**\n\n"
                 f"✅ Muvaffaqiyatli: {success_count} ta\n"
                 f"❌ Bloklaganlar: {failed_count} ta\n"
                 f"📊 Jami: {total_users} ta foydalanuvchi",
            parse_mode="Markdown"
        )
        
        await message.answer(
            "✅ Ommaviy xabar muvaffaqiyatli yakunlandi!",
            reply_markup=get_admin_keyboard()
        )
    
    elif broadcast_type == "photo":
        # Rasm bilan xabar yuborish
        if not message.photo:
            await message.answer("❌ Rasm topilmadi! Iltimos, rasm yuboring.")
            return
            
        users = await get_all_users()
        success_count = 0
        failed_count = 0
        
        total_users = len(users)
        progress_msg = await message.answer(
            f"📢 **Rasm bilan xabar yuborilmoqda...**\n\n"
            f"📊 Jami foydalanuvchilar: {total_users} ta\n"
            f"✅ Yuborildi: 0 ta\n"
            f"❌ Xatolik: 0 ta\n"
            f"⏳ Qoldi: {total_users} ta",
            parse_mode="Markdown"
        )
        
        caption = message.caption or ""
        
        for i, user in enumerate(users, 1):
            try:
                await bot.send_photo(
                    chat_id=int(user['user_id']),
                    photo=message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="Markdown" if "**" in caption else None
                )
                success_count += 1
                
                if i % 10 == 0 or i == total_users:
                    remaining = total_users - i
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_msg.message_id,
                        text=f"📢 **Rasm bilan xabar yuborilmoqda...**\n\n"
                             f"📊 Jami foydalanuvchilar: {total_users} ta\n"
                             f"✅ Yuborildi: {success_count} ta\n"
                             f"❌ Xatolik: {failed_count} ta\n"
                             f"⏳ Qoldi: {remaining} ta",
                        parse_mode="Markdown"
                    )
                
                await asyncio.sleep(0.1)
            except (TelegramBadRequest, Exception) as e:
                failed_count += 1
                error_msg = str(e).lower()
                if "blocked" not in error_msg and "deactivated" not in error_msg:
                    logging.error(f"Rasm yuborishda xatolik {user['user_id']}: {e}")
                else:
                    logging.debug(f"Foydalanuvchi bloklagan yoki deaktivatsiya qilingan: {user['user_id']}")
        
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=progress_msg.message_id,
            text=f"📢 **Rasm bilan xabar yuborildi!**\n\n"
                 f"✅ Muvaffaqiyatli: {success_count} ta\n"
                 f"❌ Bloklaganlar: {failed_count} ta\n"
                 f"📊 Jami: {total_users} ta foydalanuvchi",
            parse_mode="Markdown"
        )
        
        await message.answer(
            "✅ Rasm bilan xabar muvaffaqiyatli yakunlandi!",
            reply_markup=get_admin_keyboard()
        )
    
    elif broadcast_type == "document":
        # Hujjat bilan xabar yuborish
        if not message.document:
            await message.answer("❌ Hujjat topilmadi! Iltimos, hujjat yuboring.")
            return
            
        users = await get_all_users()
        success_count = 0
        failed_count = 0
        
        total_users = len(users)
        progress_msg = await message.answer(
            f"📢 **Hujjat bilan xabar yuborilmoqda...**\n\n"
            f"📊 Jami foydalanuvchilar: {total_users} ta\n"
            f"✅ Yuborildi: 0 ta\n"
            f"❌ Xatolik: 0 ta\n"
            f"⏳ Qoldi: {total_users} ta",
            parse_mode="Markdown"
        )
        
        caption = message.caption or ""
        
        for i, user in enumerate(users, 1):
            try:
                await bot.send_document(
                    chat_id=int(user['user_id']),
                    document=message.document.file_id,
                    caption=caption,
                    parse_mode="Markdown" if "**" in caption else None
                )
                success_count += 1
                
                if i % 10 == 0 or i == total_users:
                    remaining = total_users - i
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_msg.message_id,
                        text=f"📢 **Hujjat bilan xabar yuborilmoqda...**\n\n"
                             f"📊 Jami foydalanuvchilar: {total_users} ta\n"
                             f"✅ Yuborildi: {success_count} ta\n"
                             f"❌ Xatolik: {failed_count} ta\n"
                             f"⏳ Qoldi: {remaining} ta",
                        parse_mode="Markdown"
                    )
                
                await asyncio.sleep(0.1)
            except (TelegramBadRequest, Exception) as e:
                failed_count += 1
                error_msg = str(e).lower()
                if "blocked" not in error_msg and "deactivated" not in error_msg:
                    logging.error(f"Hujjat yuborishda xatolik {user['user_id']}: {e}")
                else:
                    logging.debug(f"Foydalanuvchi bloklagan yoki deaktivatsiya qilingan: {user['user_id']}")
        
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=progress_msg.message_id,
            text=f"📢 **Hujjat bilan xabar yuborildi!**\n\n"
                 f"✅ Muvaffaqiyatli: {success_count} ta\n"
                 f"❌ Bloklaganlar: {failed_count} ta\n"
                 f"📊 Jami: {total_users} ta foydalanuvchi",
            parse_mode="Markdown"
        )
        
        await message.answer(
            "✅ Hujjat bilan xabar muvaffaqiyatli yakunlandi!",
            reply_markup=get_admin_keyboard()
        )
    
    await state.set_state(AdminStates.MENU)

# Bir kishiga xabar yuborish
@dp.message(StateFilter(AdminStates.MENU), F.text == "💬 Bir kishiga xabar")
async def send_to_user_menu(message: types.Message, state: FSMContext):
    """Bir kishiga xabar menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💬 **Bir kishiga xabar yuborish**\n\n"
        "Foydalanuvchi ID sini kiriting:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AdminStates.USER_ID_INPUT)

@dp.message(StateFilter(AdminStates.USER_ID_INPUT))
async def process_user_id(message: types.Message, state: FSMContext):
    """Foydalanuvchi ID ni qayta ishlash"""
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_tg_id(user_id)
        
        if user:
            await state.update_data(target_user_id=user_id)
            await message.answer(
                f"✅ **Foydalanuvchi topildi!**\n\n"
                f"👤 Ism: {user.get('full_name', 'Noma\'lum')}\n"
                f"📱 Username: @{user.get('username', 'Noma\'lum')}\n"
                f"📅 Qo'shilgan: {user.get('created_at', 'Noma\'lum')}\n\n"
                f"Yubormoqchi bo'lgan xabaringizni yuboring:",
                parse_mode="Markdown"
            )
            await state.set_state(AdminStates.USER_MESSAGE)
        else:
            await message.answer(
                "❌ **Foydalanuvchi topilmadi!**\n\n"
                "To'g'ri ID kiriting yoki qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.MENU)
            
    except ValueError:
        await message.answer(
            "❌ **Noto'g'ri ID format!**\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(AdminStates.MENU)

@dp.message(StateFilter(AdminStates.USER_MESSAGE))
async def process_user_message(message: types.Message, state: FSMContext):
    """Foydalanuvchiga xabarni yuborish"""
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=message.text,
            parse_mode="Markdown" if "**" in message.text else None
        )
        
        await message.answer(
            f"✅ **Xabar muvaffaqiyatli yuborildi!**\n\n"
            f"👤 Foydalanuvchi ID: {target_user_id}",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        
        # Log qilish
        await log_action(message.from_user.id, "admin_message_sent", {
            'target_user_id': target_user_id,
            'message': message.text[:100] + "..." if len(message.text) > 100 else message.text
        })
        
    except Exception as e:
        await message.answer(
            f"❌ **Xabar yuborishda xatolik!**\n\n"
            f"Xatolik: {str(e)}",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
    
    await state.set_state(AdminStates.MENU)

# Statistika
@dp.message(StateFilter(AdminStates.MENU), F.text == "📊 Statistika")
async def statistics_menu(message: types.Message):
    """Statistika menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📊 **Statistika**\n\n"
        "Qanday statistikani ko'rmoqchisiz?",
        reply_markup=get_stats_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "stats_general")
async def show_general_stats(callback: types.CallbackQuery):
    """Umumiy statistikani ko'rsatish"""
    await callback.answer("📊 Umumiy statistika...")
    
    try:
        # Barcha foydalanuvchilarni olish
        users = await get_all_users()
        
        # Statistika hisoblash
        total_users = len(users)
        active_users = 0
        blocked_users = 0
        
        for user in users:
            try:
                # Foydalanuvchi mavjudligini tekshirish
                await bot.get_chat(user['tg_id'])
                active_users += 1
            except TelegramBadRequest:
                blocked_users += 1
            except Exception:
                blocked_users += 1
        
        stats_text = (
            f"📊 **Umumiy statistika**\n\n"
            f"👥 **Jami foydalanuvchilar:** {total_users:,}\n"
            f"✅ **Faol foydalanuvchilar:** {active_users:,}\n"
            f"🚫 **Blok qilinganlar:** {blocked_users:,}\n"
            f"📈 **Faollik darajasi:** {(active_users/total_users*100):.1f}%\n\n"
            f"📅 **Oxirgi yangilanish:** {users[0]['created_at'] if users else 'Noma\'lum'}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="stats_general")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin_menu")]
        ])
        
        await callback.message.edit_text(stats_text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ **Statistika olishda xatolik!**\n\n"
            f"Xatolik: {str(e)}",
            parse_mode="Markdown"
        )

# Balans boshqarish
@dp.message(StateFilter(AdminStates.MENU), F.text == "💰 Balans boshqarish")
async def balance_management_menu(message: types.Message):
    """Balans boshqarish menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "💰 **Balans boshqarish**\n\n"
        "Foydalanuvchi balansini boshqarish:",
        reply_markup=get_balance_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "balance_add")
async def balance_add_handler(callback: types.CallbackQuery, state: FSMContext):
    """Balans qo'shish"""
    await callback.answer("➕ Balans qo'shish...")
    
    await callback.message.edit_text(
        "➕ **Balans qo'shish**\n\n"
        "Foydalanuvchi ID sini kiriting:",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.USER_BALANCE_ID)
    await state.update_data(balance_action="add")

@dp.callback_query(F.data == "balance_subtract")
async def balance_subtract_handler(callback: types.CallbackQuery, state: FSMContext):
    """Balans ayirish"""
    await callback.answer("➖ Balans ayirish...")
    
    await callback.message.edit_text(
        "➖ **Balans ayirish**\n\n"
        "Foydalanuvchi ID sini kiriting:",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.USER_BALANCE_ID)
    await state.update_data(balance_action="subtract")

@dp.message(StateFilter(AdminStates.USER_BALANCE_ID))
async def process_balance_user_id(message: types.Message, state: FSMContext):
    """Balans uchun foydalanuvchi ID ni qayta ishlash"""
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_tg_id(user_id)
        
        if user:
            balance = await get_user_balance(user_id)
            data = await state.get_data()
            balance_action = data.get('balance_action', 'add')
            
            action_text = "qo'shish" if balance_action == "add" else "ayirish"
            
            await state.update_data(target_user_id=user_id)
            await message.answer(
                f"✅ **Foydalanuvchi topildi!**\n\n"
                f"👤 Ism: {user.get('full_name', 'Noma\'lum')}\n"
                f"💰 Joriy balans: {balance['total_balance']:,} so'm\n\n"
                f"{action_text.title()} uchun summani kiriting:",
                parse_mode="Markdown"
            )
            await state.set_state(AdminStates.BALANCE_AMOUNT)
        else:
            await message.answer(
                "❌ **Foydalanuvchi topilmadi!**\n\n"
                "To'g'ri ID kiriting yoki qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.MENU)
            
    except ValueError:
        await message.answer(
            "❌ **Noto'g'ri ID format!**\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(AdminStates.MENU)

@dp.message(StateFilter(AdminStates.BALANCE_AMOUNT))
async def process_balance_amount(message: types.Message, state: FSMContext):
    """Balans miqdorini qayta ishlash"""
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            await message.answer(
                "❌ **Summa 0 dan katta bo'lishi kerak!**\n\n"
                "Qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.MENU)
            return
        
        data = await state.get_data()
        target_user_id = data.get('target_user_id')
        balance_action = data.get('balance_action', 'add')
        
        if balance_action == "add":
            success = await update_user_balance(target_user_id, amount, 'cash')
            action_text = "qo'shildi"
        else:
            success = await deduct_user_balance(target_user_id, amount)
            action_text = "ayirildi"
        
        if success:
            # Tranzaksiya qo'shish
            await add_transaction(
                target_user_id,
                amount if balance_action == "add" else -amount,
                'admin_action',
                f'Admin tomonidan {action_text}',
                None
            )
            
            # Yangi balansni olish
            new_balance = await get_user_balance(target_user_id)
            
            await message.answer(
                f"✅ **Balans muvaffaqiyatli {action_text}!**\n\n"
                f"👤 Foydalanuvchi ID: {target_user_id}\n"
                f"💰 Summa: {amount:,} so'm\n"
                f"💳 Yangi balans: {new_balance['total_balance']:,} so'm",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
            
            # Log qilish
            await log_action(message.from_user.id, "admin_balance_change", {
                'target_user_id': target_user_id,
                'amount': amount,
                'action': balance_action
            })
        else:
            await message.answer(
                "❌ **Balans o'zgartirishda xatolik!**\n\n"
                "Iltimos, qaytadan urinib ko'ring.",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
        
    except ValueError:
        await message.answer(
            "❌ **Noto'g'ri summa format!**\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
    
    await state.set_state(AdminStates.MENU)

# Referral sozlamalari
@dp.message(StateFilter(AdminStates.MENU), F.text == "⚙️ Referral sozlamalari")
async def referral_settings_menu(message: types.Message):
    """Referral sozlamalari menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    # Hozirgi referral sozlamalari
    rewards = await get_referral_rewards()
    
    current_settings = (
        "⚙️ **Referral sozlamalari**\n\n"
        "💰 **Hozirgi bonuslar:**\n"
        f"• Taklif qilgan: {rewards['referrer_reward']:,} so'm\n"
        f"• Taklif qilingan: {rewards['referred_reward']:,} so'm\n\n"
        "📝 **Sozlash uchun:**\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    
    await message.answer(
        current_settings,
        reply_markup=get_referral_settings_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "referral_referrer_reward")
async def referral_referrer_reward_handler(callback: types.CallbackQuery, state: FSMContext):
    """Taklif qilgan uchun bonus sozlash"""
    await callback.answer("💰 Taklif qilgan uchun bonus...")
    
    rewards = await get_referral_rewards()
    
    await callback.message.edit_text(
        f"💰 **Taklif qilgan uchun bonus sozlash**\n\n"
        f"🔸 **Hozirgi bonus:** {rewards['referrer_reward']:,} so'm\n\n"
        f"Yangi bonus miqdorini kiriting (so'm):",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.REFERRAL_REWARD_INPUT)
    await state.update_data(reward_type="referrer")

@dp.callback_query(F.data == "referral_referred_reward")
async def referral_referred_reward_handler(callback: types.CallbackQuery, state: FSMContext):
    """Taklif qilingan uchun bonus sozlash"""
    await callback.answer("🎁 Taklif qilingan uchun bonus...")
    
    rewards = await get_referral_rewards()
    
    await callback.message.edit_text(
        f"🎁 **Taklif qilingan uchun bonus sozlash**\n\n"
        f"🔸 **Hozirgi bonus:** {rewards['referred_reward']:,} so'm\n\n"
        f"Yangi bonus miqdorini kiriting (so'm):",
        parse_mode="Markdown"
    )
    
    await state.set_state(AdminStates.REFERRAL_REWARD_INPUT)
    await state.update_data(reward_type="referred")

@dp.message(StateFilter(AdminStates.REFERRAL_REWARD_INPUT))
async def process_referral_reward_input(message: types.Message, state: FSMContext):
    """Referral bonus miqdorini qayta ishlash"""
    try:
        amount = int(message.text.strip())
        if amount < 0:
            await message.answer(
                "❌ **Bonus 0 dan kichik bo'lishi mumkin emas!**\n\n"
                "Qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.MENU)
            return
        
        data = await state.get_data()
        reward_type = data.get('reward_type')
        
        # Hozirgi bonuslarni olish
        current_rewards = await get_referral_rewards()
        
        if reward_type == "referrer":
            success = await update_referral_rewards(amount, current_rewards['referred_reward'])
            reward_name = "Taklif qilgan"
        else:
            success = await update_referral_rewards(current_rewards['referrer_reward'], amount)
            reward_name = "Taklif qilingan"
        
        if success:
            await message.answer(
                f"✅ **{reward_name} uchun bonus yangilandi!**\n\n"
                f"💰 **Yangi bonus:** {amount:,} so'm\n\n"
                f"🔄 Endi yangi referrallar uchun bu bonus ishlatiladi.",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
            
            # Log qilish
            await log_action(message.from_user.id, "admin_referral_reward_changed", {
                'reward_type': reward_type,
                'new_amount': amount
            })
        else:
            await message.answer(
                "❌ **Bonus yangilashda xatolik!**\n\n"
                "Iltimos, qaytadan urinib ko'ring.",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
        
    except ValueError:
        await message.answer(
            "❌ **Noto'g'ri summa format!**\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
    
    await state.set_state(AdminStates.MENU)

# Orqaga qaytish
@dp.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    """Admin menyuga qaytish"""
    await callback.answer("⬅️ Admin menyuga qaytish...")
    
    await callback.message.edit_text(
        "🔧 **Admin Panel**\n\n"
        "Quyidagi funksiyalardan birini tanlang:",
        parse_mode="Markdown"
    )
    
    # Asosiy klaviatura yuborish
    await callback.message.answer(
        "Admin menyu:",
        reply_markup=get_admin_keyboard()
    )
    
    await state.set_state(AdminStates.MENU)

# Asosiy menyuga qaytish
@dp.message(StateFilter(AdminStates.MENU), F.text == "🏠 Asosiy menyu")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Asosiy menyuga qaytish"""
    from bot import get_main_keyboard, OnboardingStates
    
    await message.answer(
        "🏠 **Asosiy menyu**\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(OnboardingStates.MENU)

# Error handler
@dp.error()
async def error_handler(event, exception):
    """Xatoliklar bilan ishlash"""
    import logging
    logger = logging.getLogger(__name__)
    
    if exception:
        logger.error(f"Admin panel xatoligi: {exception}")
    else:
        logger.warning("Admin panel noma'lum xatolik yuz berdi")

if __name__ == "__main__":
    print("Admin Panel ishga tushmoqda...")
    print(f"Admin ID lar: {ADMIN_IDS}")
    asyncio.run(dp.start_polling(bot))
