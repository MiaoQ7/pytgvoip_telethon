import asyncio

import hashlib
from random import randint

import telethon
from telethon import errors, events
from telethon.tl import types, functions

from tgvoip import CallState
from tgvoip.utils import i2b, b2i, calc_fingerprint
from pytgvoip_telethon.base_call import VoIPCallBase

import logging

logger = logging.getLogger(__name__)

class VoIPIncomingCall(VoIPCallBase):
    def __init__(self, call: types.PhoneCallRequested, *args, **kwargs):
        super(VoIPIncomingCall, self).__init__(*args, **kwargs)
        self.call_accepted_handlers = []
        self.update_state(CallState.WAITING_INCOMING)
        self.call = call
        self.call_access_hash = call.access_hash

    async def process_update(self, event):
        await super(VoIPIncomingCall, self).process_update(event)
        if isinstance(self.call, types.PhoneCall) and not self.auth_key:
            await self.call_accepted()
            raise events.StopPropagation

    def on_call_accepted(self, func: callable) -> callable:  # telegram acknowledged that you've accepted the call
        logger.debug("新增呼入 call_accepted 回调")
        self.call_accepted_handlers.append(func)
        return func

    async def accept(self) -> bool:
        self.update_state(CallState.EXCHANGING_KEYS)
        if not self.call:
            self.call_failed()
            raise RuntimeError('call is not set')
        await self.get_dhc()
        self.b = randint(2, self.dhc.p-1)
        self.g_b = pow(self.dhc.g, self.b, self.dhc.p)
        self.g_a_hash = self.call.g_a_hash
        try:
            self.call = (await self.client._sender.send(functions.phone.AcceptCallRequest(
                peer=types.InputPhoneCall(id=self.call_id, access_hash=self.call_access_hash),
                g_b=i2b(self.g_b),
                protocol=self.get_protocol()
            ))).phone_call
            errors.Call
        except errors.CallAlreadyAcceptedError as e:
            self.stop()
            return True
        except errors.CallAlreadyDeclinedError as e:
            self.call_discarded()
            return False
        if isinstance(self.call, types.PhoneCallDiscarded):
            print('Call is already discarded')
            self.call_discarded()
            return False
        return True

    async def call_accepted(self) -> None:
        for handler in self.call_accepted_handlers:
            asyncio.iscoroutinefunction(handler) and asyncio.ensure_future(handler(self), loop=self.client.loop)

        if not self.call.g_a_or_b:
            print('g_a is null')
            self.call_failed()
            return
        if self.g_a_hash != hashlib.sha256(self.call.g_a_or_b).digest():
            print('g_a_hash doesn\'t match')
            self.call_failed()
            return
        self.g_a = b2i(self.call.g_a_or_b)
        self.check_g(self.g_a, self.dhc.p)
        self.auth_key = pow(self.g_a, self.b, self.dhc.p)
        self.key_fingerprint = calc_fingerprint(self.auth_key_bytes)
        if self.key_fingerprint != self.call.key_fingerprint:
            print('fingerprints don\'t match')
            self.call_failed()
            return
        await self._initiate_encrypted_call()
