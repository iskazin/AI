from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    phase2_complaints = State()
    phase3_history = State()
    phase4_followup = State()
    phase5_docs = State()
    phase5_result = State()

class PaymentStates(StatesGroup):
    waiting_receipt = State()
    waiting_guide_receipt = State()

class AdminStates(StatesGroup):
    browsing = State()
