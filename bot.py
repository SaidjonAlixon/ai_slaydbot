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
        "price": "Bepul",
        "features": ["5-10 sahifa", "Asosiy dizayn", "PDF format"]
    },
    "STANDARD": {
        "name": "Standard tarifi 💎",
        "price": "25,000 so'm", 
        "features": ["10-15 sahifa", "Professional dizayn", "PDF + PPT format"]
    },
    "PREMIUM": {
        "name": "Premium tarifi 👑",
        "price": "50,000 so'm", 
        "features": ["10-20 sahifa", "Professional dizayn", "PDF + PPT format", "Prioritet qo'llab-quvvatlash"]
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
        "Men sizga AI yordamida professional taqdimotlar tayyorlab beraman.\n\n"
        "Avval taqdimot mavzusini kiriting:\n"
        "(Masalan: 'O'zbekiston iqtisodiyoti', 'IT texnologiyalari', 'Ta'lim tizimi' va boshqalar)",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(OrderStates.ASK_TOPIC)


@dp.message(StateFilter(OrderStates.ASK_TOPIC))
async def process_topic(message: types.Message, state: FSMContext):
    """Taqdimot mavzusini qayta ishlash"""
    topic = message.text.strip()
    
    if len(topic) < 3:
        await message.answer("Iltimos, taqdimot mavzusini to'liq kiriting (kamida 3 ta belgi):")
        return
    
    await state.update_data(topic=topic)
    
    await message.answer(
        f"✅ Mavzu qabul qilindi: **{topic}**\n\n"
        "Endi taqdimot sahifalar sonini kiriting:\n"
        "(5-20 orasida raqam kiriting)",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(OrderStates.ASK_PAGES)


@dp.message(StateFilter(OrderStates.ASK_PAGES))
async def process_pages(message: types.Message, state: FSMContext):
    """Sahifalar sonini qayta ishlash"""
    try:
        pages = int(message.text.strip())
        
        if pages < 5 or pages > 20:
            await message.answer("Iltimos, 5-20 orasida raqam kiriting:")
            return
        
        await state.update_data(pages=pages)
        
        # Tariflar haqida ma'lumot
        tariff_text = "💰 **Tarif tanlang:**\n\n"
        for tariff_key, tariff_info in TARIFFS.items():
            tariff_text += f"**{tariff_info['name']}**\n"
            tariff_text += f"💰 Narxi: {tariff_info['price']}\n"
            tariff_text += f"📋 Imkoniyatlar:\n"
            for feature in tariff_info['features']:
                tariff_text += f"  • {feature}\n"
            tariff_text += "\n"
        
        tariff_text += f"📊 **Sizning buyurtmangiz:**\n"
        tariff_text += f"• Mavzu: {topic}\n"
        tariff_text += f"• Sahifalar: {pages}\n\n"
        tariff_text += "Quyidagi tariflardan birini tanlang:"
        
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting (5-20 orasida):")
        return
    
    await message.answer(
        tariff_text,
        reply_markup=get_tariff_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.CHOOSE_TARIFF)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "ℹ️ Bot haqida")
async def about_bot(message: types.Message):
    """Bot haqida ma'lumot"""
    about_text = (
        "🤖 Taqdimot Bot haqida:\n\n"
        "Bu bot sizga professional taqdimotlar yaratishda yordam beradi. "
        "ChatGPT AI texnologiyasi yordamida mavzungiz bo'yicha to'liq strukturalangan "
        "va chiroyli dizayndagi taqdimotlar tayyorlab beraman.\n\n"
        "🔹 Imkoniyatlar:\n"
        "• AI yordamida kontent generatsiyasi\n"
        "• Professional dizayn\n"
        "• Turli formatlar (PDF, PPT)\n"
        "• Tez va sifatli xizmat\n\n"
        "📞 Qo'llab-quvvatlash: @ai_slaydbot"
    )
    
    await message.answer(about_text)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📝 Mustaqil ishlar")
async def independent_works(message: types.Message):
    """Mustaqil ishlar tayyorlash"""
    works_text = (
        "📝 Mustaqil ishlar tayyorlash xizmati:\n\n"
        "Sizga quyidagi turdagi mustaqil ishlarni tayyorlab beraman:\n\n"
        "🔹 Ma'lumotnoma va referatlar\n"
        "🔹 Kurs ishlari va diplom ishlari\n"
        "🔹 Ilmiy maqolalar\n"
        "🔹 Loyiha hujjatlari\n"
        "🔹 Hisobot va tavsiflar\n\n"
        "Batafsil ma'lumot uchun /contact buyrug'ini yuboring."
    )
    
    await message.answer(works_text)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🔧 Boshqa xizmatlar")
async def other_services(message: types.Message):
    """Boshqa xizmatlar"""
    services_text = (
        "🔧 Boshqa xizmatlar:\n\n"
        "Sizga quyidagi qo'shimcha xizmatlarni taklif etaman:\n\n"
        "🔹 Matn tahrirlash va nashrga tayyorlash\n"
        "🔹 Tilni to'g'rilash\n"
        "🔹 Kontent optimizatsiyasi\n"
        "🔹 SEO yozuvlar\n"
        "🔹 Sotuv yozuvlari\n"
        "🔹 Blog maqolalari\n\n"
        "Batafsil ma'lumot va narxlar uchun /contact buyrug'ini yuboring."
    )
    
    await message.answer(services_text)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "🎮 Sehrli o'yin")
