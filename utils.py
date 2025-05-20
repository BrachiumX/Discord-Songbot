from urllib.parse import urlparse
import asyncio
from collections import deque


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



class Video:
    def __init__(self, owner, video_url, stream_url, title):
        self.owner = owner
        self.video_url = video_url
        self.stream_url = stream_url
        self.title = title



class ThreadSafeQueue:
    def __init__(self):
        self._queue = []
        self._lock = asyncio.Lock()


    async def put(self, item):
        async with self._lock:
            self._queue.append(item)


    async def remove(self, index):
        async with self._lock:
            return self._queue.pop(index) 


    async def get_nth(self, n):
        async with self._lock:
            return self._queue[n]


    async def pop(self):
        while True:
            length = await self.length()
            if length == 0:
                await asyncio.sleep(1)
            else:
                async with self._lock:
                    return self._queue.pop(0)


    async def length(self):
        async with self._lock:
            return len(self._queue)