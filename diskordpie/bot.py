from .gateway import GatewayDisconnected, Gateway, ReconnectGateway



class Bot:

    def __init__(self):
        self._gateway = Gateway()
        self._session_id = None

    async def run(self, token: str):
        await self._gateway.connect(token)

        while True:
            msg = await self._gateway.receive()
            
            event_type = msg["t"]
            data = msg["d"]

            if event_type == "READY":
                self._session_id = data["session_id"]
                # TODO: store the rest of information
            else:
                print("Event received:")
                print(f"    op:   {msg['op']}")
                print(f"    type: {msg['t']}")
    