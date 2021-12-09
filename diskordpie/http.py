import aiohttp
import asyncio
import time


def parse_rate_headers(headers):
    limit = None
    remaining = None
    reset_at = None

    if "X-RateLimit-Limit" in headers:
        limit = int(headers["X-RateLimit-Limit"])

    if "X-RateLimit-Remaining" in headers:
        limit = int(headers["X-RateLimit-Remaining"])

    if "X-RateLimit-Limit" in headers:
        limit = int(headers["X-RateLimit-Limit"])

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


class Bucket:

    def __init__(self, limit, remaning, reset_at):
        self.limit = limit
        self.remaining = remaning
        self.reset_at = reset_at
        
        self._can_proceed = asyncio.Event()
        self._can_proceed.set()

    async def limit_the_rate(self):
        """
        Performs rate limiting. After this method returns
        the calling task is allowed to send one request.

        Checks whether there are any requests left in the bucket
        and if not waits for it to reset.
        """
        await self._can_proceed.wait()

        if time.time() >= self.reset_at:
            # allow this task to continue but let others wait
            # until this task receives a response from discord and calls update
            # so we know how to correctly update 'reset_at' and 'remaining'
            self._can_proceed.clear()
            return
        
        if self.remaining > 0:
            # it is not time to reset and we still have some requests
            # so let the task continue
            self.remaining -= 1
            return

        # now we have no request left so everyone has to wait 
        # until this task resets the bucket
        self._can_proceed.clear()
        if time.time() < self.reset_at:
            await asyncio.sleep(self.reset_at - time.time())

        # allow the task to send the request but don't set the _can_proceed flag yet
        # we have to wait for the task to call update() with the rate limiting
        # information received from discord
        
    def update(self, headers):
        """
        Updates the bucket with newly received rate limiting headers.
        Should be called after every succesfuly received response.
        """

        # we definitely dont wanna update 'remaining'
        # if the 'new_remaining' is higher, since between the time
        # the server generated this answer and this method was called
        # other tasks might have sent their requests

        if not self._can_proceed.is_set():
            # we are the task who is reseting the bucket
            # TODO: stuff
            self._can_proceed.set()


class GlobalBucket(Bucket):

    def __init__(self, limit, remaning, reset_at):
        super().__init__(limit, remaning, reset_at)

    async def limit_the_rate(self):
        await self._can_proceed.wait()

        if self.remaining > 0:
            self.remaining -= 1
            return

        self._can_proceed.clear()
        await asyncio.sleep(1)
        self.remaining = self.limit - 1
        self._can_proceed.set()


class DiskordHttpError(Exception):
    def __init__(self, code, reason, error_json=None):
        self.code = code
        self.reason = reason
        self.error_json = error_json

        


class HttpClient:

    BASE_URL = "https://discord.com/api/v9"

    def __init__(self) -> None:
        self._session = aiohttp.ClientSession()
        self._token = None

        # rate limiting stuff
        self._route_to_bucket = {} # maps routes to bucket ids
        self._buckets = {} # maps bucket ids to Bucket objects
        self._global_bucket = Bucket(limit=50, remaning=50, reset_at=1+time.time())

    async def close_session(self):
        await self._session.close()

    async def open_session(self):
        if self._session:
            raise Exception("Can't open a new session: a session already exists.")
        self._session = aiohttp.ClientSession()

    async def post(self, url, data):
        self.send_request("POST", url, data)

    async def get(self, url, data):
        self.send_request("GET", url, data)

    async def send_request(self, method: str, path: str, json_data=None, headers=None, params=None):
        if not self._token:
            raise Exception("HttpClient: send_request: no token set!")

        url = self.BASE_URL + path
        
        if not headers:
            headers = {}

        # add required headers if not provided by the client
        if "Authorization" not in headers:
            headers["Authorization"] = "Bot " + self._token
        if "User-Agenet" not in headers:
            headers["User-Agent"] = "DiscordBot (diskordos 0.0.1)"

        # let's attempt to send the request 5 times
        for i in range(5):
            async with self._session.request(method=method, url=url, json=json_data, headers=headers, params=params) as r:
                data = await r.json()

                # the request was ok
                if 200 <= r.status and r.status < 300:
                    return data["url"]

                # rate limit exceeded
                if r.status == 429:
                    retry_after = data["retry_after"]
                    await asyncio.sleep(retry_after)
                    continue
                
                # TODO: possibly handle other status codes 
                #       https://discord.com/developers/docs/topics/opcodes-and-status-codes

                raise DiskordHttpError(r.status, r.reason, data)

    def _get_bucket(self, path, method) -> Bucket:
        return self._buckets[ self._route_to_bucket[Route(path, method)] ]
