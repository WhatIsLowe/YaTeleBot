import json
import logging
from collections import deque
from typing import List, Optional, Deque

from .base import BaseContextManager
from ..cache.base import BaseCache
from ..types import MessageContext

logger = logging.getLogger(__name__)


class ContextManager(BaseContextManager):
    def __init__(self, cache_manager: BaseCache, max_context_messages: int = 5, max_tokens: int = 7500):
        self.cache_manager = cache_manager
        self.max_context_messages = max_context_messages
        self.max_tokens = max_tokens

    async def get_context(self, session_id: str) -> Optional[List[dict]]:
        context_json = await self.cache_manager.get(f"context:{session_id}")
        logger.debug(f"Контекст для данной сессии {session_id}: {context_json}")

        if context_json is not None:
            try:
                context: List[dict] = json.loads(context_json)
                return context
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка десериализации контекста: {e}")
                return None
        return None

    async def update_context(self, session_id: str, new_message: MessageContext) -> List[dict]:
        context: Deque[dict] = deque(await self.get_context(session_id) or [])

        while len(context) >= self.max_context_messages:
            context.popleft()

        total_tokens = sum(msg['tokens'] for msg in context) + new_message.tokens
        logger.debug(f"total_tokens: {total_tokens}")
        while total_tokens >= self.max_tokens and context:
            removed_message = context.popleft()
            total_tokens -= removed_message['tokens']

        context_list = list(context)
        context_list.append(
            {
                "role": new_message.role,
                "text": new_message.text,
                "tokens": new_message.tokens
            }
        )
        await self.cache_manager.set(f"context:{session_id}", json.dumps(context_list), ttl=3600)
        logger.debug(f"Контекст для сессии {session_id} обновлен")
        return context_list
