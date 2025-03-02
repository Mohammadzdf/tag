import configparser
import asyncio
from telethon import TelegramClient, events

config = configparser.ConfigParser()
config.read('config.ini')

api_id = config['telegram']['api_id']
api_hash = config['telegram']['api_hash']
phone_number = config['telegram']['phone_number']

last_reply = {}
bot_messages = {}
admins = set()
rtag_active = {}
group_messages = {}
join_text = "👋 جوین شو!"  # متن پیش‌فرض برای ریپلای

client = TelegramClient('session_name', api_id, api_hash)

async def fetch_previous_messages(group_id):
    group_messages[group_id] = []
    async for message in client.iter_messages(group_id, limit=500):
        group_messages[group_id].append(message)

@client.on(events.NewMessage(incoming=True))
async def store_messages(event):
    group_id = event.chat_id
    if group_id not in group_messages:
        group_messages[group_id] = []
    group_messages[group_id].append(event.message)

@client.on(events.NewMessage(pattern=r'^rtag$'))
async def rtag_handler(event):
    group_id = event.chat_id
    sender_id = event.sender_id

    if sender_id not in admins:
        return

    if group_id not in group_messages or not group_messages[group_id]:
        await event.reply("هیچ پیامی برای ریپلای وجود ندارد.")
        return

    rtag_active[group_id] = True

    count = 0
    for message in reversed(group_messages[group_id]):
        if not rtag_active.get(group_id, False):
            await event.reply("🚫 فرایند تگ متوقف شد.")
            return

        if message.sender_id not in last_reply.get(group_id, {}):
            reply_msg = await message.reply(join_text)  # استفاده از متن جوین شو
            bot_messages.setdefault(group_id, []).append(reply_msg.id)
            last_reply.setdefault(group_id, {})[message.sender_id] = True
            count += 1
            await asyncio.sleep(2.5)

        if count >= 500:
            break

    await event.reply(f"✅ {count} نفر تگ شدند.")
    rtag_active[group_id] = False

@client.on(events.NewMessage(pattern=r'^stop$'))
async def stop_handler(event):
    group_id = event.chat_id
    sender_id = event.sender_id

    if sender_id not in admins:
        return

    rtag_active[group_id] = False

    if group_id in bot_messages:
        await client.delete_messages(group_id, bot_messages[group_id])
        bot_messages[group_id] = []

    async for msg in client.iter_messages(group_id, from_user='me'):
        await msg.delete()

    await event.reply("✅ فرایند تگ متوقف و تمام پیام‌های من حذف شد.")

@client.on(events.NewMessage(pattern=r'^del$'))
async def del_handler(event):
    group_id = event.chat_id
    sender_id = event.sender_id

    if sender_id not in admins:
        return

    if group_id in last_reply:
        last_reply[group_id] = {}
        await event.reply("✅ لیست کاربران تگ‌شده پاک شد.")
    else:
        await event.reply("لیستی برای حذف وجود ندارد.")

@client.on(events.NewMessage(pattern=r'^promote$'))
async def promote_handler(event):
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        new_admin_id = reply_msg.sender_id
        admins.add(new_admin_id)
        await event.reply(f"✅ کاربر {new_admin_id} به لیست ادمین‌ها اضافه شد.")
    else:
        await event.reply("❌ برای اضافه کردن ادمین، روی پیام کاربر ریپلای کنید.")

@client.on(events.NewMessage(pattern=r'^settext$'))
async def settext_handler(event):
    global join_text
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        join_text = reply_msg.text  # ذخیره متن جدید
        await event.reply("✅ متن جوین شو تغییر کرد.")
    else:
        await event.reply("❌ برای تغییر متن جوین شو، روی پیام دلخواه ریپلای کنید.")

@client.on(events.NewMessage(pattern=r'^help$'))
async def help_handler(event):
    help_text = (
        "📌 **دستورات ربات:**\n"
        "🔹 `rtag` - تگ کردن پیام‌های کاربران\n"
        "🔹 `stop` - متوقف کردن `rtag` و حذف پیام‌های ربات\n"
        "🔹 `del` - حذف لیست کاربران تگ‌شده\n"
        "🔹 `promote` - اضافه کردن ادمین جدید (ریپلای روی پیام)\n"
        "🔹 `settext` - تغییر متن جوین شو (ریپلای روی پیام)\n"
        "🔹 `help` - نمایش این راهنما"
    )
    await event.reply(help_text)

async def main():
    await client.start(phone_number)
    me = await client.get_me()
    admins.add(me.id)

    async for dialog in client.iter_dialogs():
        if dialog.is_group:
            await fetch_previous_messages(dialog.id)

    print("✅ ربات در حال اجرا است...")

    await client.run_until_disconnected()

client.loop.run_until_complete(main())
