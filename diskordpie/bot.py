import asyncio
from diskordpie.http import HttpClient
from .gateway import GatewayDisconnected, Gateway, ReconnectGateway
import asyncio


class Bot:

    def __init__(self):
        self._gateway = Gateway()
        self._session_id = None
        self._http = HttpClient()

    def run(self, token: str):
        asyncio.run(self._run(token))

    async def _run(self, token: str):
        await self._gateway.connect(token)

        while True:
            try:
                msg = await self._gateway.receive()
                await self._dispatch_event(msg)
            except ReconnectGateway as e:
                print(f"Attempting to reconnect: resume={e.resume}.")
                await self._gateway.connect(e.resume)
            except GatewayDisconnected as e:
                print(f"Gateway connection lost forever :(.")
                break

    async def _dispatch_event(self, event):
        event_type = event["t"]
        data = event["d"]

        if event_type == "READY":
            self._session_id = data["session_id"]
            # TODO: store the rest of information
        else:
            print("Event received:")
            print(f"    op:   {event['op']}")
            print(f"    type: {event['t']}")
    