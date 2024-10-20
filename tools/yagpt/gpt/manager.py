import asyncio

import aiohttp
import logging
from typing import Optional, List, Dict, Tuple
from enum import StrEnum
from pydantic import BaseModel

from ..exceptions import (
    YaGptException,
    TokenLimitExceeded,
    InvalidResponse,
    RedisConnectionError,
    RequestTimeoutException,
    TokenizationError
)

from ..prompt.base import BasePromptCleaner
from ..cache.base import BaseCache
from ..context.base import BaseContextManager
from ..tokenizer.base import BaseTokenizer

from ..auth import AuthManager
from ..context import ContextManager
from ..cache import CacheManager
from ..prompt import PromptManager
from ..tokenizer import Tokenizer
from ..types import MessageContext, Role


class Message(BaseModel):
    role: Role
    text: str


class YaGptManager:
    """Менеджер взаимодействия с Yandex GPT API"""
    base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1"

    def __init__(
            self,
            service_account_key: dict,
            gpt_role: str,
            yc_folder_id: str,
            redis_dsn: str,
            tokenizer: Optional[BaseTokenizer] = None,
            context_manager: Optional[BaseContextManager] = None,
            cache_manager: Optional[BaseCache] = None,
            prompt_manager: Optional[BasePromptCleaner] = None,
            max_tokens: int = 7500,
            max_context_messages: int = 5,
            async_mode: bool = False,
            logger: Optional[logging.Logger] = None,
            async_timeout: int = 60,
    ):
        self._gpt_role = gpt_role
        self._max_tokens = max_tokens
        self._max_context_messages = max_context_messages
        self._async_mode = async_mode
        self._async_timeout = async_timeout
        self.logger = logger or logging.getLogger(__name__)
        self._model_uri = f"gpt://{yc_folder_id}/yandexgpt-lite/latest"

        self._cache_manager = cache_manager or CacheManager(redis_dsn)
        self._context_manager = context_manager or ContextManager(self._cache_manager, max_context_messages, max_tokens)
        self._prompt_manager = prompt_manager or PromptManager()
        self._auth_manager = AuthManager(service_account_key=service_account_key)

        self._headers = {
            'Content-Type': 'application/json',
            'x-folder-id': yc_folder_id
        }

        self._system_message = {
            "role": Role.SYSTEM.value,
            "text": self._gpt_role,
        }
        self._system_tokens = None
        self._role_tokens = None
        self._tokenizer = tokenizer or Tokenizer(self._model_uri, self._max_tokens)

    async def initialize(self):
        iam_token = await self._auth_manager.get_token()
        self._role_tokens = await self._tokenizer.tokenize(self._gpt_role, iam_token)
        self.logger.debug(f"Токены роли YaGpt: {self._role_tokens}")

    async def _make_request(self, url: str, payload: dict) -> dict:
        logging.debug(f"PAYLOAD: {payload}")
        try:
            # Получаем IAM токен и обновляем заголовки
            token = await self._auth_manager.get_token()
            headers = self._headers.copy()
            headers["Authorization"] = f"Bearer {token}"

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        raise InvalidResponse(f"Ошибка при запросе к Yandex GPT API: {response.status}: {err_text}")

                    if self._async_mode:
                        operation_id = (await response.json())['id']
                        response = await self._get_async_result(operation_id, token)
                        return response

                    return await response.json()

        except asyncio.TimeoutError as e:
            raise RequestTimeoutException(f"Таймаут запроса к Yandex GPT API: {e}") from e
        except aiohttp.ClientError as e:
            raise YaGptException(f"Ошибка соединения: {e}") from e

    async def _get_async_result(self, operation_id: str, token: str):
        url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"
        headers = self._headers.copy()
        headers["Authorization"] = f"Bearer {token}"

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with asyncio.timeout(self._async_timeout):
                    while True:
                        await asyncio.sleep(1)
                        async with session.get(url) as response:
                            if response.status != 200:
                                raise InvalidResponse(
                                    f"Ошибка при получении результата асинхронного запроса: {response.status}: {await response.text()}"
                                )
                            self.logger.debug(f"Запрос статуса асинхрон: {response.status} | {await response.json()}")
                            operation_data = await response.json()
                            if operation_data['done']:
                                return operation_data['response']

            except asyncio.TimeoutError:
                raise RequestTimeoutException(
                    f"Превышено время ожидания ответа от Yandex GPT API (operation_id: {operation_id})"
                )

    async def _prepare_context(self, prompt: str, session_id: str, token: str) -> List[Dict]:
        if self._prompt_manager:
            prompt = self._prompt_manager.clean(prompt)
        prompt_tokens = await self._tokenizer.tokenize(prompt, token)
        context = await self._context_manager.update_context(
            session_id,
            MessageContext(
                role=Role.USER,
                text=prompt,
                tokens=prompt_tokens
            )
        )
        return context

    async def get_answer(self, prompt: str, session_id: str) -> str:
        token = await self._auth_manager.get_token()
        context = await self._prepare_context(prompt, session_id, token)
        body = {
            "modelUri": self._model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": "500"
            },
            "messages": [self._system_message] + context
        }
        response = await self._make_request(
            url=self.base_url + "/completionAsync" if self._async_mode else "/completion",
            payload=body,
        )

        answer_tokens = response['usage']['completionTokens']
        answer = response['alternatives'][0]['message']['text']
        _ = await self._context_manager.update_context(
            session_id,
            MessageContext(role=Role.ASSISTANT, text=answer, tokens=answer_tokens)
        )
        return answer
