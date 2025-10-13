import asyncio
import logging
import os
import json
from typing import Optional
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from states import OnboardingStates, OrderStates
from database import (
    init_db, get_user_by_tg_id, create_user, create_order, 
    get_active_order, update_order_status, log_action,
    save_presentation, save_slide, get_user_statistics
)
from openai_client import generate_presentation_content
from pptx_generator import create_presentation_file

# .env faylini yuklash
load_dotenv()

# Bot tokenini environment variabledan olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variablesi topilmadi!")

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Tariflar haqida ma'lumot
TARIFFS = {
    "START": {
        "name": "Start tarifi 🚀",
        "price": "Bepul (5 marta)",
        "price_per_page": 2000,
        "features": ["5 marta bepul", "Har sahifa 2000 so'm", "PPT format"]
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
    if not message.from_user:
        return
        
    user = await get_user_by_tg_id(message.from_user.id)
    
    if user:
        # Agar foydalanuvchi mavjud bo'lsa, menyuga o'tkazish
        full_name = user.get('full_name', 'Foydalanuvchi') if user else 'Foydalanuvchi'
        await message.answer(
            f"Assalomu alaykum, {full_name}! 👋\n\n"
            "Qaytganingizdan xursandmiz. Quyidagi tugmalardan birini tanlang:",
            reply_markup=get_main_keyboard()
        )
        await state.set_state(OnboardingStates.MENU)
    else:
        # Yangi foydalanuvchi uchun ro'yxatdan o'tish
        await message.answer(
            "Assalomu alaykum va xush kelibsiz! 👋\n\n"
            "Men sizga professional taqdimotlar tayyorlashda yordam beradigan botman.\n\n"
            "Keling, tanishib olaylik! Ism-familiyangizni kiriting:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(OnboardingStates.ASK_FULLNAME)


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
    await log_action(message.from_user.id, "user_registered", user_data)
    
    await message.answer(
        f"🎉 Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n"
        f"Salom, {data.get('full_name')}! Endi siz botning barcha imkoniyatlaridan foydalanishingiz mumkin.\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard()
    )
    
    await state.set_state(OnboardingStates.MENU)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📊 Taqdimot tayyorlash")
async def start_presentation_order(message: types.Message, state: FSMContext):
    """Taqdimot buyurtmasini boshlash"""
    await message.answer(
        "📊 **Taqdimot tayyorlash** xizmati:\n\n"
        "AI yordamida professional taqdimotlar tayyorlab beramiz!\n\n"
        "Quyidagi tariflardan birini tanlang:",
        reply_markup=get_tariff_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(StateFilter(OrderStates.ASK_TOPIC))
async def process_topic(message: types.Message, state: FSMContext):
    """Taqdimot mavzusini qayta ishlash"""
    topic = message.text.strip()
    
    # Mavzu tekshirish - kamida 3 ta so'z bo'lishi kerak
    words = topic.split()
    if len(words) < 2 or len(topic) < 10:
        await message.answer(
            "❌ **Mavzu nomini to'liq va aniq kiriting!**\n\n"
            "**Misol:**\n"
            "Interstellar - kino haqida ✅\n"
            "Interstellar ❌"
        )
        return
    
    await state.update_data(topic=topic)
    
    await message.answer(
        f"✅ **Mavzu nomini qabul qilib oldim!**\n\n"
        f"Mavzu: **{topic}**\n\n"
        "Endi esa **sahifalar sonini kiriting:**\n\n"
        "**Misol:**\n"
        "10 ✅\n"
        "10-12 ❌\n"
        "14ta ❌\n"
        "Yigirma ❌\n"
        "Yigirma ikkita ❌\n"
        "O'n sakkiz sahifali ❌\n\n"
        "⚠️ **Eslatma:** 1-4 raqamlar qabul qilinmaydi!",
        parse_mode="Markdown"
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
                "❌ **Bu qiymatdagi taqdimotni tayyorlash imkonsiz!**\n\n"
                "5 va undan yuqori raqam kiriting:"
            )
            return
        
        if pages < 5 or pages > 50:
            await message.answer(
                "❌ **Noto'g'ri raqam!**\n\n"
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
            f"✅ **Javoblarni qabul qildim!**\n\n"
            f"**Sizning yakuniy buyurtmangiz quyidagicha ko'rinishda:**\n\n"
            f"📊 **Mavzu nomi:** {topic}\n"
            f"📄 **Sahifalar soni:** {pages} ta\n"
            f"👤 **Talaba:** {user_name}\n\n"
            f"❓ **Buyurtmani tasdiqlaysizmi?**"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")]
        ])
        
        await message.answer(
            confirmation_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await state.set_state(OrderStates.CONFIRM_1)
        
    except ValueError:
        await message.answer(
            "❌ **Faqat raqam kiriting!**\n\n"
            "**Misol:**\n"
            "10 ✅\n"
            "10-12 ❌\n"
            "14ta ❌"
        )
        return


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "ℹ️ Bot haqida")
async def about_bot(message: types.Message):
    """Bot haqida ma'lumot"""
    about_text = (
        "🤖 **PresentatsiyaUz Bot haqida:**\n\n"
        "Biz \"PresentatsiyaUz\" jamoasi 5 yildan buyon nafaqat O'zbekiston balki, "
        "MDH mamlakatlari talabalariga ham xizmat ko'rsatib kelmoqdamiz.\n\n"
        "Bu bot bizning barcha xizmatlarimizni faqat elektron shaklda taqdim etadi, "
        "biz qo'l yozuvi, chizmachilik yoki chop etish bilan shug'ullanmaymiz. "
        "(*hozircha)\n\n"
        "Agar siz botni tushunishda muammolarga duch kelsangiz yoki narxlar bilan "
        "bog'liq muammolarga duch kelsangiz, \"Aloqa uchun\" tugmasi orqali "
        "administratorlardan buyurtma bering!\n\n"
        "💳 **To'lov kartalari:**\n"
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
        "📝 **Mustaqil ishlar tayyorlash:**\n\n"
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
    
    await message.answer(works_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🔧 Boshqa xizmatlar")
async def other_services(message: types.Message):
    """Boshqa xizmatlar"""
    services_text = (
        "🔧 **Boshqa xizmatlar:**\n\n"
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
        "🎮 **Sehrli o'yin - Akinator**\n\n"
        "Men sizning fikringizni o'qib, siz haqingizda aytaman!\n\n"
        "🤔 **Akinator nima?**\n"
        "Bu mashhur o'yin sizning fikringizdagi shaxs, hayvon yoki narsani "
        "faqat savollar berish orqali aniqlaydi!\n\n"
        "🎯 **Qanday o'ynaydi:**\n"
        "1. Siz biror kishi, hayvon yoki narsa haqida o'ylang\n"
        "2. Akinator sizga savollar beradi\n"
        "3. Siz \"Ha\", \"Yo'q\" yoki \"Ehtimol\" javob bering\n"
        "4. Akinator sizning fikringizni aniqlaydi!\n\n"
        "🚀 **O'yinni boshlash uchun tugmani bosing!**"
    )
    
    # Akinator mini app tugmasi
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎯 Akinator o'ynash", 
            web_app=types.WebAppInfo(url="https://en.akinator.com/")
        )]
    ])
    
    await message.answer(game_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "💰 Balansim")
async def my_balance(message: types.Message):
    """Foydalanuvchi balansi"""
    if not message.from_user:
        return
    
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmadingiz. /start buyrug'ini yuboring.")
        return
    
    # Foydalanuvchi statistikasini olish
    stats = await get_user_statistics(message.from_user.id)
    
    # Balans ma'lumotlari (namuna)
    total_balance = 30000  # Umumiy balans
    cash_payment = 20000   # Naqt to'lov
    referrals = 10         # Takliflar soni
    referral_bonus = 10000 # Taklif mukofoti
    
    balance_text = (
        f"💰 **Sizning balansingiz:**\n\n"
        f"💳 **Umumiy balans:** {total_balance:,} so'm\n\n"
        f"📊 **Balans tafsilotlari:**\n"
        f"• Naqt orqali to'langan: {cash_payment:,} so'm\n"
        f"• {referrals} ta taklif uchun: {referral_bonus:,} so'm\n\n"
        f"📈 **Statistika:**\n"
        f"• Yaratilgan taqdimotlar: {stats.get('total_presentations', 0)}\n"
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yoq')}\n"
        f"• Qo'shilgan sana: {user.get('created_at', 'Nomalum')}"
    )
    
    # Balans tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up_balance")],
        [InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referral_link")],
        [InlineKeyboardButton(text="📊 Referral statistikasi", callback_data="referral_stats")]
    ])
    
    await message.answer(balance_text, reply_markup=keyboard, parse_mode="Markdown")


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
        "📞 **Biz bilan bog'laning:**\n\n"
        "Quyidagi adminlar bilan bog'laning:\n\n"
        "🕐 **Ish vaqti:**\n"
        "Dushanba - Juma: 09:00 - 18:00\n"
        "Shanba - Yakshanba: 10:00 - 16:00\n\n"
        "❓ **Savollar bormi?**\n"
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
        f"📊 **Sizning statistikangiz:**\n\n"
        f"📈 **Umumiy ko'rsatkichlar:**\n"
        f"• Yaratilgan taqdimotlar: {stats.get('total_presentations', 0)}\n"
        f"• Faol kunlar: {stats.get('active_days', 0)}\n"
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yoq')}\n\n"
        f"🎯 **Faoliyat:**\n"
        f"• Bu oy: {stats.get('this_month', 0)} ta taqdimot\n"
        f"• O'tgan oy: {stats.get('last_month', 0)} ta taqdimot\n\n"
        f"💡 **Maslahat:** Ko'proq taqdimot yaratib, tajribangizni oshiring!"
    )
    
    await message.answer(stats_text, parse_mode="Markdown")


