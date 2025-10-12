from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    """Ro'yxatdan o'tish holatlari"""
    ASK_FULLNAME = State()
    ASK_CONTACT = State()
    MENU = State()

class OrderStates(StatesGroup):
    """Buyurtma holatlari"""
    ASK_TOPIC = State()
    ASK_PAGES = State()
    CHOOSE_TARIFF = State()
    CONFIRM_1 = State()
    CONFIRM_2 = State()
    PREVIEW = State()
    PROCESSING = State()
