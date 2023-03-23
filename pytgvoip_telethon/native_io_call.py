from collections import deque
from typing import Union, List, IO

from pytgvoip_telethon import VoIPOutgoingCall, VoIPIncomingCall, VoIPService
from pytgvoip_telethon.base_call import VoIPCallBase


class VoIPNativeIOCallMixin(VoIPCallBase):
    def __init__(self, *args, **kwargs):
        super(VoIPNativeIOCallMixin, self).__init__(*args, **kwargs)
        self.ctrl.native_io = True

    def play(self, path: str):
        return self.ctrl.play(path)

    def play_on_hold(self, paths: List[str]):
        self.ctrl.play_on_hold(paths)

    def set_output_file(self, path: str):
        return self.ctrl.set_output_file(path)

    def clear_play_queue(self):
        self.ctrl.clear_play_queue()

    def clear_hold_queue(self):
        self.ctrl.clear_hold_queue()

    def unset_output_file(self):
        self.ctrl.unset_output_file()


class VoIPOutgoingNativeIOCall(VoIPNativeIOCallMixin, VoIPOutgoingCall):
    pass


class VoIPIncomingNativeIOCall(VoIPNativeIOCallMixin, VoIPIncomingCall):
    pass


class VoIPNativeIOService(VoIPService):
    incoming_call_class = VoIPIncomingNativeIOCall
    outgoing_call_class = VoIPOutgoingNativeIOCall
