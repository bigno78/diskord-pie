import aiohttp
import asyncio
import time

from typing import Dict, Union

__all__ = [ "HttpClient", "DiskordHttpError" ]

class Route:
    def __init__(self, path: str, method: str):
        self.path = path
        self.method = method

    def __eq__(self, other):
        if not isinstance(other, Route):
            return False
        return self.path == other.path and self.method == other.method

    def __hash__(self):
        return hash( (self.path, self.method) )

    def __str__(self):
        return self.method + ":" + self.path
    
    def __repr__(self):
        return str(self)


def parse_rate_header(headers, target, conversion_func):
    if target in headers:
        return conversion_func( headers[target] )
    return None


class RateLimitInfo:
    def __init__(self, headers):
        self.limit = parse_rate_header(headers, "X-RateLimit-Limit", int)
        self.remaining = parse_rate_header(headers, "X-RateLimit-Remaining", int)
        self.reset = parse_rate_header(headers, "X-RateLimit-Reset", float)
        self.reset_after = parse_rate_header(headers, "X-RateLimit-Reset-After", float)
        self.bucket = parse_rate_header(headers, "X-RateLimit-Bucket", str)
        self.is_global = parse_rate_header(headers, "X-RateLimit-Global", bool)
        self.scope = parse_rate_header(headers, "X-RateLimit-Scope", str)

    def __str__(self):
        return f"RateInfo{{remaining={self.remaining}, reset={self.reset}, reset_after={self.reset_after}}}"
    
    def __repr__(self):
        return str(self)


class GlobalLimiter:
    def __init__(self):
        self._next_refresh = time.time()
        self._limit = 50
        self._remaining = self._limit
        self._refresh_period = 1
        
        self._open = asyncio.Event()
        self._open.set()
        self._sleeping = 0
    
    async def wait(self):
        await self._open.wait()

        while self._remaining == 0:
            if self._next_refresh > time.time():
                await asyncio.sleep(self._next_refresh - time.time())
                await self._open.wait()
            # only refresh if we are the first one who woke up
            if self._remaining == 0:
                self._refresh()
        
        self._remaining -= 1

    async def handle_limit(self, error_json):
        if not error_json.get("global"):
            return
        self._sleeping += 1
        self._open.clear()
        await asyncio.sleep(error_json["retry_after"])
        self._sleeping -= 1
        if self._sleeping == 0:
            self._open.set()
            self._refresh()

    def _refresh(self):
        self._next_refresh = time.time() + self._refresh_period
        self._remaining = self._limit


class Bucket:
    def __init__(self, rate: RateLimitInfo):
        self.remaining = None
        self.reset_at = None    
        self._lock = asyncio.Lock()
        self.update(rate)

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, ex_type, ex_val, ex_traceback):
        self._lock.release()

    async def wait(self) -> None:
        if self.remaining == 0:
            print("Slow down buddy!")
            wait_for = self.reset_at - time.time()
            if wait_for > 0:
                await asyncio.sleep(wait_for)

    def update(self, rate: RateLimitInfo) -> None:
        self.remaining = rate.remaining
        # primarily use 'rate.reset_after' since our clock might not by synchronized with discord
        # (mine seems to be running several seconds out of sync)
        if not rate.reset_after:
            raise Exception("No reset_after.")
        self.reset_at = time.time() + rate.reset_after

    def __str__(self) -> str:
        return f"Bucket{{remaining={self.remaining}, reset_after={self.reset_at-time.time()}}}"

    def __repr__(self) -> str:
        return str(self)


class DefaultBucket:
    async def __aenter__(self):
        return self

    async def __aexit__(self, ex_type, ex_val, ex_traceback):
        return 

    async def wait(self):
        return

    def __str__(self) -> str:
        return "DefaultBucket"

    def __repr__(self) -> str:
        return str(self)


class DiskordHttpError(Exception):
    def __init__(self, code, reason, error_json=None):
        self.code = code
        self.reason = reason
        self.error_json = error_json

        
class HttpClient:

    BASE_URL = "https://discord.com/api/v9"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._token = None

        # rate limiting stuff
        self._route_to_bucket: Dict[Route, str] = {}
        self._buckets: Dict[str, Bucket] = {}
        self._global_limiter = GlobalLimiter()
        self._default_bucket = DefaultBucket()

    async def post(self, url, data):
        return await self.send_request("POST", url, data)

    async def get(self, path):
        return await self.send_request("GET", path)

    async def close_session(self):
        if self._session:
            await self._session.close()

    async def open_session(self):
        if self._session:
            raise Exception("Can't open a new session: a session already exists.")
        self._session = aiohttp.ClientSession()
    
    def _get_bucket(self, route: Route) -> Union[Bucket, DefaultBucket]:
        bucket_id = self._route_to_bucket.get(route)
        if not bucket_id:
            return self._default_bucket
        bucket = self._buckets.get(bucket_id)
        return bucket if bucket else self._default_bucket

    async def send_request(self, method: str, path: str, json_data=None, headers=None, params=None):
        if not self._token:
            raise Exception("HttpClient: send_request: no token set!")

        route = Route(path, method)
        url = self.BASE_URL + path
        
        if not headers:
            headers = {}

        # add required headers if not provided by the client
        if "Authorization" not in headers:
            headers["Authorization"] = "Bot " + self._token
        if "User-Agenet" not in headers:
            headers["User-Agent"] = "DiscordBot (diskord-pie)"
        
        for i in range(4):
            async with self._get_bucket(route) as bucket:
                await bucket.wait()
                await self._global_limiter.wait()
                
                async with self._session.request(method=method, url=url, json=json_data, headers=headers, params=params) as r:
                    print(f"received HTTP response with code {r.status}")

                    rate = RateLimitInfo(r.headers)
                    
                    if rate.bucket:
                        if rate.bucket not in self._buckets:
                            self._buckets[rate.bucket] = Bucket(rate)
                        else:
                            self._buckets[rate.bucket].update(rate)
                        self._route_to_bucket[route] = rate.bucket
                    
                    # rate limit exceeded
                    if r.status == 429:
                        print(f"WARNING: route {route} is being rate limited!")
                        data = await r.json()
                        if data["global"]:
                            await self._global_limiter.handle_limit(data)
                        else:
                            bucket.remaining = 0
                            bucket.reset_at = time.time() + data["retry_after"]   
                        continue

                    # the request was ok
                    if 200 <= r.status and r.status < 300:
                        return await r.json()
                    
                    # TODO: possibly handle other status codes 
                    #       https://discord.com/developers/docs/topics/opcodes-and-status-codes

                    raise DiskordHttpError(r.status, r.reason)
