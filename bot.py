import asyncio
import logging
import os
import json
from typing import Optional
from dotenv import load_dotenv
import pytz
from datetime import datetime, timedelta
from openai import AsyncOpenAI

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from states import OnboardingStates, OrderStates
from aiogram.exceptions import TelegramBadRequest
from database_adapter import (
    init_db, get_user_by_tg_id, create_user, get_all_users, get_user_balance, update_user_balance, deduct_user_balance, get_user_statistics, get_referral_stats, create_referral, confirm_referral, log_action, get_user_free_orders_count, get_referral_rewards, update_referral_rewards, create_order, update_order_status, save_presentation
)
from openai_client import generate_presentation_content
from pptx_generator import create_presentation_file

# .env faylini yuklash
load_dotenv()

# Bot tokenini environment variabledan olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variablesi topilmadi!")

# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "test_key")
if OPENAI_API_KEY == "test_key":
    print("OPENAI_API_KEY topilmadi! Test rejimida ishlaydi.")
    OPENAI_API_KEY = None
    openai_client = None
else:
    # OpenAI client sozlash (yangi format)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Admin ID larini environment variabledan olish
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]

# Vaqt sozlamalari
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

def get_current_time():
    """Hozirgi Toshkent vaqtini qaytaradi"""
    return datetime.now(TASHKENT_TZ)

def format_time(dt=None):
    """Vaqtni formatlash"""
    if dt is None:
        dt = get_current_time()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

async def generate_presentation_content(topic: str, pages: int) -> dict:
    """ChatGPT API dan taqdimot kontentini yaratish - yangi struktura"""
    from pptx_generator import generate_presentation_content_with_gpt
    return await generate_presentation_content_with_gpt(topic, pages)

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global error handler
@dp.error()
async def error_handler(event, exception):
    """Global error handler"""
    logging.error(f"Bot xatoligi: event={event}, exception={exception}")
    print(f"Bot xatoligi: {exception}")
    
    # Foydalanuvchiga umumiy xatolik xabari
    if hasattr(event, 'message') and event.message:
        try:
            await event.message.answer(
                "❌ Xatolik yuz berdi!\n\n"
                "Iltimos, qaytadan urinib ko'ring yoki /start buyrug'ini yuboring.",
            )
        except:
            pass
    
    return True

# Tariflar haqida ma'lumot
TARIFFS = {
    "START": {
        "name": "Start tarifi 🚀",
        "price": "Bepul (1 marta)",
        "price_per_page": 2000,
        "features": ["1 marta bepul", "Har sahifa 2000 so'm", "PPT format"]
    },
    "STANDARD": {
        "name": "Standard tarifi 💎",
        "price": "4,500 so'm", 
        "price_per_page": 4500,
        "features": ["Professional dizayn", "PPT format"]
    },
    "SMART": {
        "name": "Smart tarifi 🧠",
        "price": "6,500 so'm", 
        "price_per_page": 6500,
        "features": ["Smart dizayn", "PPT + PDF format", "AI optimizatsiya"]
    }
}

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi"""
    builder = ReplyKeyboardBuilder()
    # Birinchi qator - 2 ta tugma
    builder.row(
        KeyboardButton(text="📊 Taqdimot tayyorlash"),
        KeyboardButton(text="📝 Mustaqil ishlar")
    )
    # Ikkinchi qator - 2 ta tugma
    builder.row(
        KeyboardButton(text="🔧 Boshqa xizmatlar"),
        KeyboardButton(text="🎮 Sehrli o'yin")
    )
    # Uchinchi qator - 2 ta tugma
    builder.row(
        KeyboardButton(text="💰 Balansim"),
        KeyboardButton(text="ℹ️ Bot haqida")
    )
    # To'rtinchi qator - 1 ta tugma
    builder.row(KeyboardButton(text="📞 Aloqa uchun"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


# Admin tekshirish funksiyasi
async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id in ADMIN_IDS

# Admin guruhga taqdimot yuborish funksiyasi
async def send_presentation_to_admin_group(user_tg_id: int, topic: str, pages: int, tariff: str, file_path: str):
    """Tayyorlangan taqdimotni admin guruhga yuborish"""
    try:
        # Guruh ID
        group_id = int(os.getenv("GROUP_ID", "-1001234567890"))
        
        # Foydalanuvchi ma'lumotlarini olish
        user = await get_user_by_tg_id(user_tg_id)
        if not user:
            return
        
        # Balans ma'lumotlarini olish
        balance = await get_user_balance(user_tg_id)
        
        # Tarif narxini hisoblash
        tariff_info = TARIFFS[tariff]
        total_price = pages * tariff_info['price_per_page']
        
        # Fayl nomini tayyorlash
        filename = f"taqdimot_{topic.replace(' ', '_')}.pptx"
        
        # Admin guruhga fayl yuborish
        from aiogram.types import FSInputFile
        input_file = FSInputFile(file_path, filename=filename)
        
        # Xavfsiz matn tayyorlash
        safe_full_name = str(user.get('full_name', 'Noma\'lum'))
        safe_username = str(user.get('username', 'Noma\'lum'))
        safe_topic = str(topic)
        safe_tariff_name = str(tariff_info['name'])
        safe_filename = str(filename)
        
        await bot.send_document(
            chat_id=group_id,
            document=input_file,
            caption=f"📊 Yangi taqdimot tayyorlandi!\n\n"
                   f"👤 Foydalanuvchi: {safe_full_name}\n"
                   f"🆔 ID: {user_tg_id}\n"
                   f"📱 Username: @{safe_username}\n\n"
                   f"📋 Taqdimot ma'lumotlari:\n"
                   f"• Mavzu: {safe_topic}\n"
                   f"• Sahifalar: {pages} ta\n"
                   f"• Tarif: {safe_tariff_name}\n"
                   f"• Narx: {total_price:,} so'm\n\n"
                   f"💰 Foydalanuvchi balansi: {balance['total_balance']:,} so'm\n"
                   f"📅 Tayyorlangan vaqt: {format_time()}\n\n"
                   f"📁 Fayl: {safe_filename}"
        )
        
        # Log qilish
        await log_action(user_tg_id, "presentation_sent_to_admin", {
            'topic': topic,
            'pages': pages,
            'tariff': tariff,
            'total_price': total_price,
            'group_id': group_id
        })
        
    except Exception as e:
        logging.error(f"Admin guruhga taqdimot yuborishda xatolik: {e}")


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Admin asosiy klaviaturasi"""
    builder = ReplyKeyboardBuilder()
    # Birinchi qator - 2 ta tugma
    builder.row(
        KeyboardButton(text="📢 Ommaviy xabar"),
        KeyboardButton(text="💬 Bir kishiga xabar")
    )
    # Ikkinchi qator - 2 ta tugma
    builder.row(
        KeyboardButton(text="📊 Statistika"),
        KeyboardButton(text="💰 Balans boshqarish")
    )
    # Uchinchi qator - 1 ta tugma
    builder.row(
        KeyboardButton(text="⚙️ Referral sozlamalari")
    )
    # To'rtinchi qator - 1 ta tugma
    builder.row(
        KeyboardButton(text="🏠 Asosiy menyu")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """Kontakt bo'lishish klaviaturasi"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📱 Telefon raqamni bo'lishish", request_contact=True))
    builder.row(KeyboardButton(text="⏩ O'tkazib yuborish"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_tariff_keyboard() -> InlineKeyboardMarkup:
    """Tarif tanlash uchun inline klaviatura"""
    builder = InlineKeyboardBuilder()
    
    for tariff_key, tariff_info in TARIFFS.items():
        builder.row(InlineKeyboardButton(
            text=f"{tariff_info['name']} - {tariff_info['price']}",
            callback_data=f"tariff_{tariff_key}"
        ))
    
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu"))
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Orqaga qaytish uchun klaviatura"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu"))
    return builder.as_markup()


@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    """Bot ishga tushganda birinchi handler"""
    try:
        if not message.from_user:
            return
        
        # Referral havola tekshirish
        referral_id = None
        if len(message.text.split()) > 1:
            start_param = message.text.split()[1]
            if start_param.startswith('ref_'):
                try:
                    referral_id = int(start_param.replace('ref_', ''))
                    # Agar o'zini taklif qilmoqchi bo'lsa
                    if referral_id == message.from_user.id:
                        referral_id = None
                except ValueError:
                    referral_id = None
        
        user = await get_user_by_tg_id(message.from_user.id)
        
        if user:
            # Agar foydalanuvchi mavjud bo'lsa, menyuga o'tkazish
            full_name = user.get('name', 'Foydalanuvchi')
            await message.answer(
                f"Assalomu alaykum, {full_name}! 👋\n\n"
                "Qaytganingizdan xursandmiz. Quyidagi tugmalardan birini tanlang:",
                reply_markup=get_main_keyboard()
            )
            await state.set_state(OnboardingStates.MENU)
        else:
            # Yangi foydalanuvchi uchun ro'yxatdan o'tish
            welcome_text = (
                "Assalomu alaykum va xush kelibsiz! 👋\n\n"
                "Men sizga professional taqdimotlar tayyorlashda yordam beradigan botman.\n\n"
            )
            
            # Agar referral havola orqali kelgan bo'lsa
            if referral_id:
                referrer = await get_user_by_tg_id(referral_id)
                if referrer:
                    referrer_name = referrer.get('full_name', 'Do\'stingiz')
                    welcome_text += f"🎉 Sizni {referrer_name} taklif qildi!\n\n"
                    # Referral yaratish
                    await create_referral(referral_id, message.from_user.id)
            
            welcome_text += "Keling, tanishib olaylik! Ism-familiyangizni kiriting:"
            
            await message.answer(
                welcome_text,
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.set_state(OnboardingStates.ASK_FULLNAME)
    
    except Exception as e:
        logging.error(f"Start handler xatoligi: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=types.ReplyKeyboardRemove()
        )


@dp.message(StateFilter(OnboardingStates.ASK_FULLNAME))
async def process_fullname(message: types.Message, state: FSMContext):
    """Ism-familiyani qayta ishlash"""
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting:")
        return
    
    await state.update_data(full_name=full_name)
    
    await message.answer(
        f"Rahmat, {full_name}! 👍\n\n"
        "Endi telefon raqamingizni bo'lishingiz mumkin yoki o'tkazib yuborishingiz mumkin:",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(OnboardingStates.ASK_CONTACT)


@dp.message(StateFilter(OnboardingStates.ASK_CONTACT), F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    """Kontakt ma'lumotlarini qayta ishlash"""
    contact = message.contact
    
    await state.update_data(
        phone=contact.phone_number,
        contact_shared=True
    )
    
    await finish_registration(message, state)


@dp.message(StateFilter(OnboardingStates.ASK_CONTACT), F.text == "⏩ O'tkazib yuborish")
async def skip_contact(message: types.Message, state: FSMContext):
    """Kontaktni o'tkazib yuborish"""
    await state.update_data(
        phone=None,
        contact_shared=False
    )
    
    await finish_registration(message, state)


async def finish_registration(message: types.Message, state: FSMContext):
    """Ro'yxatdan o'tishni yakunlash"""
    data = await state.get_data()
    
    if not message.from_user:
        return
    
    # Foydalanuvchini ma'lumotlar bazasiga saqlash
    user_data = {
        'tg_id': message.from_user.id,
        'username': message.from_user.username,
        'full_name': data.get('full_name'),
        'phone': data.get('phone'),
        'contact_shared': data.get('contact_shared', False)
    }
    
    await create_user(user_data)
    
    # Referral funksiyalari hozircha ishlamaydi
    referral_confirmed = False
    
    welcome_text = (
        f"🎉 Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n"
        f"Salom, {data.get('full_name')}! Endi siz botning barcha imkoniyatlaridan foydalanishingiz mumkin.\n\n"
    )
    
    # Agar referral tasdiqlangan bo'lsa
    if referral_confirmed:
        welcome_text += "🎁 Bonus: Sizga referral bonus sifatida 500 so'm qo'shildi!\n\n"
    
    welcome_text += "Quyidagi tugmalardan birini tanlang:"
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    await state.set_state(OnboardingStates.MENU)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📊 Taqdimot tayyorlash")
async def start_presentation_order(message: types.Message, state: FSMContext):
    """Taqdimot buyurtmasini boshlash"""
    await message.answer(
        "📊 Taqdimot tayyorlash xizmati:\n\n"
        "AI yordamida professional taqdimotlar tayyorlab beramiz!\n\n"
        "Quyidagi tariflardan birini tanlang:",
        reply_markup=get_tariff_keyboard()
    )


@dp.message(StateFilter(OrderStates.ASK_TOPIC))
async def process_topic(message: types.Message, state: FSMContext):
    """Taqdimot mavzusini qayta ishlash"""
    topic = message.text.strip()
    
    # Mavzu tekshirish - kamida 3 ta so'z bo'lishi kerak
    words = topic.split()
    if len(words) < 2 or len(topic) < 10:
        await message.answer(
            "❌ Mavzu nomini to'liq va aniq kiriting!\n\n"
            "Misol:\n"
            "Interstellar - kino haqida ✅\n"
            "Interstellar ❌"
        )
        return
    
    await state.update_data(topic=topic)
    
    await message.answer(
        f"✅ Mavzu nomini qabul qilib oldim!\n\n"
        f"Mavzu: {topic}\n\n"
        "Endi esa sahifalar sonini kiriting:\n\n"
        "Misol:\n"
        "10 ✅\n"
        "10-12 ❌\n"
        "14ta ❌\n"
        "Yigirma ❌\n"
        "Yigirma ikkita ❌\n"
        "O'n sakkiz sahifali ❌\n\n"
        "⚠️ Eslatma: 1-4 raqamlar qabul qilinmaydi!"
    )
    await state.set_state(OrderStates.ASK_PAGES)


@dp.message(StateFilter(OrderStates.ASK_PAGES))
async def process_pages(message: types.Message, state: FSMContext):
    """Sahifalar sonini qayta ishlash"""
    try:
        pages = int(message.text.strip())
        
        # 1-4 raqamlar qabul qilinmaydi
        if pages >= 1 and pages <= 4:
            await message.answer(
                "❌ Bu qiymatdagi taqdimotni tayyorlash imkonsiz!\n\n"
                "5 va undan yuqori raqam kiriting:"
            )
            return
        
        if pages < 5 or pages > 50:
            await message.answer(
                "❌ Noto'g'ri raqam!\n\n"
                "5-50 orasida raqam kiriting:"
            )
            return
        
        await state.update_data(pages=pages)
        data = await state.get_data()
        topic = data.get('topic', '')
        tariff_key = data.get('tariff', '')
        
        # Foydalanuvchi ma'lumotlarini olish
        user = await get_user_by_tg_id(message.from_user.id) if message.from_user else None
        user_name = user.get('full_name', 'Foydalanuvchi') if user else 'Foydalanuvchi'
        
        # Yakuniy buyurtma ma'lumotlari
        confirmation_text = (
            f"✅ Javoblarni qabul qildim!\n\n"
            f"Sizning yakuniy buyurtmangiz quyidagicha ko'rinishda:\n\n"
            f"📊 Mavzu nomi: {topic}\n"
            f"📄 Sahifalar soni: {pages} ta\n"
            f"👤 Talaba: {user_name}\n\n"
            f"❓ Buyurtmani tasdiqlaysizmi?"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")]
        ])
        
        await message.answer(
            confirmation_text,
            reply_markup=keyboard
        )
        await state.set_state(OrderStates.CONFIRM_1)
        
    except ValueError:
        await message.answer(
            "❌ Faqat raqam kiriting!\n\n"
            "Misol:\n"
            "10 ✅\n"
            "10-12 ❌\n"
            "14ta ❌"
        )
        return


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "ℹ️ Bot haqida")
async def about_bot(message: types.Message):
    """Bot haqida ma'lumot"""
    about_text = (
        "🤖 PresentatsiyaUz Bot haqida:\n\n"
        "Biz \"PresentatsiyaUz\" jamoasi 5 yildan buyon nafaqat O'zbekiston balki, "
        "MDH mamlakatlari talabalariga ham xizmat ko'rsatib kelmoqdamiz.\n\n"
        "Bu bot bizning barcha xizmatlarimizni faqat elektron shaklda taqdim etadi, "
        "biz qo'l yozuvi, chizmachilik yoki chop etish bilan shug'ullanmaymiz. "
        "(*hozircha)\n\n"
        "Agar siz botni tushunishda muammolarga duch kelsangiz yoki narxlar bilan "
        "bog'liq muammolarga duch kelsangiz, \"Aloqa uchun\" tugmasi orqali "
        "administratorlardan buyurtma bering!\n\n"
        "💳 To'lov kartalari:\n"
        "• Uzcard: 5614682110523232\n"
        "• Humo: 9860170104108668\n"
        "• VISA: 4023060518185649\n"
        "(Sodiqjon Nigmatov)"
    )
    
    # Havolalar uchun tugmalar
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Bot asoschisi", url="https://t.me/MUKHAMMADSODlQ")],
        [InlineKeyboardButton(text="👨‍💼 Ikkinchi akkaunt", url="https://t.me/MUHAMMADS0DlQ")],
        [InlineKeyboardButton(text="📢 Kanal", url="https://t.me/preuzb")],
        [InlineKeyboardButton(text="✅ Ishonch kanali", url="https://t.me/pre_ishonch")],
        [InlineKeyboardButton(text="👨‍💼 Admin1", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="👨‍💼 Admin2", url="https://t.me/prezintatsiyauz_admin")],
        [InlineKeyboardButton(text="🛒 Soff'dagi biz", url="https://soff.uz/seller/879")],
        [InlineKeyboardButton(text="📸 Instagram", url="https://www.instagram.com/prezintatsiya.uz/profilecard/?igsh=ZDVqcnZ5Z2JpaTlt")],
        [InlineKeyboardButton(text="💝 Donat", url="https://tirikchilik.uz/mukhammadsodiq")]
    ])
    
    await message.answer(about_text, reply_markup=keyboard)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📝 Mustaqil ishlar")
