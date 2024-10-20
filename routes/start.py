from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums.parse_mode import ParseMode

from yagptmanager.exceptions import EmptyTextError

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    await message.answer("Hello!")


@router.message()
async def chat_command(message: Message, yagpt_manager):
    try:
        answer = await yagpt_manager.get_answer(message.text, message.chat.id)
        await message.answer(text=str(answer), parse_mode=ParseMode.MARKDOWN)
    except EmptyTextError as e:
        await message.answer(text=str(e))
