from asyncio.locks import Event
from re import U
import aiohttp
import asyncio
import sys
from . import http
from .event import DiscordEvent
import random

__all__ = [ "Gateway", "ReconnectGateway", "GatewayDisconnected" ]

class ReconnectGateway(Exception):
    
    def __init__(self, resume):
        self.resume = resume


class GatewayDisconnected(Exception):

    def __init__(self, code=None):
        self.code = code

class CloseCode:
    CLOSE_NORMAL = 1000
    UNKNOWN_ERROR = 4000	
    UNKNOWN_OPCODE = 4001
    DECODE_ERROR = 4002
    NOT_AUTHENTICATED = 4003
    AUTHENTICATION_FAILED = 4004
    ALREADY_AUTHENTICATED = 4005	
    INVALID_SEQ = 4007	
    RATE_LIMITED = 4008	
    SESSION_TIMED = 4009 
    INVALID_SHARD = 4010	
    SHARDING_REQUIRED = 4011	
    INVALID_API_VERSION = 4012	
    INVALID_INTENTS = 4013	
    DISALLOWED_INTENTS = 4014
    NO_HEARTBEAT_ACK = 4420
    
    code_strings = {
        CLOSE_NORMAL: "Normal_close",
        UNKNOWN_ERROR: "Unknown_error",
        UNKNOWN_OPCODE: "Unknown_opcode",
        DECODE_ERROR: "Decode_error",
        NOT_AUTHENTICATED: "Not_authenticated",
        AUTHENTICATION_FAILED: "Authentication_failed",
        ALREADY_AUTHENTICATED: "Already_authenticated",
        INVALID_SEQ: "Invalid_seq",
        RATE_LIMITED: "Rate_limited",
        SESSION_TIMED: "Session_timed",
        INVALID_SHARD: "Invalid_shard",
        SHARDING_REQUIRED: "Sharding_required",
        INVALID_API_VERSION: "Invalid_API_version",
        INVALID_INTENTS: "Invalid_intents",
        DISALLOWED_INTENTS: "Disallowed_intents",
        NO_HEARTBEAT_ACK: "No_heartbeat_ack"
    }

    @staticmethod
    def description(code: int) -> str:
        if code in CloseCode.code_strings:
            return CloseCode.code_strings[code]
        return "Unknown_close_code"