async def independent_works(message: types.Message):
    """Mustaqil ishlar tayyorlash"""
    works_text = (
        "📝 Mustaqil ishlar tayyorlash:\n\n"
        "Professional mustaqil ishlarni tayyorlab beramiz!\n\n"
        "Quyidagi xizmatlardan birini tanlang:"
    )
    
    # Mustaqil ishlar tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Kurs ishi tayyorlash", callback_data="course_work")],
        [InlineKeyboardButton(text="📄 Ilmiy maqola tayyorlash", callback_data="scientific_article")],
        [InlineKeyboardButton(text="📚 Referat tayyorlash", callback_data="essay")],
        [InlineKeyboardButton(text="📋 Mustaqil ish tayyorlash", callback_data="independent_work")],
        [InlineKeyboardButton(text="📊 Hisobot tayyorlash", callback_data="report")]
    ])
    
    await message.answer(works_text, reply_markup=keyboard)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🔧 Boshqa xizmatlar")
async def other_services(message: types.Message):
    """Boshqa xizmatlar"""
    services_text = (
        "🔧 Boshqa xizmatlar:\n\n"
        "Professional dizayn va yozuv xizmatlarini taklif etamiz!\n\n"
        "Quyidagi xizmatlardan birini tanlang:"
    )
    
    # Boshqa xizmatlar tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Online taklifnoma (QR-kodli)", callback_data="online_invitation")],
        [InlineKeyboardButton(text="📄 Rezyume", callback_data="resume")],
        [InlineKeyboardButton(text="🎨 YouTube kanal uchun banner", callback_data="youtube_banner")],
        [InlineKeyboardButton(text="🎯 Logo tayyorlash", callback_data="logo_design")]
    ])
    
    await message.answer(services_text, reply_markup=keyboard)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🎮 Sehrli o'yin")
async def magic_game(message: types.Message):
    """Sehrli o'yin - Akinator"""
    game_text = (
        "🎮 Sehrli o'yin - Akinator\n\n"
        "Men sizning fikringizni o'qib, siz haqingizda aytaman!\n\n"
        "🤔 Akinator nima?\n"
        "Bu mashhur o'yin sizning fikringizdagi shaxs, hayvon yoki narsani "
        "faqat savollar berish orqali aniqlaydi!\n\n"
        "🎯 Qanday o'ynaydi:\n"
        "1. Siz biror kishi, hayvon yoki narsa haqida o'ylang\n"
        "2. Akinator sizga savollar beradi\n"
        "3. Siz \"Ha\", \"Yo'q\" yoki \"Ehtimol\" javob bering\n"
        "4. Akinator sizning fikringizni aniqlaydi!\n\n"
        "🚀 O'yinni boshlash uchun tugmani bosing!"
    )
    
    # Akinator mini app tugmasi
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎯 Akinator o'ynash", 
            web_app=types.WebAppInfo(url="https://en.akinator.com/")
        )]
    ])
    
    await message.answer(game_text, reply_markup=keyboard)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "💰 Balansim")
