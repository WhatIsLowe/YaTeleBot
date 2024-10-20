from aiogram import BaseMiddleware
from aiogram.types import Message
from tools.yagpt import YaGptManager


class YaGptMiddleware(BaseMiddleware):
    def __init__(self, yagpt_manager: YaGptManager):
        super().__init__()
        self.yagpt_manager = yagpt_manager

    async def __call__(self, handler, event: Message, data: dict):
        data["yagpt_manager"] = self.yagpt_manager
        return await handler(event, data)