# Callback query handlers
@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: types.CallbackQuery, state: FSMContext):
    """Tarif tanlashni qayta ishlash"""
    tariff_key = callback.data.replace("tariff_", "")
    await state.update_data(tariff=tariff_key)
    
    tariff_info = TARIFFS[tariff_key]
    
    if tariff_key == "START":
        start_text = (
            f"🚀 **Start tarifini tanladingiz!**\n\n"
            f"Ushbu tarifdan foydalanish besh marotabagacha bepul! "
            f"\\(beshinchisi hisobga kirmaydi!\\)\n\n"
            f"Undan keyin esa har bir sahifasi uchun {tariff_info['price_per_page']:,} so'mdan to'laysiz\\.\n"
            f"Format: **PPT**\n\n"
            f"Endi esa **Mavzu nomini to'liq va aniq kiriting:**\n\n"
            f"**Misol:**\n"
            f"Interstellar \\- kino haqida ✅\n"
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
        tariff_name = tariff_info['name'].replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
        format_name = format_text.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
        
        start_text = (
            f"💰 **{tariff_name}ni tanladingiz!**\n\n"
            f"Format: **{format_name}**\n\n"
            f"Endi esa **Mavzu nomini to'liq va aniq kiriting:**\n\n"
            f"**Misol:**\n"
            f"Interstellar \\- kino haqida ✅\n"
            f"Interstellar ❌"
        )
    
    await callback.message.edit_text(
        start_text,
        parse_mode="Markdown"
    )
    
    await callback.answer()
    await state.set_state(OrderStates.ASK_TOPIC)


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await callback.message.edit_text(
        "🏠 **Asosiy menyu**\n\n"
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
        "🎉 **Buyurtma tasdiqlandi!**\n\n"
        "🚀 Taqdimot yaratish jarayoni boshlandi...\n"
        "⏱️ Tahmini vaqt: 2-3 daqiqa\n\n"
        "📱 Tayyor bo'lganda sizga xabar beramiz!",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
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
        # Namuna: 3-chi buyurtma (bepul buyurtmalar sonini hisoblash kerak)
        free_orders = 3  # Bu ma'lumotlar bazasidan kelishi kerak
        remaining_free = 5 - free_orders
        
        second_confirmation_text = (
            f"🔒 **Ikkinchi tasdiqlash bosqichi**\n\n"
            f"Siz bepul obunada **{free_orders}-chi** buyurtmani amalga oshirmoqdasiz, "
            f"sizda yana **{remaining_free} ta** bepul taqdimot tayyorlash imkoni qolmoqda!\n\n"
            f"**Buyurtmangizni 100% tasdiqlashga imkoningiz komilmi?**"
        )
    else:
        # Premium tariflar uchun
        tariff_info = TARIFFS[tariff_key]
        total_price = pages * tariff_info['price_per_page']
        
        second_confirmation_text = (
            f"💰 **To'lov ma'lumotlari:**\n\n"
            f"Siz **{data['topic']}** mavzusida **{pages} ta** sahifali taqdimot "
            f"buyurtma qilyapsiz va uning narxi "
            f"**({pages} × {tariff_info['price_per_page']:,} = {total_price:,} so'm)** "
            f"**{total_price:,} so'm** bo'ldi.\n\n"
            f"❓ **Buyurtmani tasdiqlaysizmi?**"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_final")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")]
    ])
    
    await callback.message.edit_text(
        second_confirmation_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
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
        # Start tarifi uchun yakuniy xabar
        final_text = (
            f"🔒 **Yakuniy tasdiqlash:**\n\n"
            f"Siz buyurtmani tasdiqladingiz, ishonch va xavfsizlik uchun uni yana tasdiqlashingizni "
            f"va bu ishni o'zingiz onli ravishda bajarishingizni so'rayman.\n\n"
            f"Agar hozir yana bir bor, **Ha✅**ni bossangiz taqdimot tayyorlash jarayoni boshlanadi.\n\n"
            f"**Tanlang:**"
        )
    else:
        # Premium tariflar uchun
        tariff_info = TARIFFS[tariff_key]
        total_price = pages * tariff_info['price_per_page']
        
        final_text = (
            f"🔒 **Yakuniy tasdiqlash:**\n\n"
            f"Siz buyurtmani tasdiqladingiz, ishonch va xavfsizlik uchun uni yana tasdiqlashingizni "
            f"va bu ishni o'zingiz onli ravishda bajarishingizni so'rayman.\n\n"
            f"Agar hozir yana bir bor, **Ha✅**ni bossangiz hisobingizdan "
            f"**{total_price:,} so'm** mablag' yechib olaman.\n\n"
            f"**Tanlang:**"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="start_generation")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        final_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "confirm_no")
