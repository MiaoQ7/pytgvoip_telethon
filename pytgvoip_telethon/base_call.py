import asyncio

# import pyrogram
# from pyrogram import errors
# from pyrogram.raw import functions, types
# from pyrogram.handlers import RawUpdateHandler
import telethon
from telethon import errors,events
from telethon.tl import types, functions
import logging

logger = logging.getLogger(__name__)

from tgvoip import VoIPController, CallState, CallError, Endpoint, DataSaving, VoIPServerConfig
from tgvoip.utils import i2b, b2i, check_g


class DH:
    def __init__(self, dhc: types.messages.DhConfig):
        self.p = b2i(dhc.p)
        self.g = dhc.g
        self.resp = dhc


class VoIPCallBase:
    min_layer = 65
    max_layer = VoIPController.CONNECTION_MAX_LAYER
    is_outgoing = False

    def __init__(self, client: telethon.TelegramClient, use_proxy_if_available: bool = True):
        if not client.is_connected:
            raise RuntimeError('Client must be started first')
        self.client = client
        self.ctrl = VoIPController()
        self.ctrl_started = False
        self.call = None
        self.call_access_hash = None
        self.peer = None
        self.state = None
        self.dhc = None
        self.a = None
        self.g_a = None
        self.g_a_hash = None
        self.b = None
        self.g_b = None
        self.g_b_hash = None
        self.auth_key = None
        self.key_fingerprint = None
        self.call_started_handlers = []
        self.call_discarded_handlers = []
        self.call_ended_handlers = []

        if use_proxy_if_available and client._proxy:
            proxy = self.client._proxy
            self.ctrl.set_proxy(proxy['hostname'], proxy['port'], proxy['username'], proxy['password'])

        # 如何实现事件循环
        # self._updates_handle = 
        # self._updates_handle = self.client.loop.create_task(self.process_update)
        # self._update_handler = RawUpdateHandler(self.process_update)
        # self.client.add_handler(self._update_handler, -1)
        self.client.add_event_handler(self.process_update, events.raw.Raw)

    async def process_update(self, event):
        logger.info('-------',event)
        update = event
        if not isinstance(update, types.UpdatePhoneCall):
            return

        call = update.phone_call
        if not self.call or not call or call.id != self.call.id:
            return
        self.call = call
        if hasattr(call, 'access_hash') and call.access_hash:
            self.call_access_hash = call.access_hash

        if isinstance(call, types.PhoneCallDiscarded):
            self.call_discarded()
            raise events.StopPropagation

    def on_call_started(self, func: callable) -> callable:  # well, the conversation has started
        '''
        '''
        logger.debug("新增 call started 回调")
        print('新增 call started 回调')
        self.call_started_handlers.append(func)
        return func

    def on_call_discarded(self, func: callable) -> callable:  # call was discarded, not necessarily started before
        logger.debug("新增 call discarded 回调")
        print('新增 call discarded 回调')
        self.call_discarded_handlers.append(func)
        return func

    def on_call_ended(self, func: callable) -> callable:  # call was discarded with non-busy reason
                                                          # (was started and then discarded?)
        logger.debug("新增 on_call_ended 回调")
        print('新增 on_call_ended 回调')
        self.call_ended_handlers.append(func)
        return func

    def on_call_state_changed(self, func: callable) -> callable:
        logger.debug("新增 call_state_changed 回调")
        print('新增 call_state_changed 回调')
        if callable(func):
            self.ctrl.call_state_changed_handlers.append(lambda state: (func(self, state),print('-------call_state_changed_handlers')))
        return func

    @property
    def auth_key_bytes(self) -> bytes:
        return i2b(self.auth_key) if self.auth_key is not None else b''

    @property
    def call_id(self) -> int:
        return self.call.id if self.call else 0

    def get_protocol(self) -> types.PhoneCallProtocol:
        return types.PhoneCallProtocol(min_layer=self.min_layer, max_layer=self.max_layer, udp_p2p=True,
                                       udp_reflector=True, library_versions=["2.4.4", "2.7"])

    async def get_dhc(self):
        self.dhc = DH(await self.client._sender.send(functions.messages.GetDhConfigRequest(version=0, random_length=256)))

    def check_g(self, g_x: int, p: int) -> None:
        try:
            check_g(g_x, p)
        except RuntimeError:
            self.call_discarded()
            raise

    def stop(self) -> None:
        async def _():
            try:
                self.client.remove_event_handler(self.process_update, events.raw.Raw)
            except ValueError:
                pass
        asyncio.ensure_future(_())

        del self.ctrl
        self.ctrl = None

        for handler in self.call_ended_handlers:
            asyncio.iscoroutinefunction(handler) and asyncio.ensure_future(handler(self), loop=self.client.loop)

    def update_state(self, val: CallState) -> None:
        self.state = val
        self.ctrl.update_state(val)

    def call_ended(self) -> None:
        self.update_state(CallState.ENDED)
        self.stop()

    def call_failed(self, error: CallError = None) -> None:
        if error is None:
            error = self.ctrl.get_last_error() if self.ctrl and self.ctrl_started else CallError.UNKNOWN
        print('Call', self.call_id, 'failed with error', error)
        self.update_state(CallState.FAILED)
        self.stop()

    def call_discarded(self):
        # TODO: call.need_debug
        need_rate = self.ctrl and VoIPServerConfig.config.get('bad_call_rating') and self.ctrl.need_rate()
        if isinstance(self.call.reason, types.PhoneCallDiscardReasonBusy):
            self.update_state(CallState.BUSY)
            self.stop()
        else:
            self.call_ended()
        if self.call.need_rating or need_rate:
            pass  # TODO: rate

        for handler in self.call_discarded_handlers:
            asyncio.iscoroutinefunction(handler) and asyncio.ensure_future(handler(self), loop=self.client.loop)

    async def discard_call(self, reason=None):
        # TODO: rating
        if not reason:
            reason = types.PhoneCallDiscardReasonDisconnect()
        try:
            await self.client._sender.send(functions.phone.DiscardCallRequest(
                peer=types.InputPhoneCall(id=self.call_id, access_hash=self.call_access_hash),
                duration=self.ctrl.call_duration,
                connection_id=self.ctrl.get_preferred_relay_id(),
                reason=reason
            ))
        except (errors.CallAlreadyDeclinedError, errors.CallAlreadyAcceptedError):
            pass
        self.call_ended()

    async def _initiate_encrypted_call(self) -> None:
        config = await self.client._sender.send(functions.help.GetConfigRequest())  # type: types.Config
        self.ctrl.set_config(config.call_packet_timeout_ms / 1000., config.call_connect_timeout_ms / 1000.,
                             DataSaving.NEVER, self.call.id)
        self.ctrl.set_encryption_key(self.auth_key_bytes, self.is_outgoing)
        endpoints = [Endpoint(e.id, e.ip, e.ipv6, e.port, e.peer_tag) for e in self.call.connections]
        self.ctrl.set_remote_endpoints(endpoints, self.call.p2p_allowed, False, self.call.protocol.max_layer)
        self.ctrl.start()
        self.ctrl.connect()
        self.ctrl_started = True
        self.update_state(CallState.ESTABLISHED)

        for handler in self.call_started_handlers:
            asyncio.iscoroutinefunction(handler) and asyncio.ensure_future(handler(self), loop=self.client.loop)