async def my_balance(message: types.Message):
    """Foydalanuvchi balansi"""
    if not message.from_user:
        return
    
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmadingiz. /start buyrug'ini yuboring.")
        return
    
    # Real balans ma'lumotlarini olish
    balance = await get_user_balance(message.from_user.id)
    
    # Foydalanuvchi statistikasini olish
    stats = await get_user_statistics(message.from_user.id)
    
    # Referral statistikasini olish
    referral_stats = await get_referral_stats(message.from_user.id)
    
    current_time = format_time()
    balance_text = (
        f"💰 Sizning balansingiz:\n\n"
        f"💳 Umumiy balans: {balance['total_balance']:,} so'm\n\n"
        f"📊 Balans tafsilotlari:\n"
        f"• Naqt orqali to'langan: {balance['cash_balance']:,} so'm\n"
        f"• {referral_stats['confirmed_referrals']} ta taklif uchun: {balance['referral_balance']:,} so'm\n\n"
        f"📈 Statistika:\n"
        f"• Yaratilgan taqdimotlar: {stats.get('total_presentations', 0)}\n"
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yoq')}\n"
        f"• Qo'shilgan sana: {user.get('created_at', 'Nomalum')}\n\n"
        f"🕐 Oxirgi yangilanish: {current_time}"
    )
    
    # Balans tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
        [InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referral_link")],
        [InlineKeyboardButton(text="📊 Referral statistikasi", callback_data="referral_stats")]
    ])
    
    await message.answer(balance_text, reply_markup=keyboard)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📞 Aloqa uchun")
async def contact_us(message: types.Message):
    """Aloqa uchun"""
    # Admin havolalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Birinchi admin", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="👩‍💼 Ikkinchi admin", url="https://t.me/prezintatsiyauz_admin")],
        [InlineKeyboardButton(text="👨‍💻 Direktor1", url="https://t.me/MUHAMMADS0DlQ")],
        [InlineKeyboardButton(text="👨‍💻 Direktor2", url="https://t.me/MUKHAMMADSODlQ")]
    ])
    
    contact_text = (
        "📞 Biz bilan bog'laning:\n\n"
        "Quyidagi adminlar bilan bog'laning:\n\n"
        "🕐 Ish vaqti:\n"
        "Dushanba - Juma: 09:00 - 18:00\n"
        "Shanba - Yakshanba: 10:00 - 16:00\n\n"
        "❓ Savollar bormi?\n"
        "Har qanday savol va takliflar uchun adminlardan biriga yozing!"
    )
    
    await message.answer(contact_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(Command("stats"))
async def user_stats(message: types.Message):
    """Foydalanuvchi statistikasi"""
    if not message.from_user:
        return
    
    stats = await get_user_statistics(message.from_user.id)
    
    stats_text = (
        f"📊 Sizning statistikangiz:\n\n"
        f"📈 Umumiy ko'rsatkichlar:\n"
        f"• Yaratilgan taqdimotlar: {stats.get('total_presentations', 0)}\n"
        f"• Faol kunlar: {stats.get('active_days', 0)}\n"
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yoq')}\n\n"
        f"🎯 Faoliyat:\n"
        f"• Bu oy: {stats.get('this_month', 0)} ta taqdimot\n"
        f"• O'tgan oy: {stats.get('last_month', 0)} ta taqdimot\n\n"
        f"💡 Maslahat: Ko'proq taqdimot yaratib, tajribangizni oshiring!"
    )
    
    await message.answer(stats_text, parse_mode="Markdown")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    """Admin panel"""
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return
    
    await message.answer(
        "🔧 Admin Panel\n\n"
        "Quyidagi funksiyalardan birini tanlang:",
        reply_markup=get_admin_keyboard(),
    )
    await state.set_state(OnboardingStates.MENU)


# Callback query handlers
@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: types.CallbackQuery, state: FSMContext):
    """Tarif tanlashni qayta ishlash"""
    tariff_key = callback.data.replace("tariff_", "")
    await state.update_data(tariff=tariff_key)
    
    tariff_info = TARIFFS[tariff_key]
    
    if tariff_key == "START":
        # Foydalanuvchining bepul buyurtmalar sonini olish
        free_orders_count = await get_user_free_orders_count(callback.from_user.id)
        remaining_free = 1 - free_orders_count
        
        if remaining_free > 0:
            start_text = (
                f"🚀 Start tarifini tanladingiz!\n\n"
                f"Ushbu tarifdan foydalanish {remaining_free} marta bepul qoldi! "
                f"(siz allaqachon {free_orders_count} marta foydalangansiz)\n\n"
                f"Bepul buyurtmalar tugagach, har bir sahifasi uchun {tariff_info['price_per_page']:,} so'mdan to'laysiz.\n"
                f"Format: PPT\n\n"
                f"Endi esa mavzu nomini to'liq va aniq kiriting:\n\n"
                f"Misol:\n"
                f"Interstellar - kino haqida ✅\n"
                f"Interstellar ❌"
            )
        else:
            start_text = (
                f"🚀 Start tarifini tanladingiz!\n\n"
                f"⚠️ Bepul buyurtmalar tugadi! "
                f"Siz allaqachon 1 marta bepul foydalangansiz.\n\n"
                f"Endi har bir sahifasi uchun {tariff_info['price_per_page']:,} so'mdan to'laysiz.\n"
                f"Format: PPT\n\n"
                f"Endi esa mavzu nomini to'liq va aniq kiriting:\n\n"
                f"Misol:\n"
                f"Interstellar - kino haqida ✅\n"
                f"Interstellar ❌"
            )
    else:
        if tariff_key == "STANDARD":
            format_text = "PPT"
        elif tariff_key == "SMART":
            format_text = "PPT + PDF"
        else:
            format_text = "PPT"
            
        # Markdown'da maxsus belgilarni escape qilish
        tariff_name = tariff_info['name'].replace('*', '*').replace('_', '_').replace('[', '[').replace('`', '`')
        format_name = format_text.replace('*', '*').replace('_', '_').replace('[', '[').replace('`', '`')
        
        start_text = (
            f"💰 {tariff_name}ni tanladingiz!\n\n"
            f"Format: {format_name}\n\n"
            f"Endi esa Mavzu nomini to'liq va aniq kiriting:\n\n"
            f"Misol:\n"
            f"Interstellar - kino haqida ✅\n"
            f"Interstellar ❌"
        )
    
    await callback.message.edit_text(
        start_text,
    )
    
    await callback.answer()
    await state.set_state(OrderStates.ASK_TOPIC)


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await callback.message.edit_text(
        "🏠 Asosiy menyu\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=None
    )
    
    # Asosiy klaviatura yuborish
    await callback.message.answer(
        "Bosh menyu:",
        reply_markup=get_main_keyboard()
    )
    
    await callback.answer("Asosiy menyuga qaytildi")
    await state.set_state(OnboardingStates.MENU)


@dp.callback_query(StateFilter(OrderStates.PREVIEW), F.data == "confirm_yes")
async def confirm_preview(callback: types.CallbackQuery, state: FSMContext):
    """Taqdimotni ko'rib chiqishdan keyin tasdiqlash"""
    await callback.answer("✅ Tasdiqlanmoqda...")
    
    data = await state.get_data()
    
    # Buyurtma yaratish
    order_data = {
        'user_tg_id': callback.from_user.id,
        'topic': data['topic'],
        'pages': data['pages'],
        'tariff': data['tariff'],
        'status': 'confirmed'
    }
    
    order_id = await create_order(order_data)
    
    await callback.message.edit_text(
        "🎉 Buyurtma tasdiqlandi!\n\n"
        "🚀 Taqdimot yaratish jarayoni boshlandi...\n"
        "⏱️ Tahmini vaqt: 2-3 daqiqa\n\n"
        "📱 Tayyor bo'lganda sizga xabar beramiz!",
        reply_markup=get_back_keyboard(),
    )
    
    await state.set_state(OnboardingStates.MENU)
    
    # Taqdimot yaratish vazifasini boshlash
    asyncio.create_task(generate_presentation_task(
        callback.from_user.id, order_id, data['topic'], data['pages'], data['tariff']
    ))


@dp.callback_query(StateFilter(OrderStates.CONFIRM_1), F.data == "confirm_yes")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    """Buyurtmani tasdiqlash - birinchi bosqich"""
    await callback.answer("✅ Birinchi tasdiqlash...")
    
    data = await state.get_data()
    tariff_key = data.get('tariff', '')
    pages = data.get('pages', 0)
    
    # Foydalanuvchi ma'lumotlarini olish
    user = await get_user_by_tg_id(callback.from_user.id) if callback.from_user else None
    user_name = user.get('full_name', 'Foydalanuvchi') if user else 'Foydalanuvchi'
    
    # Start tarifi uchun maxsus xabar
    if tariff_key == "START":
        # Real bepul buyurtmalar sonini olish
        free_orders = await get_user_free_orders_count(callback.from_user.id)
        remaining_free = 1 - free_orders
        tariff_info = TARIFFS[tariff_key]  # tariff_info ni aniqlash
        
        if remaining_free > 0:
            second_confirmation_text = (
                f"🔒 Ikkinchi tasdiqlash bosqichi\n\n"
                f"Siz bepul obunada {free_orders + 1}-chi buyurtmani amalga oshirmoqdasiz, "
                f"sizda yana {remaining_free - 1} ta bepul taqdimot tayyorlash imkoni qolmoqda!\n\n"
                f"Buyurtmangizni 100% tasdiqlashga imkoningiz komilmi?"
            )
        else:
            second_confirmation_text = (
                f"🔒 Ikkinchi tasdiqlash bosqichi\n\n"
                f"⚠️ Bepul buyurtmalar tugadi! "
                f"Siz allaqachon 1 marta bepul foydalangansiz.\n\n"
                f"Bu buyurtma uchun {pages * tariff_info['price_per_page']:,} so'm to'lashingiz kerak.\n\n"
                f"Buyurtmangizni 100% tasdiqlashga imkoningiz komilmi?"
            )
    else:
        # Premium tariflar uchun
        tariff_info = TARIFFS[tariff_key]
        total_price = pages * tariff_info['price_per_page']
        
        second_confirmation_text = (
            f"💰 To'lov ma'lumotlari:\n\n"
            f"Siz {data['topic']} mavzusida {pages} ta sahifali taqdimot "
            f"buyurtma qilyapsiz va uning narxi "
            f"({pages} × {tariff_info['price_per_page']:,} = {total_price:,} so'm) "
            f"{total_price:,} so'm bo'ldi.\n\n"
            f"❓ Buyurtmani tasdiqlaysizmi?"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_final")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")]
    ])
    
    await callback.message.edit_text(
        second_confirmation_text,
        reply_markup=keyboard,
    )
    await state.set_state(OrderStates.CONFIRM_2)


