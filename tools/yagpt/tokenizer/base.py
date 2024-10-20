from abc import ABC, abstractmethod
from typing import Optional


class BaseTokenizer(ABC):
    """Класс для вычисления количества токенов"""

    async def tokenize_completion(self, messages: dict, token: Optional[str]) -> int:
        """Подсчитывает количество токенов в контексте с помощью API Yandex Cloud.

        :param messages: Контекст для токенизации.
        :param token: IAM токен.

        :returns Количество токенов в контексте
        """

    async def tokenize(self, text: str, token: Optional[str]) -> int:
        """Подсчитывает количество токенов в тексте с помощью API Yandex Cloud.

        :param text: Текст для токенизации.
        :param token: IAM токен.

        :returns Количество токенов в тексте
        """
