import aiohttp
import asyncio
import sys
import random
import logging
import time

from enum import IntEnum

from . import http


__all__ = [ "Gateway", "ReconnectGateway", "GatewayDisconnected" ]

_logger = logging.getLogger(__name__)


class ReconnectGateway(Exception):
    
    def __init__(self, resume):
        self.resume = resume


class GatewayDisconnected(Exception):

    def __init__(self, code=None):
        self.code = code


class GatewayEvent:

    def __init__(self, event_json) -> None:
        if event_json["op"] != 0:
            raise Exception("Can't create Event from non DISPATCH message.")

        self.type = event_json["t"]
        self.data = event_json["d"]


class CloseCode(IntEnum):
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

def _close_code_str(code: int):
    try:
        c = CloseCode(code)
        return str(c)
    except ValueError:
        return "UNKNOWN_CODE"


class OpCode(IntEnum):
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


class Gateway:

    GET_GATEWAY_PATH = "/gateway/bot"

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
            _logger.error("Can't resume without session_id!")
            raise ReconnectGateway(resume=False)
        
        self.resuming = resume
        self._token = token

        try:
            gateway_url = await self._get_gateway_url(token)
            gateway_url += "?v=9&encoding=json"
            
            _logger.debug("Connecting websocket to url: " + gateway_url)
            self._ws = await self._session.ws_connect(gateway_url)

            # receive hello message
            hello_msg = await self._receive()
            if not hello_msg["op"] == OpCode.HELLO:
                raise RuntimeError("First msg received was not HELLO.")
            interval = hello_msg["d"]["heartbeat_interval"]

            _logger.info(f"Starting heartbeat with interval {interval} ms")

            # start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeater(interval))
            
            # send identify message or resume
            if not resume:
                await self._identify(token)
            else:
                await self._resume(token)

        except Exception as e:
            _logger.error("Exception when connecting to the gateway!")
            await self.close()
            raise e

    async def next_event(self) -> GatewayEvent:
        while True:
            data = await self._receive()
            op = data["op"]

            if op == OpCode.DISPATCH:
                _logger.debug(f"Received event {data['t']}")
                if data["t"] == "READY":
                    # steal the session id for ourselves before handing the event over
                    self._session_id = data["d"]["session_id"]
                if data["t"] == "RESUMED":
                    self.resuming = False
                return GatewayEvent(data)
            
            if op == OpCode.HEARTBEAT:
                _logger.debug("Request to send hearbeat received.")
                self._send_heartbeat()
            elif op == OpCode.RECONNECT:
                # we should immediately reconnect and resume
                _logger.warning("We were requested to reconnect.")
                await self.close()
                raise ReconnectGateway(resume=True)
            elif op == OpCode.INVALID_SESSION:
                if self.resuming:
                    _logger.warning("Resuming failed. Sending identify instead.")
                    await asyncio.sleep(random.uniform(1, 5))
                    await self._identify(self._token)
                else:
                    _logger.warning(f"Received INVALID_SESSION. Should reconnect = {data['d']}")
                    raise ReconnectGateway(resume=data["d"])
            elif op == OpCode.HELLO:
                _logger.warning("Unexpected HELLO message.")
            elif op == OpCode.HEARTBEAT_ACK:
                _logger.debug("Hearbeat acked.")
                self._heartbeat_acked = True
            else:
                raise Exception(f"Gateway received unknown opcode {op}")

    async def _identify(self, token):
        _logger.info("Sending identify.")
        data = {
            "op": OpCode.IDENTIFY,
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
        _logger.info("Attempting to resume.")
        data = {          
            "op": OpCode.RESUME,
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
            _logger.warning("Discord is recomending to use more shards then one! Your bot might be too large.")
        return data["url"]
            
    async def _receive(self):
        msg = await self._ws.receive()

        if msg.type == aiohttp.WSMsgType.TEXT or msg.type == aiohttp.WSMsgType.BINARY:
            json_data = msg.json()
            if json_data.get("s"):
                self._seq = json_data["s"]
            return json_data

        if msg.type in [ aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING ]:
            code = self._ws.close_code
            _logger.info(f"WebSocket closed with code {code} {_close_code_str(code)} and data '{msg.data}'")

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
            _logger.error("Websocket received an error.")
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
                # as per discord documentation close the websocket with non-1000 code
                # and attempt to resume
                _logger.warning(f"Hartbeat was not acked! Closing the websocket.")
                await self._ws.close(code=CloseCode.NO_HEARTBEAT_ACK)
            
            _logger.debug("Sending heartbeat.")
            self._heartbeat_acked = False
            await self._send_heartbeat()

            await asyncio.sleep(seconds)
    
    async def _end_heartbeat(self):
        if not self._heartbeat_task:
            return

        if not self._heartbeat_task.done() and not self._heartbeat_task.cancelled():
            self._heartbeat_task.cancel()
        
            # wait for the task to be cancelled
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                _logger.error(f"Unexpected exception when canceling heartbeat:\n{e}")

    async def _send_heartbeat(self):
        data = {
            "op": OpCode.HEARTBEAT,
            "d": self._seq
        }
        await self._ws.send_json(data)
