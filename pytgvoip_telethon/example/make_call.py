import asyncio

from tgvoip import VoIPServerConfig
from pytgvoip_telethon import VoIPFileStreamService, VoIPNativeIOService
from pytgvoip_telethon.idle import idle
import telethon


VoIPServerConfig.set_bitrate_config(80000, 100000, 60000, 5000, 5000)
client = telethon.TelegramClient('session', api_id = 19455944, api_hash="a4fc69ed737630feb72a32c88528f442")
loop = asyncio.get_event_loop()
voip_service = VoIPFileStreamService(client, receive_calls=False)  # use VoIPNativeIOService for native I/O


async def main():
    await client.start()

    call = await voip_service.start_call('@jacker0808')
    call.play('/opt/tgvoip_telethon/pytgvoip_telethon/example/input.raw')
    call.play_on_hold(['/opt/tgvoip_telethon/pytgvoip_telethon/example/input.raw'])
    call.set_output_file('/opt/tgvoip_telethon/pytgvoip_telethon/example/output.raw')

    # 调用被丢弃，不一定在之前启动
    @call.on_call_discarded
    def discarded(call):
        print('----------discarded')

    @call.on_call_started
    def state_started(call):
        print('----------Started')

    @call.on_call_accepted
    def accepted(call):
        print('----------accepted')
    
    # @call.on_incoming_call
    # def incoming(call):
    #     print('----------incoming')
    

    @call.on_call_state_changed
    def state_changed(call, state):
        print('State changed:', call, state)

    # you can use `call.on_call_ended(lambda _: app.disconnect())` here instead
    # 由于非繁忙原因，呼叫被丢弃
    @call.on_call_ended
    async def call_ended(call):     
        await client.disconnect()

    # 循环等待中断信号
    await idle(client.loop)

loop.run_until_complete(main())


'''
$ ffmpeg -i input.mp3 -f s16le -ac 1 -ar 48000 -acodec pcm_s16le input.raw  # encode
$ ffmpeg -f s16le -ac 1 -ar 48000 -acodec pcm_s16le -i output.raw output.mp3  # decode
'''