import asyncio
from typing import Union


import telethon
from telethon import events
from telethon.tl import types

from pytgvoip_telethon.incoming_call import VoIPIncomingCall
from pytgvoip_telethon.outgoing_call import VoIPOutgoingCall


class VoIPService:
    incoming_call_class = VoIPIncomingCall
    outgoing_call_class = VoIPOutgoingCall

    def __init__(self, client: telethon.TelegramClient, receive_calls=True):
        self.client = client
        self.incoming_call_handlers = []
        if receive_calls:
            client.add_event_handler(self.update_handler, events.raw.Raw)
        # client.on_message()

    def get_incoming_call_class(self):
        return self.incoming_call_class

    def get_outgoing_call_class(self):
        return self.outgoing_call_class

    def on_incoming_call(self, func) -> callable:
        self.incoming_call_handlers.append(func)
        return func

    async def start_call(self, user_id: Union[str, int]):
        call = self.get_outgoing_call_class()(user_id, client=self.client)
        await call.request()
        return call

    def update_handler(self, event):
        print('========',event)
        update = event
        if isinstance(update, types.UpdatePhoneCall):
            call = update.phone_call
            if isinstance(call, types.PhoneCallRequested):
                async def _():
                    voip_call = self.get_incoming_call_class()(call, client=self.client)
                    for handler in self.incoming_call_handlers:
                        asyncio.iscoroutinefunction(handler) and asyncio.ensure_future(handler(voip_call),
                                                                                       loop=self.client.loop)
                asyncio.ensure_future(_(), loop=self.client.loop)
        return