async def magic_game(message: types.Message):
    """Sehrli o'yin"""
    game_text = (
        "🎮 Sehrli o'yin - Keling, o'ynaylik!\n\n"
        "Men sizning fikringizni o'qib, siz haqingizda aytaman!\n\n"
        "1️⃣ 1-10 orasida bir son tanlang\n"
        "2️⃣ Mavzu tanlang:\n"
        "   • Sevgi\n"
        "   • Ishlar\n"
        "   • Kelajak\n"
        "   • Baxt\n\n"
        "O'yinni boshlash uchun 'O'ynash' tugmasini bosing!"
    )
    
    # O'yin tugmasi
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 O'ynash", callback_data="start_game")]
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
    
    # Foydalanuvchi statistikasini olish
    stats = await get_user_statistics(message.from_user.id)
    
    balance_text = (
        f"💰 Sizning balansingiz:\n\n"
        f"📊 Statistika:\n"
        f"• Yaratilgan taqdimotlar: {stats.get('total_presentations', 0)}\n"
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yo\'q')}\n"
        f"• Qo'shilgan sana: {user.get('created_at', 'Noma\'lum')}\n\n"
        f"💳 Balans: 0 so'm (Hozircha bepul xizmat)\n\n"
        f"💡 Maslahat: Ko'proq taqdimot yaratib, tajribangizni oshiring!"
    )
    
    await message.answer(balance_text)


@dp.message(StateFilter(OnboardingStates.MENU), F.text == "📞 Aloqa uchun")
async def contact_us(message: types.Message):
    """Aloqa uchun"""
    contact_text = (
        "📞 Biz bilan bog'laning:\n\n"
        "💬 Telegram: @ai_slaydbot\n"
        "📧 Email: ai.slayd.bot@gmail.com\n"
        "📱 Qo'llab-quvvatlash: @ai_slaydbot\n\n"
        "🕐 Ish vaqti:\n"
        "Dushanba - Juma: 09:00 - 18:00\n"
        "Shanba - Yakshanba: 10:00 - 16:00\n\n"
        "❓ Savollar bormi?\n"
        "Har qanday savol va takliflar uchun bizga yozing!\n\n"
        "📋 Kontakt ma'lumotlari:\n"
        "• Telegram: @ai_slaydbot\n"
        "• Email: ai.slayd.bot@gmail.com\n"
        "• Qo'llab-quvvatlash: @ai_slaydbot"
    )
    
    await message.answer(contact_text)


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
        f"• So'nggi faollik: {stats.get('last_activity', 'Hali yo\'q')}\n\n"
        f"🎯 **Faoliyat:**\n"
        f"• Bu oy: {stats.get('this_month', 0)} ta taqdimot\n"
        f"• O'tgan oy: {stats.get('last_month', 0)} ta taqdimot\n\n"
        f"💡 **Maslahat:** Ko'proq taqdimot yaratib, tajribangizni oshiring!"
    )
    
    await message.answer(stats_text, parse_mode="Markdown")