async def cancel_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Tasdiqni rad etish"""
    await callback.answer("❌ Buyurtma bekor qilindi")
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(
            "❌ **Buyurtma bekor qilindi.**\n\n"
            "Agar fikringizni o'zgartirsangiz, qaytadan 'Taqdimot tayyorlash' tugmasini bosing.",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )


@dp.callback_query(F.data == "start_generation")
async def start_presentation_generation(callback: types.CallbackQuery, state: FSMContext):
    """Taqdimot yaratishni boshlash"""
    await callback.answer("🚀 Taqdimot yaratish boshlanmoqda...")
    
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
        "🎉 **Buyurtma tasdiqlandi!**\n\n"
        "🚀 Taqdimot yaratish jarayoni boshlandi...\n"
        "⏱️ Tahmini vaqt: 2-3 daqiqa\n\n"
        "📱 Tayyor bo'lganda sizga xabar beramiz!",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
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
        "📋 **Online taklifnoma (QR-kodli):**\n\n"
        "Professional online taklifnomalar tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• To'ylar uchun taklifnoma\n"
        "• Tug'ilgan kun taklifnomasi\n"
        "• Tadbirlar uchun taklifnoma\n"
        "• Korxona tadbirlari\n"
        "• QR-kod bilan\n\n"
        "⏱️ **Muddati:** 1-3 kun\n"
        "💰 **Narx:** Taklifnoma turiga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📄 **Rezyume tayyorlash:**\n\n"
        "Professional va zamonaviy rezyumelar tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Standart rezyume\n"
        "• Kreativ rezyume\n"
        "• IT mutaxassislar uchun\n"
        "• Marketing uchun\n"
        "• PDF va Word formatlarida\n\n"
        "⏱️ **Muddati:** 1-2 kun\n"
        "💰 **Narx:** Rezyume turiga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "🎨 **YouTube kanal uchun banner:**\n\n"
        "Professional YouTube kanal bannerlarini tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Standart YouTube banner\n"
        "• Kreativ dizayn\n"
        "• Kanal mavzusiga mos\n"
        "• Mobil va desktop uchun\n"
        "• PNG va JPG formatlarida\n\n"
        "⏱️ **Muddati:** 1-2 kun\n"
        "💰 **Narx:** Dizayn murakkabligiga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "🎯 **Logo tayyorlash:**\n\n"
        "Professional va zamonaviy logolarni tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Korporativ logo\n"
        "• Kichik biznes logo\n"
        "• Start-up logo\n"
        "• Shaxsiy brend logo\n"
        "• Turli formatlarda (PNG, SVG, PDF)\n\n"
        "⏱️ **Muddati:** 2-5 kun\n"
        "💰 **Narx:** Logo murakkabligiga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "🔧 **Boshqa xizmatlar:**\n\n"
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
        "🎓 **Kurs ishi tayyorlash:**\n\n"
        "Professional kurs ishlarini tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Kurs ishi yozish (15-50 sahifa)\n"
        "• Ilmiy tadqiqot ishlari\n"
        "• Texnik kurs ishlari\n"
        "• Iqtisodiy kurs ishlari\n"
        "• Pedagogik kurs ishlari\n\n"
        "⏱️ **Muddati:** 3-7 kun\n"
        "💰 **Narx:** Mavzu va sahifalar soniga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📄 **Ilmiy maqola tayyorlash:**\n\n"
        "Ilmiy va akademik maqolalarni tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Ilmiy maqola yozish\n"
        "• Akademik tadqiqot ishlari\n"
        "• Konferensiya maqolalari\n"
        "• Jurnal uchun maqolalar\n"
        "• Ilmiy tezis yozish\n\n"
        "⏱️ **Muddati:** 5-10 kun\n"
        "💰 **Narx:** Mavzu va hajmga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📚 **Referat tayyorlash:**\n\n"
        "Har qanday mavzu bo'yicha referatlarni tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Akademik referatlar\n"
        "• Ilmiy referatlar\n"
        "• Mavzu referatlar\n"
        "• Tadqiqot referatlar\n"
        "• Xulosa referatlar\n\n"
        "⏱️ **Muddati:** 2-5 kun\n"
        "💰 **Narx:** Sahifalar soniga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📋 **Mustaqil ish tayyorlash:**\n\n"
        "Turli yo'nalishlardagi mustaqil ishlarni tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Akademik mustaqil ishlar\n"
        "• Ilmiy mustaqil ishlar\n"
        "• Amaliy mustaqil ishlar\n"
        "• Tadqiqot mustaqil ishlar\n"
        "• Yaratuvchilik ishlar\n\n"
        "⏱️ **Muddati:** 3-7 kun\n"
        "💰 **Narx:** Ish turi va hajmga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📊 **Hisobot tayyorlash:**\n\n"
        "Professional hisobotlarni tayyorlab beramiz!\n\n"
        "📋 **Xizmatlar:**\n"
        "• Tadqiqot hisobotlari\n"
        "• Amaliy hisobotlar\n"
        "• Ish hisobotlari\n"
        "• Statistika hisobotlari\n"
        "• Analiz hisobotlari\n\n"
        "⏱️ **Muddati:** 2-5 kun\n"
        "💰 **Narx:** Hisobot turi va hajmga qarab\n\n"
        "📞 **Buyurtma uchun admin bilan bog'laning:**"
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
        "📝 **Mustaqil ishlar tayyorlash:**\n\n"
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
        "💳 **Balansni to'ldirish:**\n\n"
        "Quyidagi usullar orqali balansingizni to'ldirishingiz mumkin:\n\n"
        "🔹 **Naqt to'lov:**\n"
        "• Uzcard: 5614682110523232\n"
        "• Humo: 9860170104108668\n"
        "• VISA: 4023060518185649\n\n"
        "🔹 **Elektron to'lov:**\n"
        "• Payme\n"
        "• Click\n"
        "• Uzcard Mobile\n\n"
        "💡 **Eslatma:** To'lov amalga oshirgandan so'ng, "
        "chek rasmini yuboring va balansingiz 5-10 daqiqada to'ldiriladi."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Chek yuborish", callback_data="send_receipt")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(payment_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "referral_link")
async def get_referral_link(callback: types.CallbackQuery):
    """Referral link olish"""
    await callback.answer("👥 Referral link...")
    
    if not callback.from_user:
        return
    
    # Referral link yaratish
    referral_link = f"https://t.me/preuz_bot?start=ref_{callback.from_user.id}"
    
    referral_text = (
        "👥 **Do'stlarni taklif qilish:**\n\n"
        "Do'stlaringizni taklif qiling va har bir taklif uchun 1,000 so'm bonus oling!\n\n"
        f"🔗 **Sizning taklif havolangiz:**\n"
        f"`{referral_link}`\n\n"
        "📋 **Qanday ishlaydi:**\n"
        "1. Havolani do'stlaringizga yuboring\n"
        "2. Do'stingiz bot orqali ro'yxatdan o'tadi\n"
        "3. Sizga 1,000 so'm bonus qo'shiladi\n"
        "4. Do'stingiz ham 500 so'm bonus oladi\n\n"
        "💡 **Maslahat:** Ko'proq do'st taklif qiling va ko'proq bonus oling!"
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
    
    # Namuna statistikalar
    total_referrals = 10
    active_referrals = 8
    total_bonus = 10000
    pending_bonus = 2000
    
    stats_text = (
        "📊 **Referral statistikasi:**\n\n"
        f"👥 **Umumiy takliflar:** {total_referrals} ta\n"
        f"✅ **Faol takliflar:** {active_referrals} ta\n"
        f"💰 **Jami bonus:** {total_bonus:,} so'm\n"
        f"⏳ **Kutilayotgan bonus:** {pending_bonus:,} so'm\n\n"
        f"🏆 **Eng ko'p taklif qilgan:** 5 ta (bu oy)\n"
        f"📈 **O'sish sur'ati:** +2 ta (o'tgan hafta)\n\n"
        f"💡 **Maslahat:** Har hafta kamida 3 ta do'st taklif qiling!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="referral_stats")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(stats_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "back_to_balance")
async def back_to_balance(callback: types.CallbackQuery):
    """Balans sahifasiga qaytish"""
    await callback.answer("⬅️ Balansga qaytish...")
    
    if not callback.from_user:
        return
    
    # Balans ma'lumotlari (namuna)
    total_balance = 30000
    cash_payment = 20000
    referrals = 10
    referral_bonus = 10000
    
    balance_text = (
        f"💰 **Sizning balansingiz:**\n\n"
        f"💳 **Umumiy balans:** {total_balance:,} so'm\n\n"
        f"📊 **Balans tafsilotlari:**\n"
        f"• Naqt orqali to'langan: {cash_payment:,} so'm\n"
        f"• {referrals} ta taklif uchun: {referral_bonus:,} so'm"
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
        "📸 **Chek yuborish:**\n\n"
        "To'lov cheki rasmini yuboring va quyidagi ma'lumotlarni ko'rsating:\n\n"
        "🔹 **Kerakli ma'lumotlar:**\n"
        "• To'lov summasi\n"
        "• To'lov sanasi va vaqti\n"
        "• Karta raqami (oxirgi 4 ta raqam)\n\n"
        "⏱️ **Tekshirish vaqti:** 5-10 daqiqa\n"
        "✅ **Tasdiqlangandan so'ng:** Balansingiz avtomatik to'ldiriladi\n\n"
        "💡 **Eslatma:** Faqat aniq va o'qiladigan rasmlarni yuboring."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="top_up_balance")]
    ])
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(receipt_text, reply_markup=keyboard, parse_mode="Markdown")


async def generate_presentation_task(user_tg_id: int, order_id: int, topic: str, pages: int, tariff: str):
    """Taqdimot yaratish vazifasi"""
    try:
        # OpenAI dan kontent olish
        content = await generate_presentation_content(topic, pages)
        
        # PowerPoint fayl yaratish
        file_path = await create_presentation_file(content, topic, user_tg_id)
        
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
        with open(file_path, 'rb') as file:
            await bot.send_document(
                chat_id=user_tg_id,
                document=file,
                caption=f"🎉 **Taqdimot tayyor!**\n\n"
                       f"📊 **Mavzu:** {topic}\n"
                       f"📄 **Sahifalar:** {pages}\n"
                       f"💰 **Tarif:** {TARIFFS[tariff]['name']}\n\n"
                       f"✅ Fayl muvaffaqiyatli yaratildi!",
                parse_mode="Markdown"
            )
        
        # Log yaratish
        await log_action(user_tg_id, "presentation_generated", {
            'topic': topic,
            'pages': pages,
            'tariff': tariff,
            'file_path': file_path
        })
        
    except Exception as e:
        # Xatolik holatida foydalanuvchiga xabar berish
        await bot.send_message(
            chat_id=user_tg_id,
            text=f"❌ **Xatolik yuz berdi!**\n\n"
                 f"Taqdimot yaratishda muammo bo'ldi. Iltimos, qaytadan urinib ko'ring.\n\n"
                 f"📞 Agar muammo davom etsa, qo'llab-quvvatlashga murojaat qiling.",
            parse_mode="Markdown"
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


# Error handler
@dp.error()
async def error_handler(event, **kwargs):
    """Xatoliklar bilan ishlash"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Exception'ni to'g'ri olish
    exception = None
    if 'exception' in kwargs:
        exception = kwargs['exception']
    elif hasattr(event, 'exception'):
        exception = event.exception
    
    if exception:
        logger.error(f"Bot xatoligi: {exception}")
    else:
        logger.warning("Noma'lum xatolik yuz berdi")
    
    # Foydalanuvchiga umumiy xatolik xabari
    if hasattr(event, 'message') and event.message:
        try:
            await event.message.answer(
                "❌ **Xatolik yuz berdi!**\n\n"
                "Iltimos, qaytadan urinib ko'ring yoki /start buyrug'ini yuboring.",
                parse_mode="Markdown"
            )
        except:
            pass