@dp.callback_query(F.data == "confirm_final")
async def confirm_final_order(callback: types.CallbackQuery, state: FSMContext):
    """Yakuniy tasdiqlash"""
    await callback.answer("🔒 Yakuniy tasdiqlash...")
    
    data = await state.get_data()
    tariff_key = data.get('tariff', '')
    pages = data.get('pages', 0)
    
    if tariff_key == "START":
        # Real bepul buyurtmalar sonini olish
        free_orders = await get_user_free_orders_count(callback.from_user.id)
        remaining_free = 1 - free_orders
        
        if remaining_free > 0:
            final_text = (
                f"🔒 Yakuniy tasdiqlash:\n\n"
                f"Siz buyurtmani tasdiqladingiz, ishonch va xavfsizlik uchun uni yana tasdiqlashingizni "
                f"va bu ishni o'zingiz onli ravishda bajarishingizni so'rayman.\n\n"
                f"Bu sizning {free_orders + 1}-chi bepul buyurtmangiz bo'ladi.\n"
                f"Agar hozir yana bir bor, Ha✅ni bossangiz taqdimot tayyorlash jarayoni boshlanadi.\n\n"
                f"Tanlang:"
            )
        else:
            tariff_info = TARIFFS[tariff_key]
            total_price = pages * tariff_info['price_per_page']
            final_text = (
                f"🔒 Yakuniy tasdiqlash:\n\n"
                f"Siz buyurtmani tasdiqladingiz, ishonch va xavfsizlik uchun uni yana tasdiqlashingizni "
                f"va bu ishni o'zingiz onli ravishda bajarishingizni so'rayman.\n\n"
                f"⚠️ Bepul buyurtmalar tugadi! "
                f"Agar hozir yana bir bor, Ha✅ni bossangiz hisobingizdan "
                f"{total_price:,} so'm mablag' yechib olaman.\n\n"
                f"Tanlang:"
            )
    else:
        # Premium tariflar uchun
        tariff_info = TARIFFS[tariff_key]
        total_price = pages * tariff_info['price_per_page']
        
        final_text = (
            f"🔒 Yakuniy tasdiqlash:\n\n"
            f"Siz buyurtmani tasdiqladingiz, ishonch va xavfsizlik uchun uni yana tasdiqlashingizni "
            f"va bu ishni o'zingiz onli ravishda bajarishingizni so'rayman.\n\n"
            f"Agar hozir yana bir bor, Ha✅ni bossangiz hisobingizdan "
            f"{total_price:,} so'm mablag' yechib olaman.\n\n"
            f"Tanlang:"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="start_generation")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        final_text,
        reply_markup=keyboard,
    )