class Gateway:

    GET_GATEWAY_PATH = "/gateway/bot"

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

    def __init__(self, session: aiohttp.ClientSession, http: http.HttpClient) -> None:
        self._session = session
        self._http = http
        self._seq = None
        self._ws = None
        self._heartbeat_task = None
        self._heartbeat_acked = True
        self._session_id = None
        self._token = None

        self.resuming = False

    async def connect(self, token, resume=False) -> None:
        if resume and not self._session_id:
            print("Can't resume without session_id!")
            raise ReconnectGateway(resume=False)
        
        self.resuming = resume
        self._token = token

        try:
            gateway_url = await self._get_gateway_url(token)

            params = {
                "v": 9,
                "encoding": "json"
            }

            self._ws = await self._session.ws_connect(gateway_url, params=params)

            # receive hello message
            hello_msg = await self._receive()
            if not hello_msg["op"] == self.HELLO:
                raise RuntimeError("First msg received was not HELLO.")
            interval = hello_msg["d"]["heartbeat_interval"]

            # start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeater(interval))
            
            # send identify message or resume
            if not resume:
                await self._identify(token)
            else:
                await self._resume(token)

        except Exception as e:
            print("ERROR: Exception when connecting to the gateway!")
            await self.close()
            raise e

    async def _identify(self, token):
        data = {
            "op": self.IDENTIFY,
            "d": {
                "token": token,
                "intents": 1 << 9,
                "properties": {
                    "$os": sys.platform,
                    "$browser": "diskord-pie",
                    "$device": "diskord-pie"
                }
            }
        }
        await self.send(data)

    async def _resume(self, token):
        data = {          
            "op": self.RESUME,
            "d": {
                "token": token,
                "session_id": self._session_id,
                "seq": self._seq
            }
        }
        await self.send(data)

    async def _get_gateway_url(self, token: str) -> str:
        data = await self._http.get(Gateway.GET_GATEWAY_PATH)
        if data["shards"] > 1:
            print("WARNING: Discord is recomending to use more shards then one!")
        return data["url"]

    async def next_event(self):
        while True:
            data = await self._receive()
            op = data["op"]

            print(f"Received a thingy: ", end="")
            print(repr(op))

            if op == self.DISPATCH:
                if data["t"] == "READY":
                    # steal the session id for ourselves before handing the event over
                    self._session_id = data["d"]["session_id"]
                if data["t"] == "RESUMED":
                    self.resuming = False
                return DiscordEvent(data)
            
            if op == self.HEARTBEAT:
                self._send_heartbeat()
            if op == self.RECONNECT:
                # we should immediately reconnect and resume
                print("We were requested to reconnect.")
                await self.close()
                raise ReconnectGateway(resume=True)
            if op == self.INVALID_SESSION:
                if self.resuming:
                    print("WARNING: Resuming failed. Send identify instead.")
                    await asyncio.sleep(random.uniform(1, 5))
                    await self._identify(self._token)
                else:
                    raise ReconnectGateway(resume=op["d"])
            if op == self.HELLO:
                print("WARNING: Unexpected HELLO message.")
            if op == self.HEARTBEAT_ACK:
                self._heartbeat_acked = True
            
    async def _receive(self):
        msg = await self._ws.receive()
        #print(f"Received a msg: {msg.type}.")

        if msg.type == aiohttp.WSMsgType.TEXT or msg.type == aiohttp.WSMsgType.BINARY:
            json_data = msg.json()
            if json_data.get("s"):
                self._seq = json_data["s"]
            return json_data

        if msg.type == aiohttp.WSMsgType.CLOSE or msg.type == aiohttp.WSMsgType.CLOSED:
            code = self._ws.close_code
            print(f"WebSocket closed with code {code} {CloseCode.description(code)} and data '{msg.data}'")

            await self._end_heartbeat()
            
            # codes for which we will try to resume the session
            if code in [ CloseCode.CLOSE_NORMAL, CloseCode.NO_HEARTBEAT_ACK ]:
                raise ReconnectGateway(resume=True)
            
            # codes for which we will try to reconnect and create new session
            # currently no codes
            if code in [ ]:
                raise ReconnectGateway(resume=False)
            
            # now just give up
            raise GatewayDisconnected(code)

        if msg.type == aiohttp.WSMsgType.ERROR:
            print("WebSocket error.")
            await self._end_heartbeat()
            raise RuntimeError(msg.data)

        raise RuntimeError("Received unknown data from WebSocket:", msg)

    async def send(self, data):
        await self._ws.send_json(data)

    async def close(self):
        if self._ws and not self._ws.closed:
                await self._ws.close()
        if self._heartbeat_task:
            await self._end_heartbeat()

    async def _heartbeater(self, interval_ms):
        seconds = interval_ms/1000

        jitter = seconds * random.random()
        await asyncio.sleep(jitter)
        
        while True:
            if self._ws.closed:
                break
            
            if not self._heartbeat_acked:
                # as per documentation close the websocket with non-1000 code
                # and attempt to resume
                print("Heartbeat was not acked! Closing the websocket.")
                await self._ws.close(code=CloseCode.NO_HEARTBEAT_ACK)
            
            self._heartbeat_acked = False
            await self._send_heartbeat()

            await asyncio.sleep(seconds)
    
    async def _end_heartbeat(self):
        if not self._heartbeat_task:
            return

        print("Ending heartbeat")

        if not self._heartbeat_task.done() and not self._heartbeat_task.cancelled():
            self._heartbeat_task.cancel()
        
            # wait for the task to be cancelled
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                print("ERROR: Unexpected exception when cancelling heartbeat task.")

    async def _send_heartbeat(self):
        data = {
            "op": 1,
            "d": self._seq
        }
        await self._ws.send_json(data)
