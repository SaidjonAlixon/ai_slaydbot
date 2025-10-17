from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    """Ro'yxatdan o'tish holatlari"""
    ASK_FULLNAME = State()
    ASK_CONTACT = State()
    MENU = State()
    BROADCAST_MESSAGE = State()
    USER_ID_INPUT = State()
    USER_MESSAGE = State()
    BALANCE_USER_ID = State()
    BALANCE_ACTION = State()
    BALANCE_AMOUNT = State()
    RECEIPT_FIRST = State()
    RECEIPT_SECOND = State()

class OrderStates(StatesGroup):
    """Buyurtma holatlari"""
    ASK_TOPIC = State()
    ASK_PAGES = State()
    CHOOSE_TARIFF = State()
    CONFIRM_1 = State()
    CONFIRM_2 = State()
    PREVIEW = State()
    PROCESSING = State()
