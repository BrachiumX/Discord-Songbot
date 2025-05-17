from urllib.parse import urlparse
import asyncio


def is_url(string):
    parsed = urlparse(string)
    return all([parsed.scheme, parsed.netloc])


def get_link_type(url):
    if "list=" in url:
        return "list"
    if "watch?v=" in url:
        return "video"
    return "unknown"


class AsyncSafeInt:
    def __init__(self, initial=0):
        self._value = initial
        self._lock = asyncio.Lock()


    async def get(self) -> int:
        async with self._lock:
            return self._value


    async def set(self, value: int):
        async with self._lock:
            self._value = value


    async def increment(self, amount=1):
        async with self._lock:
            self._value += amount


    async def decrement(self, amount=1):
        async with self._lock:
            self._value -= amount