@dp.callback_query(F.data == "confirm_no")
async def cancel_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Tasdiqni rad etish"""
    await callback.answer("❌ Buyurtma bekor qilindi")
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(
            "❌ Buyurtma bekor qilindi.\n\n"
            "Agar fikringizni o'zgartirsangiz, qaytadan 'Taqdimot tayyorlash' tugmasini bosing.",
            reply_markup=get_back_keyboard(),
        )


@dp.callback_query(F.data == "start_generation")
async def start_presentation_generation(callback: types.CallbackQuery, state: FSMContext):
    """Taqdimot yaratishni boshlash"""
    await callback.answer("🚀 Taqdimot yaratish boshlanmoqda...")
    
    data = await state.get_data()
    tariff_key = data.get('tariff', '')
    pages = data.get('pages', 0)
    
    # Tariff tekshirish
    if not tariff_key or tariff_key not in TARIFFS:
        await callback.message.edit_text(
            "❌ Xatolik: Tariff topilmadi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Barcha tariflar uchun balans tekshirish
    tariff_info = TARIFFS[tariff_key]
    total_price = pages * tariff_info['price_per_page']
    
    # START tarifi uchun bepul buyurtmalar tekshirish
    if tariff_key == "START":
        free_orders = await get_user_free_orders_count(callback.from_user.id)
        remaining_free = 1 - free_orders
        
        # Agar bepul buyurtmalar tugagan bo'lsa, balansdan mablag' yechish
        if remaining_free <= 0:
            # Balansni tekshirish
            balance = await get_user_balance(callback.from_user.id)
            if balance['total_balance'] < total_price:
                # Balans to'ldirish tugmalari
                balance_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu")]
                ])
                
                await callback.message.edit_text(
                    f"❌ Balans yetarli emas!\n\n"
                    f"Bu buyurtma uchun {total_price:,} so'm kerak.\n"
                    f"Sizning balansingiz: {balance['total_balance']:,} so'm\n"
                    f"Yetishmayotgan summa: {total_price - balance['total_balance']:,} so'm\n\n"
                    f"💡 Balansingizni to'ldiring va qaytadan urinib ko'ring!",
                    reply_markup=balance_keyboard,
                )
                return
            
            # Balansdan mablag' yechish
            success = await deduct_user_balance(callback.from_user.id, total_price)
            if not success:
                await callback.message.edit_text(
                    "❌ Balansdan mablag' yechishda xatolik!\n\n"
                    "Iltimos, qaytadan urinib ko'ring.",
                    reply_markup=get_back_keyboard(),
                )
                return
            
            # Tranzaksiya qo'shish
            await add_transaction(
                callback.from_user.id, 
                total_price, 
                'debit', 
                f'START tarifi taqdimot uchun ({pages} sahifa)', 
                None
            )
    else:
        # Boshqa tariflar uchun balans tekshirish
        balance = await get_user_balance(callback.from_user.id)
        if balance['total_balance'] < total_price:
            # Balans to'ldirish tugmalari
            balance_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu")]
            ])
            
            await callback.message.edit_text(
                f"❌ Balans yetarli emas!\n\n"
                f"Bu buyurtma uchun {total_price:,} so'm kerak.\n"
                f"Sizning balansingiz: {balance['total_balance']:,} so'm\n"
                f"Yetishmayotgan summa: {total_price - balance['total_balance']:,} so'm\n\n"
                f"💡 Balansingizni to'ldiring va qaytadan urinib ko'ring!",
                reply_markup=balance_keyboard,
            )
            return
        
        # Balansdan mablag' yechish
        success = await deduct_user_balance(callback.from_user.id, total_price)
        if not success:
            await callback.message.edit_text(
                "❌ Balansdan mablag' yechishda xatolik!\n\n"
                "Iltimos, qaytadan urinib ko'ring.",
                reply_markup=get_back_keyboard(),
            )
            return
        
        # Tranzaksiya qo'shish
        await add_transaction(
            callback.from_user.id, 
            total_price, 
            'debit', 
            f'{tariff_info["name"]} taqdimot uchun ({pages} sahifa)', 
            None
        )
    
    # Buyurtma yaratish
    order_data = {
        'user_tg_id': callback.from_user.id,
        'topic': data['topic'],
        'pages': data['pages'],
        'tariff': data['tariff'],
        'status': 'confirmed'
    }
    
    order_id = await create_order(order_data)
    
    await callback.message.edit_text(
        "🎉 Buyurtma tasdiqlandi!\n\n"
        "🚀 Taqdimot yaratish jarayoni boshlandi...\n"
        "⏱️ Tahmini vaqt: 2-3 daqiqa\n\n"
        "📱 Tayyor bo'lganda sizga xabar beramiz!",
        reply_markup=get_back_keyboard(),
    )
    
    await state.set_state(OnboardingStates.MENU)
    
    # Taqdimot yaratish vazifasini boshlash
    asyncio.create_task(generate_presentation_task(
        callback.from_user.id, order_id, data['topic'], data['pages'], data['tariff']
    ))


@dp.callback_query(F.data == "online_invitation")
async def online_invitation_handler(callback: types.CallbackQuery):
    """Online taklifnoma (QR-kodli)"""
    await callback.answer("📋 Online taklifnoma...")
    
    service_text = (
        "📋 Online taklifnoma (QR-kodli):\n\n"
        "Professional online taklifnomalar tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• To'ylar uchun taklifnoma\n"
        "• Tug'ilgan kun taklifnomasi\n"
        "• Tadbirlar uchun taklifnoma\n"
        "• Korxona tadbirlari\n"
        "• QR-kod bilan\n\n"
        "⏱️ Muddati: 1-3 kun\n"
        "💰 Narx: Taklifnoma turiga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_services")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(service_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "resume")
async def resume_handler(callback: types.CallbackQuery):
    """Rezyume"""
    await callback.answer("📄 Rezyume...")
    
    service_text = (
        "📄 Rezyume tayyorlash:\n\n"
        "Professional va zamonaviy rezyumelar tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Standart rezyume\n"
        "• Kreativ rezyume\n"
        "• IT mutaxassislar uchun\n"
        "• Marketing uchun\n"
        "• PDF va Word formatlarida\n\n"
        "⏱️ Muddati: 1-2 kun\n"
        "💰 Narx: Rezyume turiga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_services")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(service_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "youtube_banner")
async def youtube_banner_handler(callback: types.CallbackQuery):
    """YouTube kanal uchun banner"""
    await callback.answer("🎨 YouTube banner...")
    
    service_text = (
        "🎨 YouTube kanal uchun banner:\n\n"
        "Professional YouTube kanal bannerlarini tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Standart YouTube banner\n"
        "• Kreativ dizayn\n"
        "• Kanal mavzusiga mos\n"
        "• Mobil va desktop uchun\n"
        "• PNG va JPG formatlarida\n\n"
        "⏱️ Muddati: 1-2 kun\n"
        "💰 Narx: Dizayn murakkabligiga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_services")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(service_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "logo_design")
async def logo_design_handler(callback: types.CallbackQuery):
    """Logo tayyorlash"""
    await callback.answer("🎯 Logo dizayn...")
    
    service_text = (
        "🎯 Logo tayyorlash:\n\n"
        "Professional va zamonaviy logolarni tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Korporativ logo\n"
        "• Kichik biznes logo\n"
        "• Start-up logo\n"
        "• Shaxsiy brend logo\n"
        "• Turli formatlarda (PNG, SVG, PDF)\n\n"
        "⏱️ Muddati: 2-5 kun\n"
        "💰 Narx: Logo murakkabligiga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_services")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(service_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "back_to_services")
async def back_to_services(callback: types.CallbackQuery):
    """Boshqa xizmatlar sahifasiga qaytish"""
    await callback.answer("⬅️ Orqaga...")
    
    services_text = (
        "🔧 Boshqa xizmatlar:\n\n"
        "Professional dizayn va yozuv xizmatlarini taklif etamiz!\n\n"
        "Quyidagi xizmatlardan birini tanlang:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Online taklifnoma (QR-kodli)", callback_data="online_invitation")],
        [InlineKeyboardButton(text="📄 Rezyume", callback_data="resume")],
        [InlineKeyboardButton(text="🎨 YouTube kanal uchun banner", callback_data="youtube_banner")],
        [InlineKeyboardButton(text="🎯 Logo tayyorlash", callback_data="logo_design")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(services_text, reply_markup=keyboard, parse_mode="Markdown")




@dp.callback_query(F.data == "course_work")
async def course_work_handler(callback: types.CallbackQuery):
    """Kurs ishi tayyorlash"""
    await callback.answer("🎓 Kurs ishi...")
    
    work_text = (
        "🎓 Kurs ishi tayyorlash:\n\n"
        "Professional kurs ishlarini tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Kurs ishi yozish (15-50 sahifa)\n"
        "• Ilmiy tadqiqot ishlari\n"
        "• Texnik kurs ishlari\n"
        "• Iqtisodiy kurs ishlari\n"
        "• Pedagogik kurs ishlari\n\n"
        "⏱️ Muddati: 3-7 kun\n"
        "💰 Narx: Mavzu va sahifalar soniga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_works")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(work_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "scientific_article")
async def scientific_article_handler(callback: types.CallbackQuery):
    """Ilmiy maqola tayyorlash"""
    await callback.answer("📄 Ilmiy maqola...")
    
    work_text = (
        "📄 Ilmiy maqola tayyorlash:\n\n"
        "Ilmiy va akademik maqolalarni tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Ilmiy maqola yozish\n"
        "• Akademik tadqiqot ishlari\n"
        "• Konferensiya maqolalari\n"
        "• Jurnal uchun maqolalar\n"
        "• Ilmiy tezis yozish\n\n"
        "⏱️ Muddati: 5-10 kun\n"
        "💰 Narx: Mavzu va hajmga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_works")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(work_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "essay")
async def essay_handler(callback: types.CallbackQuery):
    """Referat tayyorlash"""
    await callback.answer("📚 Referat...")
    
    work_text = (
        "📚 Referat tayyorlash:\n\n"
        "Har qanday mavzu bo'yicha referatlarni tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Akademik referatlar\n"
        "• Ilmiy referatlar\n"
        "• Mavzu referatlar\n"
        "• Tadqiqot referatlar\n"
        "• Xulosa referatlar\n\n"
        "⏱️ Muddati: 2-5 kun\n"
        "💰 Narx: Sahifalar soniga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_works")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(work_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "independent_work")
async def independent_work_handler(callback: types.CallbackQuery):
    """Mustaqil ish tayyorlash"""
    await callback.answer("📋 Mustaqil ish...")
    
    work_text = (
        "📋 Mustaqil ish tayyorlash:\n\n"
        "Turli yo'nalishlardagi mustaqil ishlarni tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Akademik mustaqil ishlar\n"
        "• Ilmiy mustaqil ishlar\n"
        "• Amaliy mustaqil ishlar\n"
        "• Tadqiqot mustaqil ishlar\n"
        "• Yaratuvchilik ishlar\n\n"
        "⏱️ Muddati: 3-7 kun\n"
        "💰 Narx: Ish turi va hajmga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_works")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(work_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "report")
async def report_handler(callback: types.CallbackQuery):
    """Hisobot tayyorlash"""
    await callback.answer("📊 Hisobot...")
    
    work_text = (
        "📊 Hisobot tayyorlash:\n\n"
        "Professional hisobotlarni tayyorlab beramiz!\n\n"
        "📋 Xizmatlar:\n"
        "• Tadqiqot hisobotlari\n"
        "• Amaliy hisobotlar\n"
        "• Ish hisobotlari\n"
        "• Statistika hisobotlari\n"
        "• Analiz hisobotlari\n\n"
        "⏱️ Muddati: 2-5 kun\n"
        "💰 Narx: Hisobot turi va hajmga qarab\n\n"
        "📞 Buyurtma uchun admin bilan bog'laning:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Admin bilan bog'lanish", url="https://t.me/preuzadmin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_works")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(work_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "back_to_works")
async def back_to_works(callback: types.CallbackQuery):
    """Mustaqil ishlar sahifasiga qaytish"""
    await callback.answer("⬅️ Orqaga...")
    
    works_text = (
        "📝 Mustaqil ishlar tayyorlash:\n\n"
        "Professional mustaqil ishlarni tayyorlab beramiz!\n\n"
        "Quyidagi xizmatlardan birini tanlang:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Kurs ishi tayyorlash", callback_data="course_work")],
        [InlineKeyboardButton(text="📄 Ilmiy maqola tayyorlash", callback_data="scientific_article")],
        [InlineKeyboardButton(text="📚 Referat tayyorlash", callback_data="essay")],
        [InlineKeyboardButton(text="📋 Mustaqil ish tayyorlash", callback_data="independent_work")],
        [InlineKeyboardButton(text="📊 Hisobot tayyorlash", callback_data="report")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(works_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "top_up_balance")
async def top_up_balance(callback: types.CallbackQuery):
    """Balansni to'ldirish"""
    await callback.answer("💳 Balansni to'ldirish...")
    
    payment_text = (
        "💳 **Balansni to'ldirish**\n\n"
        "Quyidagi usullar orqali balansingizni to'ldirishingiz mumkin:\n\n"
        "🔹 Naqt to'lov:\n"
        "• Uzcard: 5614682110523232\n"
        "• Humo: 9860170104108668\n"
        "• VISA: 4023060518185649\n\n"
        "🔹 Elektron to'lov:\n"
        "• Payme\n"
        "• Click\n"
        "• Uzcard Mobile\n\n"
        "💡 Eslatma: To'lov amalga oshirgandan so'ng, "
        "chek rasmini yuboring va balansingiz 5-10 daqiqada to'ldiriladi."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 CLICK orqali to'lov", callback_data="click_payment")],
        [InlineKeyboardButton(text="📷 Chek yuborish", callback_data="send_receipt")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(payment_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "click_payment")
async def click_payment_menu(callback: types.CallbackQuery):
    """CLICK orqali to'lov menyusi"""
    await callback.answer("💳 CLICK to'lov...")
    
    text = (
        "💳 **CLICK orqali to'lov**\n\n"
        "Balansingizni to'ldirish uchun miqdorni tanlang:\n\n"
        "💰 **Mavjud to'lov miqdorlari:**"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5,000 so'm", callback_data="click_amount_5000")],
        [InlineKeyboardButton(text="10,000 so'm", callback_data="click_amount_10000")],
        [InlineKeyboardButton(text="20,000 so'm", callback_data="click_amount_20000")],
        [InlineKeyboardButton(text="50,000 so'm", callback_data="click_amount_50000")],
        [InlineKeyboardButton(text="100,000 so'm", callback_data="click_amount_100000")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="top_up_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("click_amount_"))
async def process_click_payment(callback: types.CallbackQuery):
    """CLICK to'lovni qayta ishlash"""
    amount_str = callback.data.replace("click_amount_", "")
    amount = int(amount_str)
    
    await callback.answer(f"💳 {amount:,} so'm to'lov...")
    
    # Click to'lov uchun ma'lumotlar
    user_id = callback.from_user.id
    username = callback.from_user.username or "Noma'lum"
    
    # Click to'lov havolasini yaratish (bu yerda real Click API ishlatiladi)
    click_payment_url = f"https://my.click.uz/pay/{user_id}_{amount}_{int(datetime.now().timestamp())}"
    
    text = (
        f"💳 **CLICK to'lov - {amount:,} so'm**\n\n"
        f"👤 **Foydalanuvchi:** @{username}\n"
        f"💰 **Miqdor:** {amount:,} so'm\n"
        f"🆔 **ID:** {user_id}\n\n"
        f"🔗 **To'lov havolasi:**\n"
        f"`{click_payment_url}`\n\n"
        f"📱 **To'lov qilish uchun:**\n"
        f"1. Havolani bosib o'ting\n"
        f"2. Click ilovasida to'lov qiling\n"
        f"3. To'lov muvaffaqiyatli bo'lgandan so'ng, bot avtomatik ravishda balansingizni to'ldiradi\n\n"
        f"⏰ **Eslatma:** To'lov 5-10 daqiqada qayta ishlanadi"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 To'lov qilish", url=click_payment_url)],
        [InlineKeyboardButton(text="🔄 To'lov holatini tekshirish", callback_data=f"check_payment_{user_id}_{amount}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="click_payment")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_click_payment_status(callback: types.CallbackQuery):
    """CLICK to'lov holatini tekshirish"""
    parts = callback.data.split("_")
    user_id = parts[2]
    amount = int(parts[3])
    
    await callback.answer("🔄 To'lov holatini tekshirish...")
    
    # Bu yerda real Click API orqali to'lov holatini tekshirish kerak
    # Hozircha demo uchun random natija qaytaramiz
    import random
    is_paid = random.choice([True, False])
    
    if is_paid:
        # To'lov muvaffaqiyatli bo'lsa, balansni to'ldirish
        current_balance = await get_user_balance(user_id)
        new_balance = current_balance + amount
        await update_user_balance(user_id, new_balance)
        
        text = (
            f"✅ **To'lov muvaffaqiyatli!**\n\n"
            f"💰 **To'ldirilgan miqdor:** {amount:,} so'm\n"
            f"💳 **Joriy balans:** {new_balance:,} so'm\n\n"
            f"🎉 Balansingiz muvaffaqiyatli to'ldirildi!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Balansim", callback_data="my_balance")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]
        ])
    else:
        text = (
            f"⏳ **To'lov hali qayta ishlanmagan**\n\n"
            f"💰 **Miqdor:** {amount:,} so'm\n\n"
            f"📱 Iltimos, to'lovni tugatgandan so'ng yana urinib ko'ring.\n"
            f"⏰ To'lov 5-10 daqiqada qayta ishlanadi."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Qayta tekshirish", callback_data=f"check_payment_{user_id}_{amount}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="click_payment")]
        ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "send_receipt")
async def send_receipt_menu(callback: types.CallbackQuery, state: FSMContext):
    """Chek yuborish menyusi"""
    await callback.answer("📷 Chek yuborish...")
    
    receipt_text = (
        "📷 Chek yuborish\n\n"
        "To'lov chekini yuboring:\n\n"
        "📋 Talablar:\n"
        "• Rasm aniq va o'qiladigan bo'lishi kerak\n"
        "• To'lov summasi va vaqti ko'rinishi kerak\n"
        "• Chek to'liq ko'rinishi kerak\n\n"
        "Tez orada balansingiz to'ldiriladi"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_receipt")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        try:
            await callback.message.edit_text(receipt_text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            await callback.message.answer(receipt_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.answer(receipt_text, reply_markup=keyboard, parse_mode="Markdown")
    
    await state.set_state(OnboardingStates.RECEIPT_FIRST)

@dp.message(StateFilter(OnboardingStates.RECEIPT_FIRST), F.photo)
async def process_first_receipt(message: types.Message, state: FSMContext):
    """Birinchi chekni qayta ishlash"""
    if not message.from_user:
        return
    
    # Birinchi chekni saqlash
    first_photo = message.photo[-1]
    await state.update_data(first_receipt=first_photo.file_id)
    
    # Bekor qilish tugmasi
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_receipt")]
    ])
    
    # Ikkinchi chek so'rash
    await message.answer(
        "Iltimos, haqiqiy chekni yuboring qaytadan!\n\n"
        "📷 Chekni qayta yuboring:",
        reply_markup=cancel_keyboard
    )
    await state.set_state(OnboardingStates.RECEIPT_SECOND)

@dp.message(StateFilter(OnboardingStates.RECEIPT_SECOND), F.photo)
async def process_second_receipt(message: types.Message, state: FSMContext):
    """Ikkinchi chekni qayta ishlash"""
    if not message.from_user:
        return
    
    # Ikkinchi chekni saqlash
    second_photo = message.photo[-1]
    data = await state.get_data()
    first_receipt = data.get('first_receipt')
    
    # Admin guruhga yuborish
    admin_group_id = int(os.getenv("ADMIN_GROUP_ID", "-1001234567890"))  # Admin guruh ID
    
    try:
        # Bitta xabarda 2 ta chek yuborish
        media_group = [
            types.InputMediaPhoto(
                media=first_receipt,
                caption=f"📷 To'lov cheklari\n\n"
                       f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
                       f"🆔 ID: {message.from_user.id}\n"
                       f"📅 Vaqt: {format_time()}\n\n"
                       f"📷 Birinchi chek",
            ),
            types.InputMediaPhoto(
                media=second_photo.file_id,
                caption="📷 Ikkinchi chek",
            )
        ]
        
        await bot.send_media_group(
            chat_id=admin_group_id,
            media=media_group
        )
        
        # Qo'shimcha izoh yuborish
        await bot.send_message(
            chat_id=admin_group_id,
            text=f"📋 To'lov ma'lumotlari:\n\n"
                 f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
                 f"🆔 ID: {message.from_user.id}\n"
                 f"📅 Vaqt: {format_time()}\n"
                 f"📷 Cheklar: 2 ta rasm yuborildi\n\n"
                 f"💡 Eslatma: To'lovni tekshirib, balansni to'ldiring",
        )
        
        # Foydalanuvchiga javob
        await message.answer(
            "✅ To'lovingiz tekshirib chiqilmoqda tez orada tasdiqlanadi",
            reply_markup=get_main_keyboard(),
        )
        
        # Log qilish
        await log_action(message.from_user.id, "receipt_sent", {
            'first_receipt': first_receipt,
            'second_receipt': second_photo.file_id,
            'sent_to_group': admin_group_id
        })
        
    except Exception as e:
        await message.answer(
            f"❌ Chek yuborishda xatolik!\n\n"
            f"Xatolik: {str(e)}\n\n"
            f"Qaytadan urinib ko'ring yoki @support_admin ga murojaat qiling.",
            reply_markup=get_main_keyboard(),
        )
    
    await state.set_state(OnboardingStates.MENU)

@dp.message(StateFilter(OnboardingStates.RECEIPT_SECOND))
async def handle_non_photo_receipt(message: types.Message, state: FSMContext):
    """RECEIPT_SECOND holatida rasm bo'lmagan narsalar uchun"""
    if not message.from_user:
        return
    
    # Bekor qilish tugmasi
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_receipt")]
    ])
    
    await message.answer(
        "❌ Faqat rasm yuboring!\n\n"
        "📷 Chekni rasm ko'rinishida yuboring yoki bekor qiling:",
        reply_markup=cancel_keyboard
    )

@dp.callback_query(F.data == "cancel_receipt")
async def cancel_receipt_handler(callback: types.CallbackQuery, state: FSMContext):
    """Chek yuborishni bekor qilish"""
    await callback.message.edit_text(
        "❌ Chek yuborish bekor qilindi",
    )
    await state.set_state(OnboardingStates.MENU)
    await callback.answer()

@dp.callback_query(F.data == "referral_link")
async def get_referral_link(callback: types.CallbackQuery):
    """Referral link olish"""
    await callback.answer("👥 Referral link...")
    
    if not callback.from_user:
        return
    
    # Referral statistikasini olish
    referral_stats = await get_referral_stats(callback.from_user.id)
    
    # Referral bonuslarini olish
    rewards = await get_referral_rewards()
    
    # Referral link yaratish
    referral_link = f"https://t.me/preuz_bot?start=ref_{callback.from_user.id}"
    
    referral_text = (
        "👥 Do'stlarni taklif qilish:\n\n"
        f"Do'stlaringizni taklif qiling va har bir taklif uchun {rewards['referrer_reward']:,} so'm bonus oling!\n\n"
        f"🔗 Sizning taklif havolangiz:\n"
        f"`{referral_link}`\n\n"
        f"📊 Joriy natijalar:\n"
        f"• Umumiy takliflar: {referral_stats['total_referrals']} ta\n"
        f"• Tasdiqlangan: {referral_stats['confirmed_referrals']} ta\n"
        f"• Jami bonus: {referral_stats['total_bonus']:,} so'm\n\n"
        "📋 Qanday ishlaydi:\n"
        "1. Havolani do'stlaringizga yuboring\n"
        "2. Do'stingiz bot orqali ro'yxatdan o'tadi\n"
        f"3. Sizga {rewards['referrer_reward']:,} so'm bonus qo'shiladi\n"
        f"4. Do'stingiz ham {rewards['referred_reward']:,} so'm bonus oladi\n\n"
        "💡 Maslahat: Ko'proq do'st taklif qiling va ko'proq bonus oling!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Havolani yuborish", url=f"https://t.me/share/url?url={referral_link}&text=PresentatsiyaUz boti orqali taqdimotlar tayyorlang!")],
        [InlineKeyboardButton(text="📊 Statistikani ko'rish", callback_data="referral_stats")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(referral_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: types.CallbackQuery):
    """Referral statistikasini ko'rsatish"""
    await callback.answer("📊 Statistikani ko'rish...")
    
    if not callback.from_user:
        return
    
    # Real referral statistikasini olish
    referral_stats = await get_referral_stats(callback.from_user.id)
    
    stats_text = (
        "📊 Referral statistikasi:\n\n"
        f"👥 Umumiy takliflar: {referral_stats['total_referrals']} ta\n"
        f"✅ Tasdiqlangan: {referral_stats['confirmed_referrals']} ta\n"
        f"⏳ Kutilayotgan: {referral_stats['pending_referrals']} ta\n"
        f"💰 Jami bonus: {referral_stats['total_bonus']:,} so'm\n"
        f"📅 Bu oy: {referral_stats['this_month']} ta taklif\n\n"
        f"💡 Maslahat: Har hafta kamida 3 ta do'st taklif qiling!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="referral_stats")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(stats_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "top_up_balance")
async def top_up_balance_handler(callback: types.CallbackQuery, state: FSMContext):
    """Balans to'ldirish"""
    await callback.answer("💳 Balans to'ldirish...")
    
    if not callback.from_user:
        return
    
    balance_text = (
        "Balansni to'ldirish:\n\n"
        "Quyidagi usullar orqali balansingizni to'ldirishingiz mumkin:\n\n"
        "Naqt to'lov:\n"
        "• Uzcard: 5614682110523232\n"
        "• Humo: 9860170104108668\n"
        "• VISA: 4023060518185649\n\n"
        "Elektron to'lov:\n"
        "• Payme\n"
        "• Click\n"
        "• Uzcard Mobile\n\n"
        "Eslatma: To'lov amalga oshirgandan so'ng, chek rasmini yuboring va balansingiz 5-10 daqiqada to'ldiriladi."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Chek yuborish", callback_data="send_receipt")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(balance_text, reply_markup=keyboard)

@dp.callback_query(F.data == "send_receipt")
async def send_receipt_handler(callback: types.CallbackQuery, state: FSMContext):
    """Chek yuborish"""
    await callback.answer("📷 Chek yuborish...")
    
    if not callback.from_user:
        return
    
    receipt_text = (
        "Chek yuborish:\n\n"
        "Iltimos, faqat skrinshot rasmni yuboring. Boshqasi qabul qilinmaydi.\n\n"
        "Chek yuborish uchun rasmni yuboring:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_receipt")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(receipt_text, reply_markup=keyboard)
    
    await state.set_state(OnboardingStates.RECEIPT_FIRST)

@dp.callback_query(F.data == "cancel_receipt")
async def cancel_receipt_handler(callback: types.CallbackQuery, state: FSMContext):
    """Chek yuborishni bekor qilish"""
    await callback.answer("❌ Chek yuborish bekor qilindi!")
    await state.set_state(OnboardingStates.MENU)
    
    # Asosiy menyuga qaytish
    menu_text = (
        "Xush kelibsiz!\n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Taqdimot tayyorlash", callback_data="create_presentation")],
        [InlineKeyboardButton(text="💰 Balansim", callback_data="my_balance")],
        [InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referral_link")],
        [InlineKeyboardButton(text="📞 Aloqa", callback_data="contact_us")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(menu_text, reply_markup=keyboard)

@dp.message(StateFilter(OnboardingStates.RECEIPT_FIRST), F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    """Chek rasmini qabul qilish"""
    await message.answer(
        "✅ Chek qabul qilindi!\n\n"
        "Admin tez orada sizning balansingizni to'ldiradi.\n"
        "Balans yangilanishi haqida xabar beramiz.",
        reply_markup=get_main_keyboard()
    )
    await state.set_state(OnboardingStates.MENU)

@dp.message(StateFilter(OnboardingStates.RECEIPT_FIRST))
async def process_receipt_other(message: types.Message, state: FSMContext):
    """Chek bo'lmagan narsa yuborilganda"""
    await message.answer(
        "❌ Iltimos, faqat skrinshot rasmni yuboring!\n\n"
        "Boshqa narsalar qabul qilinmaydi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_receipt")]
        ])
    )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await callback.answer("🏠 Asosiy menyuga qaytish...")
    await state.set_state(OnboardingStates.MENU)
    
    # Asosiy menyu matnini yuborish
    menu_text = (
        "🎉 Xush kelibsiz!\n\n"
        "🤖 @preuz_bot - professional taqdimotlar yaratish uchun!\n\n"
        "📋 Xizmatlar:\n"
        "• 🎯 Taqdimot yaratish\n"
        "• 📊 Hisobot tayyorlash\n"
        "• 💰 Balans boshqarish\n"
        "• 👥 Do'stlarni taklif qilish\n\n"
        "🚀 Boshlash uchun tugmalardan birini tanlang!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Taqdimot yaratish", callback_data="create_presentation")],
        [InlineKeyboardButton(text="💰 Balansim", callback_data="my_balance")],
        [InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referral_link")],
        [InlineKeyboardButton(text="📞 Aloqa", callback_data="contact_us")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(menu_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "create_presentation")
async def create_presentation_callback(callback: types.CallbackQuery, state: FSMContext):
    """Taqdimot yaratish callback handler"""
    await callback.answer("📊 Taqdimot tayyorlash...")
    
    # Taqdimot tayyorlashni boshlash
    await callback.message.edit_text(
        "📊 Taqdimot tayyorlash xizmati:\n\n"
        "AI yordamida professional taqdimotlar tayyorlab beramiz!\n\n"
        "Quyidagi tariflardan birini tanlang:",
        reply_markup=get_tariff_keyboard()
    )

@dp.callback_query(F.data == "back_to_balance")
async def back_to_balance(callback: types.CallbackQuery):
    """Balans sahifasiga qaytish"""
    await callback.answer("⬅️ Balansga qaytish...")
    
    if not callback.from_user:
        return
    
    # Real balans ma'lumotlarini olish
    balance = await get_user_balance(callback.from_user.id)
    referral_stats = await get_referral_stats(callback.from_user.id)
    
    balance_text = (
        f"💰 Sizning balansingiz:\n\n"
        f"💳 Umumiy balans: {balance['total_balance']:,} so'm\n\n"
        f"📊 Balans tafsilotlari:\n"
        f"• Naqt orqali to'langan: {balance['cash_balance']:,} so'm\n"
        f"• {referral_stats['confirmed_referrals']} ta taklif uchun: {balance['referral_balance']:,} so'm"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
        [InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referral_link")],
        [InlineKeyboardButton(text="📊 Referral statistikasi", callback_data="referral_stats")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(balance_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "send_receipt")
async def send_receipt(callback: types.CallbackQuery):
    """Chek yuborish"""
    await callback.answer("📸 Chek yuborish...")
    
    receipt_text = (
        "📸 Chek yuborish:\n\n"
        "To'lov cheki rasmini yuboring va quyidagi ma'lumotlarni ko'rsating:\n\n"
        "🔹 Kerakli ma'lumotlar:\n"
        "• To'lov summasi\n"
        "• To'lov sanasi va vaqti\n"
        "• Karta raqami (oxirgi 4 ta raqam)\n\n"
        "⏱️ Tekshirish vaqti: 5-10 daqiqa\n"
        "✅ Tasdiqlangandan so'ng: Balansingiz avtomatik to'ldiriladi\n\n"
        "💡 Eslatma: Faqat aniq va o'qiladigan rasmlarni yuboring."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="top_up_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(receipt_text, reply_markup=keyboard, parse_mode="Markdown")


async def generate_presentation_task(user_tg_id: int, order_id: int, topic: str, pages: int, tariff: str):
    """Taqdimot yaratish vazifasi - yangi struktura"""
    try:
        # OpenAI dan kontent olish
        content = await generate_presentation_content(topic, pages)
        print(f"ChatGPT dan kontent olindi: {content}")
        
        # PowerPoint fayl yaratish - yangi funksiya
        from pptx_generator import create_presentation_file
        files = await create_presentation_file(topic, pages, tariff)
        file_path = files[0]  # PowerPoint fayl birinchi o'rinda
        
        # Ma'lumotlar bazasiga saqlash
        presentation_data = {
            'user_tg_id': user_tg_id,
            'order_id': order_id,
            'topic': topic,
            'pages': pages,
            'tariff': tariff,
            'file_path': file_path,
            'status': 'completed'
        }
        
        await save_presentation(presentation_data)
        await update_order_status(order_id, 'completed')
        
        # Foydalanuvchiga fayl yuborish
        from aiogram.types import FSInputFile
        
        input_file = FSInputFile(file_path, filename=f"taqdimot_{topic.replace(' ', '_')}.pptx")
        await bot.send_document(
            chat_id=user_tg_id,
            document=input_file,
            caption=f"🎉 Taqdimot tayyor!\n\n"
                   f"📊 Mavzu: {topic}\n"
                   f"📄 Sahifalar: {pages}\n"
                   f"💰 Tarif: {TARIFFS[tariff]['name']}\n\n"
                   f"✅ Fayl muvaffaqiyatli yaratildi!",
        )
        
        # Admin guruhga taqdimot haqida xabar yuborish
        await send_presentation_to_admin_group(user_tg_id, topic, pages, tariff, file_path)
        
        # Log yaratish
        await log_action(user_tg_id, "presentation_generated", {
            'topic': topic,
            'pages': pages,
            'tariff': tariff,
            'file_path': file_path
        })
        
        # Barcha fayllarni o'chirish (foydalanuvchiga yuborilgandan keyin)
        try:
            for file_path in files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"File deleted after sending: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting files: {e}")
        
    except Exception as e:
        # Xatolik holatida foydalanuvchiga xabar berish
        print(f"Taqdimot yaratishda xatolik: {e}")
        logging.error(f"Taqdimot yaratishda xatolik: {e}")
        
        await bot.send_message(
            chat_id=user_tg_id,
            text=f"❌ Xatolik yuz berdi!\n\n"
                 f"Taqdimot yaratishda muammo bo'ldi. Iltimos, qaytadan urinib ko'ring.\n\n"
                 f"📞 Agar muammo davom etsa, qo'llab-quvvatlashga murojaat qiling.\n\n"
                 f"🔍 Xatolik tafsiloti: {str(e)[:100]}...",
        )
        
        # Xatolikni log qilish
        await log_action(user_tg_id, "presentation_error", {
            'error': str(e),
            'topic': topic,
            'pages': pages,
            'tariff': tariff
        })
        
        # Buyurtma holatini yangilash
        await update_order_status(order_id, 'failed')


# Admin funksiyalari
@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📢 Ommaviy xabar")
async def broadcast_menu(message: types.Message, state: FSMContext):
    """Ommaviy xabar menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    # Bekor qilish tugmasi
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])
    
    await message.answer(
        "📢 Ommaviy xabar yuborish\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring:",
        reply_markup=cancel_keyboard
    )
    await state.set_state(OnboardingStates.BROADCAST_MESSAGE)

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
    await state.set_state(OnboardingStates.MENU)

# Ommaviy xabar yuborish funksiyasi
@dp.message(StateFilter(OnboardingStates.BROADCAST_MESSAGE))
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Ommaviy xabarni qayta ishlash"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        # Barcha foydalanuvchilarni olish
        users = await get_all_users()
        total_users = len(users)
        success_count = 0
        failed_count = 0
        
        # Boshlash xabarini yuborish
        progress_msg = await message.answer(
            f"📢 Ommaviy xabar yuborilmoqda...\n\n"
            f"📊 Jami foydalanuvchilar: {total_users} ta\n"
            f"✅ Yuborildi: 0 ta\n"
            f"❌ Xatolik: 0 ta\n"
            f"⏳ Qoldi: {total_users} ta",
        )
        
        # Xabarni yuborish
        for i, user in enumerate(users, 1):
            try:
                # Agar xabar matn bo'lsa
                if message.text:
                    await bot.send_message(
                        chat_id=int(user['user_id']),
                        text=message.text if "" in message.text else None
                    )
                # Agar xabar forward qilingan bo'lsa
                elif message.forward_from or message.forward_from_chat:
                    await bot.forward_message(
                        chat_id=int(user['user_id']),
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                # Agar xabar rasm bo'lsa
                elif message.photo:
                    await bot.send_photo(
                        chat_id=int(user['user_id']),
                        photo=message.photo[-1].file_id,
                        caption=message.caption if message.caption else None
                    )
                # Agar xabar video bo'lsa
                elif message.video:
                    await bot.send_video(
                        chat_id=int(user['user_id']),
                        video=message.video.file_id,
                        caption=message.caption if message.caption else None
                    )
                # Agar xabar hujjat bo'lsa
                elif message.document:
                    await bot.send_document(
                        chat_id=int(user['user_id']),
                        document=message.document.file_id,
                        caption=message.caption if message.caption else None
                    )
                # Boshqa holatda
                else:
                    await bot.copy_message(
                        chat_id=int(user['user_id']),
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                
                success_count += 1
                
                # Har 10 ta xabardan keyin progress yangilash
                if i % 10 == 0 or i == total_users:
                    remaining = total_users - i
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_msg.message_id,
                        text=f"📢 Ommaviy xabar yuborilmoqda...\n\n"
                             f"📊 Jami foydalanuvchilar: {total_users} ta\n"
                             f"✅ Yuborildi: {success_count} ta\n"
                             f"❌ Xatolik: {failed_count} ta\n"
                             f"⏳ Qoldi: {remaining} ta",
                    )
                
                await asyncio.sleep(0.1)  # Rate limiting uchun
            except (TelegramBadRequest, Exception) as e:
                failed_count += 1
                logging.error(f"Xabar yuborishda xatolik {user['user_id']}: {e}")
        
        # Yakuniy natijani ko'rsatish
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=progress_msg.message_id,
            text=f"📢 Ommaviy xabar yuborildi!\n\n"
                 f"✅ Muvaffaqiyatli: {success_count} ta\n"
                 f"❌ Bloklaganlar: {failed_count} ta\n"
                 f"📊 Jami: {total_users} ta foydalanuvchi",
        )
        
        await message.answer(
            "✅ Ommaviy xabar muvaffaqiyatli yakunlandi!",
            reply_markup=get_admin_keyboard()
        )
        
        # Log qilish
        await log_action(message.from_user.id, "admin_broadcast_sent", {
            'success_count': success_count,
            'failed_count': failed_count,
            'total_users': len(users)
        })
        
    except Exception as e:
        await message.answer(
            f"❌ Xabar yuborishda xatolik!\n\n"
            f"Xatolik: {str(e)}",
            reply_markup=get_admin_keyboard(),
        )
    
    await state.set_state(OnboardingStates.MENU)

# Bekor qilish tugmasi
@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
    """Ommaviy xabarni bekor qilish"""
    if not await is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "❌ Ommaviy xabar bekor qilindi",
    )
    await state.set_state(OnboardingStates.MENU)
    await callback.answer()

# Bir kishiga xabar bekor qilish
@dp.callback_query(F.data == "cancel_user_message")
async def cancel_user_message_handler(callback: types.CallbackQuery, state: FSMContext):
    """Bir kishiga xabarni bekor qilish"""
    if not await is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "❌ Bir kishiga xabar bekor qilindi",
    )
    await state.set_state(OnboardingStates.MENU)
    await callback.answer()

# Bir kishiga xabar yuborish
@dp.message(StateFilter(OnboardingStates.MENU), F.text == "💬 Bir kishiga xabar")
async def send_to_user_menu(message: types.Message, state: FSMContext):
    """Bir kishiga xabar menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    # Bekor qilish tugmasi
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_user_message")]
    ])
    
    await message.answer(
        "💬 Bir kishiga xabar yuborish\n\n"
        "Foydalanuvchi ID sini kiriting:",
        reply_markup=cancel_keyboard
    )
    await state.set_state(OnboardingStates.USER_ID_INPUT)

@dp.message(StateFilter(OnboardingStates.USER_ID_INPUT))
async def process_user_id(message: types.Message, state: FSMContext):
    """Foydalanuvchi ID ni qayta ishlash"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_tg_id(user_id)
        
        if user:
            await state.update_data(target_user_id=user_id)
            
            # Bekor qilish tugmasi
            cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_user_message")]
            ])
            
            full_name = user.get('name', 'Noma\'lum')
            username = user.get('username', 'Noma\'lum')
            created_at = user.get('created_at', 'Noma\'lum')
            
            await message.answer(
                f"✅ Foydalanuvchi topildi!\n\n"
                f"👤 Ism: {full_name}\n"
                f"📱 Username: @{username}\n"
                f"📅 Qo'shilgan: {created_at}\n\n"
                f"Yubormoqchi bo'lgan xabaringizni yuboring:",
                reply_markup=cancel_keyboard
            )
            await state.set_state(OnboardingStates.USER_MESSAGE)
        else:
            await message.answer(
                "❌ Foydalanuvchi topilmadi!\n\n"
                "To'g'ri ID kiriting yoki qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(OnboardingStates.MENU)
            
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri ID format!\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(OnboardingStates.MENU)

@dp.message(StateFilter(OnboardingStates.USER_MESSAGE))
async def process_user_message(message: types.Message, state: FSMContext):
    """Foydalanuvchiga xabarni yuborish"""
    if not await is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    
    try:
        # Agar xabar matn bo'lsa
        if message.text:
            await bot.send_message(
                chat_id=target_user_id,
                text=message.text if "" in message.text else None
            )
        # Agar xabar forward qilingan bo'lsa
        elif message.forward_from or message.forward_from_chat:
            await bot.forward_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        # Agar xabar rasm bo'lsa
        elif message.photo:
            await bot.send_photo(
                chat_id=target_user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption if message.caption else None
            )
        # Agar xabar video bo'lsa
        elif message.video:
            await bot.send_video(
                chat_id=target_user_id,
                video=message.video.file_id,
                caption=message.caption if message.caption else None
            )
        # Agar xabar hujjat bo'lsa
        elif message.document:
            await bot.send_document(
                chat_id=target_user_id,
                document=message.document.file_id,
                caption=message.caption if message.caption else None
            )
        # Boshqa holatda
        else:
            await bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        
        await message.answer(
            f"✅ Xabar muvaffaqiyatli yuborildi!\n\n"
            f"👤 Foydalanuvchi ID: {target_user_id}",
            reply_markup=get_admin_keyboard(),
        )
        
        # Log qilish
        await log_action(message.from_user.id, "admin_message_sent", {
            'target_user_id': target_user_id,
            'message_type': 'text' if message.text else 'media'
        })
        
    except Exception as e:
        await message.answer(
            f"❌ Xabar yuborishda xatolik!\n\n"
            f"Xatolik: {str(e)}",
            reply_markup=get_admin_keyboard(),
        )
    
    await state.set_state(OnboardingStates.MENU)

@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📊 Statistika")
async def admin_statistics(message: types.Message):
    """Admin statistika"""
    if not await is_admin(message.from_user.id):
        return
    
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
        
        current_time = format_time()
        stats_text = (
            f"📊 Umumiy statistika\n\n"
            f"👥 Jami foydalanuvchilar: {total_users:,}\n"
            f"✅ Faol foydalanuvchilar: {active_users:,}\n"
            f"🚫 Blok qilinganlar: {blocked_users:,}\n"
            f"📈 Faollik darajasi: {(active_users/total_users*100):.1f}%\n\n"
            f"🕐 Oxirgi yangilanish: {current_time}"
        )
        
        await message.answer(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(
            f"❌ Statistika olishda xatolik!\n\n"
            f"Xatolik: {str(e)}",
        )

@dp.message(StateFilter(OnboardingStates.MENU), F.text == "💰 Balans boshqarish")
async def balance_management_menu(message: types.Message, state: FSMContext):
    """Balans boshqarish menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    # Bekor qilish tugmasi
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_balance")]
    ])
    
    await message.answer(
        "💰 Balans boshqarish\n\n"
        "Foydalanuvchi ID sini kiriting:",
        reply_markup=cancel_keyboard
    )
    await state.set_state(OnboardingStates.BALANCE_USER_ID)

@dp.message(StateFilter(OnboardingStates.BALANCE_USER_ID))
async def process_balance_user_id(message: types.Message, state: FSMContext):
    """Balans boshqarish uchun foydalanuvchi ID ni qayta ishlash"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_tg_id(user_id)
        
        if user:
            balance = await get_user_balance(user_id)
            await state.update_data(target_user_id=user_id)
            
            # Balans boshqarish tugmalari
            balance_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Balans qo'shish", callback_data="add_balance")],
                [InlineKeyboardButton(text="➖ Balans kamaytirish", callback_data="subtract_balance")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_balance")]
            ])
            
            full_name = user.get('name', 'Noma\'lum')
            username = user.get('username', 'Noma\'lum')
            
            await message.answer(
                f"👤 Foydalanuvchi: {full_name}\n"
                f"📱 Username: @{username}\n"
                f"💳 Joriy balans: {balance['total_balance']:,} so'm\n\n"
                f"Balans boshqarish uchun amalni tanlang:",
                reply_markup=balance_keyboard
            )
            await state.set_state(OnboardingStates.BALANCE_ACTION)
        else:
            await message.answer(
                "❌ Foydalanuvchi topilmadi!\n\n"
                "To'g'ri ID kiriting yoki qaytadan urinib ko'ring:",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(OnboardingStates.MENU)
            
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri ID format!\n\n"
            "Faqat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(OnboardingStates.MENU)

@dp.callback_query(F.data.in_(["add_balance", "subtract_balance"]))
async def balance_action_handler(callback: types.CallbackQuery, state: FSMContext):
    """Balans amalini tanlash"""
    if not await is_admin(callback.from_user.id):
        return
    
    action = "qo'shish" if callback.data == "add_balance" else "kamaytirish"
    emoji = "➕" if callback.data == "add_balance" else "➖"
    
    await callback.message.edit_text(
        f"{emoji} Balans {action}\n\n"
        f"Qancha so'm {action}ni kiriting:",
    )
    
    await state.update_data(balance_action=callback.data)
    await state.set_state(OnboardingStates.BALANCE_AMOUNT)
    await callback.answer()

@dp.message(StateFilter(OnboardingStates.BALANCE_AMOUNT))
async def process_balance_amount(message: types.Message, state: FSMContext):
    """Balans miqdorini qayta ishlash"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError("Miqdor musbat bo'lishi kerak")
        
        data = await state.get_data()
        user_id = data.get('target_user_id')
        action = data.get('balance_action')
        
        if action == "add_balance":
            success = await update_user_balance(user_id, amount, 'cash')
            if success:
                action_text = "qo'shildi"
                emoji = "✅"
            else:
                action_text = "qo'shishda xatolik"
                emoji = "❌"
        else:
            success = await deduct_user_balance(user_id, amount)
            if success:
                action_text = "kamaytirildi"
                emoji = "✅"
            else:
                action_text = "kamaytirishda xatolik (yetarli mablag' yo'q)"
                emoji = "❌"
        
        # Balansni yangilash
        balance = await get_user_balance(user_id)
        user = await get_user_by_tg_id(user_id)
        
        full_name = user.get('full_name', 'Noma\'lum')
        
        await message.answer(
            f"{emoji} Balans muvaffaqiyatli {action_text}!\n\n"
            f"👤 Foydalanuvchi: {full_name}\n"
            f"💰 Yangi balans: {balance['total_balance']:,} so'm\n"
            f"💳 Naqt balans: {balance['cash_balance']:,} so'm\n"
            f"🎁 Referral balans: {balance['referral_balance']:,} so'm",
            reply_markup=get_admin_keyboard(),
        )
        
        # Log qilish
        await log_action(message.from_user.id, "admin_balance_change", {
            'target_user_id': user_id,
            'action': action,
            'amount': amount,
            'new_balance': balance['total_balance']
        })
        
    except ValueError as e:
        await message.answer(
            f"❌ Noto'g'ri miqdor!\n\n"
            f"Xatolik: {str(e)}\n"
            f"Faqat musbat raqam kiriting:",
            reply_markup=get_admin_keyboard()
        )
    
    await state.set_state(OnboardingStates.MENU)

# Balans boshqarish bekor qilish
@dp.callback_query(F.data == "cancel_balance")
async def cancel_balance_handler(callback: types.CallbackQuery, state: FSMContext):
    """Balans boshqarishni bekor qilish"""
    if not await is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "❌ Balans boshqarish bekor qilindi",
    )
    await state.set_state(OnboardingStates.MENU)
    await callback.answer()

