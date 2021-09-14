import aiohttp
import asyncio
import sys


class Gateway:

    BASE_URL = "https://discord.com/api/v9"
    GET_GATEWAY_URL = BASE_URL + "/gateway/bot"

    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE_UPDATE = 3
    VOICE_STATE_UPDATE = 4
    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

    def __init__(self) -> None:
        self._seq = None
        self._session = None
        self._ws = None
        self._heartbeat_task = None

    async def connect(self, token) -> None:
        self._session = aiohttp.ClientSession()
        
        try:
            gateway_url = await self._get_gateway_url(token)
            self._ws = await self._session.ws_connect(gateway_url)

            # receive hello message
            hello_msg = await self._receive()
            if not hello_msg["op"] == self.HELLO:
                raise RuntimeError("First msg received was not HELLO.")
            interval = hello_msg["d"]["heartbeat_interval"]

            # start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeater(interval))
        
            # send identify message
            data = {
                "op": self.IDENTIFY,
                "d": {
                    "token": token,
                    "intents": 1 << 9,
                    "properties": {
                        "$os": sys.platform,
                        "$browser": "my_library",
                        "$device": "my_library"
                    }
                }
            }
            await self.send(data)
            data = await self.receive()
            print(data)

        except Exception as e:
            print("Exception when connecting!!!!!")
            if not self._session.closed:
                await self._session.close()
            raise e

    async def _get_gateway_url(self, token):
        headers = {
            "Authorization": "Bot " + token,
            "User-Agent": "DiscordBot (diskordos 0.0.1)"
        }

        params = {
            "v": 9,
            "encoding": "json"
        }

        # the number of retries in case of rate limiting after which
        # we give up and assume we are banned
        retries = 3

        for _ in range(retries):
            async with self._session.get(Gateway.GET_GATEWAY_URL, headers=headers, params=params) as r:
                data = await r.json()

                # the request was ok
                if 200 <= r.status and r.status < 300:
                    return data["url"]

                # rate limit exceeded
                if r.status == 429:
                    retry_after = data["retry_after"]
                    asyncio.sleep(retry_after)
                    continue

                raise RuntimeError(f"Request for gateway URL failed with code {r.status} - {r.reason}")

    async def receive(self):
        data = self._receive()

        while data["op"] != self.DISPATCH:
            if data["op"] == self.HEARTBEAT:
                self._send_heartbeat()
            if data["op"] == self.RECONNECT:
                pass
            if data["op"] == self.INVALID_SESSION:
                pass
            if data["op"] == self.HELLO:
                pass
            if data["op"] == self.HEARTBEAT_ACK:
                pass

        return data

    async def _receive(self):
        msg = await self._ws.receive()

        if msg.type == aiohttp.WSMsgType.TEXT or msg.type == aiohttp.WSMsgType.BINARY:
            json_data = msg.json()
            if "s" in json_data:
                self._seq = json_data["s"]
            return json_data

        if msg.type == aiohttp.WSMsgType.CLOSE or msg.type == aiohttp.WSMsgType.CLOSED:
            print("WebSocket closed.")
            raise RuntimeError(msg.data)

        if msg.type == aiohttp.WSMsgType.ERROR:
            print("WebSocket error.")
            raise RuntimeError(msg.data)

        raise RuntimeError("Received unknown data from WebSocket:", msg)


    async def send(self, data):
        await self._ws.send_json(data)

    async def close(self):
        self._heartbeat_task.cancel()
        
        # wait for the task to be cancelled
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        except Exception:
            print("Error when cancelling heartbeat task.")

        # close the websocket
        await self._ws.close()

        # close the session object
        await self._session.close()

    async def _send_heartbeat(self):
        data = {
            "op": 1,
            "d": self._seq
        }
        await self._ws.send_json(data)

    async def _heartbeater(self, interval):
        seconds = interval/1000

        while True:
            await asyncio.sleep(seconds)
            if self._ws.closed:
                break
            await self._send_heartbeat()