# Callback query handlers
@dp.callback_query(StateFilter(OrderStates.CHOOSE_TARIFF), F.data.startswith("tariff_"))
async def process_tariff_selection(callback: types.CallbackQuery, state: FSMContext):
    """Tarif tanlashni qayta ishlash"""
    tariff_key = callback.data.replace("tariff_", "")
    data = await state.get_data()
    
    await state.update_data(tariff=tariff_key)
    
    tariff_info = TARIFFS[tariff_key]
    
    confirmation_text = (
        f"✅ **Buyurtma tasdiqlash:**\n\n"
        f"📊 **Mavzu:** {data['topic']}\n"
        f"📄 **Sahifalar:** {data['pages']}\n"
        f"💰 **Tarif:** {tariff_info['name']}\n"
        f"💵 **Narxi:** {tariff_info['price']}\n\n"
        f"📋 **Imkoniyatlar:**\n"
    )
    
    for feature in tariff_info['features']:
        confirmation_text += f"  • {feature}\n"
    
    confirmation_text += "\n❓ **Buyurtmani tasdiqlaysizmi?**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="confirm_no")]
    ])
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await callback.answer()
    await state.set_state(OrderStates.CONFIRM_1)


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
    """Buyurtmani tasdiqlash"""
    await callback.answer("✅ Buyurtma tasdiqlanmoqda...")
    
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


@dp.callback_query(F.data == "confirm_no")
async def cancel_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Tasdiqni rad etish"""
    await callback.answer("❌ Buyurtma bekor qilindi")
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(
            "❌ Buyurtma bekor qilindi.\n\n"
            "Agar fikringizni o'zgartirsangiz, qaytadan 'Taqdimot tayyorlash' tugmasini bosing.",
            reply_markup=get_back_keyboard()
        )


@dp.callback_query(F.data == "start_game")
async def start_magic_game(callback: types.CallbackQuery):
    """Sehrli o'yinni boshlash"""
    await callback.answer("🎮 O'yin boshlanmoqda...")
    
    import random
    
    # Tasodifiy javoblar
    responses = [
        "🌟 Sizning kelajagingiz yorqin! Har bir qadam sizni muvaffaqiyatga olib boradi.",
        "💫 Sevgi sizning hayotingizda kuchli! Yaqinlaringiz sizni qadrlaydi.",
        "🚀 Ishlaringiz rivojlanmoqda! Tez orada katta muvaffaqiyatlar kutilmoqda.",
        "🎯 Maqsadingizga yaqinlashyapsiz! Sabr-toqat bilan davom eting.",
        "✨ Baxtingiz ochiq! Har qanday vaziyatda ijobiy yechim topasiz.",
        "🔥 Enerjiyingiz yuqori! Bugun aynan sizga kerakli kun.",
        "💎 Qiymatingizni bilasiz! O'z qadr-qimmatingizni himoya qilasiz.",
        "🌈 Rang-barang hayot! Har bir kun sizga yangi imkoniyatlar beradi."
    ]
    
    magic_text = random.choice(responses)
    
    if callback.message and hasattr(callback.message, 'edit_text') and not isinstance(callback.message, types.InaccessibleMessage):
        await callback.message.edit_text(
            f"🔮 Sehrli javob:\n\n{magic_text}\n\n"
            "🎮 Yana o'ynash uchun 'Qayta o'ynash' tugmasini bosing!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta o'ynash", callback_data="start_game")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu")]
            ])
        )


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
async def error_handler(event, exception):
    """Xatoliklar bilan ishlash"""
    logger.error(f"Bot xatoligi: {exception}")
    
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