@dp.message(StateFilter(OnboardingStates.MENU), F.text == "⚙️ Referral sozlamalari")
async def referral_settings_menu(message: types.Message):
    """Referral sozlamalari menyusi"""
    if not await is_admin(message.from_user.id):
        return
    
    # Hozirgi referral sozlamalari
    rewards = await get_referral_rewards()
    
    current_settings = (
        "⚙️ Referral sozlamalari\n\n"
        "💰 Hozirgi bonuslar:\n"
        f"• Taklif qilgan: {rewards['referrer_reward']:,} so'm\n"
        f"• Taklif qilingan: {rewards['referred_reward']:,} so'm\n\n"
        "📝 Sozlash uchun:\n"
        "Quyidagi formatda yuboring:\n"
        "`referral: taklif_qilgan: 1500, taklif_qilingan: 700`"
    )
    
    await message.answer(
        current_settings,
    )



@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🏠 Asosiy menyu")
async def back_to_main_menu(message: types.Message):
    """Asosiy menyuga qaytish"""
    await message.answer(
        "🏠 Asosiy menyu\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard(),
    )

# Referral sozlamalarini qabul qilish
@dp.message(StateFilter(OnboardingStates.MENU), F.text.regexp(r'^referral:\s*taklif_qilgan:\s*(\d+),\s*taklif_qilingan:\s*(\d+)$'))
async def process_referral_settings(message: types.Message):
    """Referral sozlamalarini qabul qilish"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        # Matnni parse qilish
        text = message.text.strip()
        parts = text.split(',')
        
        referrer_amount = int(parts[0].split(':')[2].strip())
        referred_amount = int(parts[1].split(':')[1].strip())
        
        # Referral bonuslarini yangilash
        success = await update_referral_rewards(referrer_amount, referred_amount)
        
        if success:
            await message.answer(
                f"✅ Referral sozlamalari yangilandi!\n\n"
                f"💰 Yangi bonuslar:\n"
                f"• Taklif qilgan: {referrer_amount:,} so'm\n"
                f"• Taklif qilingan: {referred_amount:,} so'm\n\n"
                f"🔄 Endi yangi referrallar uchun bu bonuslar ishlatiladi.",
            )
            
            # Log qilish
            await log_action(message.from_user.id, "admin_referral_settings_changed", {
                'referrer_reward': referrer_amount,
                'referred_reward': referred_amount
            })
        else:
            await message.answer(
                "❌ Sozlamalarni yangilashda xatolik!\n\n"
                "Iltimos, qaytadan urinib ko'ring.",
            )
            
    except Exception as e:
        await message.answer(
            f"❌ Noto'g'ri format!\n\n"
            f"To'g'ri format: `referral: taklif_qilgan: 1500, taklif_qilingan: 700`\n\n"
            f"Xatolik: {str(e)}",
        )


# Error handler


async def main():
    """Asosiy funksiya"""
    print("Bot ishga tushmoqda...")
    
    # Database ni ishga tushirish
    await init_db()
    
    # Bot ni ishga tushirish
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
