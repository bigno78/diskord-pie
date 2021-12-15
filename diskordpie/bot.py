import asyncio
import asyncio
import aiohttp
import logging

from .http import HttpClient
from .gateway import (
    GatewayDisconnected, 
    Gateway, 
    ReconnectGateway,
    GatewayEvent,
)
from .commands import SlashCommand
from .entities import User, Application

__all__ = [ "Bot" ]

_logger = logging.getLogger(__name__)


class Bot:

    def __init__(self):
        self._session_id = None
        self._http_session = None
        self._http = None
        self._gateway = None
        self._commands = []

        self.user = None
        self.app = None

    def run(self, token: str):
        asyncio.run(self._run(token))

    async def _run(self, token: str):
        # apparently ClientSession has to be created in a coroutine 
        # so let's initialize everything here
        self._http_session = aiohttp.ClientSession()
        self._http = HttpClient(self._http_session)
        self._http._token = token
        self._gateway = Gateway(self._http_session, self._http)
        
        await self._gateway.connect(token)

        while True:
            try:
                event = await self._gateway.next_event()
                await self._dispatch_event(event)
            except ReconnectGateway as e:
                _logger.warning(f"Attempting to reconnect: resume={e.resume}.")
                await self._gateway.connect(token, resume=e.resume)
            except GatewayDisconnected as e:
                _logger.error(f"Gateway connection lost forever :(.")
                break

    async def _dispatch_event(self, event: GatewayEvent):
        if event.type == "READY":
            _logger.info(f"Connected to gateway version {event.data['v']} as shard {event.data.get('shard')}")
            self._session_id = event.data["session_id"]
            self.user = User(**event.data["user"])
            self.app = Application(**event.data["application"])
            _logger.info(f"Bot user is {self.user.username}")
            _logger.info(f"App is {self.app.id}")
        elif event.type == "RESUMED":
            print("Resuming finished.")
        elif event.type == "MESSAGE_CREATE":
            print("Message: " + event.data["content"])            
        else:
            print("Event received:")
            print(f"    type: {event.type}")

    def slash_command(self, name=None, description=None, options=None):
        def dec(func):
            cmd = SlashCommand(func, name=name, description=description, options=options)
            self._commands.append(cmd)
            return cmd
        return dec
    