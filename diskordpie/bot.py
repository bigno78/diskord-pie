import asyncio
from diskordpie.http import HttpClient
from .gateway import CloseCode, GatewayDisconnected, Gateway, ReconnectGateway
import asyncio
import aiohttp
import time
from .event import DiscordEvent

__all__ = [ "Bot" ]

class Bot:

    def __init__(self):
        self._session_id = None
        self._session_http = None
        self._http = None
        self._gateway = None

    def run(self, token: str):
        asyncio.run(self._run(token))

    async def _run(self, token: str):
        # apparently ClientSession has to be created in a coroutine 
        # so let's initialize everything here
        self._session_http = aiohttp.ClientSession()
        self._http = HttpClient(self._session_http)
        self._http._token = token
        self._gateway = Gateway(self._session_http, self._http)
        
        await self._gateway.connect(token)

        while True:
            try:
                event = await self._gateway.next_event()
                await self._dispatch_event(event)
            except ReconnectGateway as e:
                print(f"Attempting to reconnect: resume={e.resume}.")
                await self._gateway.connect(token, resume=e.resume)
            except GatewayDisconnected as e:
                print(f"Gateway connection lost forever :(.")
                break

    async def _dispatch_event(self, event):
        if event.type == "READY":
            print("Received READY event.")
            self._session_id = event.data["session_id"]
        elif event.type == "RESUMED":
            print("Resuming finished.")
        elif event.type == "MESSAGE_CREATE":
            if event.data["content"] == "resume":
                print("Gonna resume.")
                await self._gateway._ws.close(code=CloseCode.NO_HEARTBEAT_ACK)
            if event.data["content"] == "res":
                print("resing.")
                await self._gateway._end_heartbeat()
            print("Message: " + event.data["content"])            
        else:
            print("Event received:")
            print(f"    type: {event.type}")
    