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
from .commands import SlashCommand, Interaction
from .entities import User, Application
from .api import DiscordAPI

__all__ = [ "Bot" ]

_logger = logging.getLogger(__name__)


class Bot:

    def __init__(self):
        self._session_id = None
        self._http_session = None
        self._http = None
        self._gateway = None
        self._commands = []
        self._api = None

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

            self._api = DiscordAPI(self._http, self.app)

            for cmd in self._commands:
                await self._api.create_slash_command(cmd)

        elif event.type == "RESUMED":
            print("Resuming finished.")
        elif event.type == "MESSAGE_CREATE":
            print("Message: " + event.data["content"])  
        elif event.type == "INTERACTION_CREATE":
            _logger.info(f"Interaction received: {event.data['type']}")
            interaction = Interaction(self._http, event.data)
            for cmd in self._commands:
                if cmd._id == interaction._cmd_id:
                    await self.invoke_command(cmd, interaction)
        else:
            print(f"Event received: {event.type}")
            print(f"{event.data}")

    async def invoke_command(self, cmd: SlashCommand, interaction: Interaction):
        args = {}

        for arg in interaction._args:
            opt = None
            for o in cmd.options:
                if o.name == arg.name:
                    opt = o
                    break
            if opt is None:
                raise Exception("Unknown option in interaction.")
            args[opt._arg_name] = arg.value
        
        await cmd.invoke(interaction, **args)

    def slash_command(self, name=None, description=None, options=None):
        def dec(func):
            cmd = SlashCommand(func, name=name, description=description, options=options)
            self._commands.append(cmd)
            return cmd
        return dec
    