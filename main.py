import configparser
import asyncio
import threading
import time
import requests
from flask import Flask
from telethon import TelegramClient, events

# خواندن اطلاعات از فایل config.ini
config = configparser.ConfigParser()
config.read('config.ini')

api_id = int(config['telegram']['api_id'])  # مقدار را به عدد تبدیل می‌کنیم
api_hash = config['telegram']['api_hash']
phone_number = config['telegram']['phone_number']

# متغیرهای ربات
last_reply = {}
bot_messages = {}
admins = set()
rtag_active = {}
group_messages = {}
join_text = "👋 جوین شو!"  # متن پیش‌فرض برای ریپلای

# راه‌اندازی کلاینت Telethon
client = TelegramClient('session_name', api_id, api_hash)

async def fetch_previous_messages(group_id):
    """دریافت پیام‌های قبلی گروه"""
    group_messages[group_id] = []
    async for message in client.iter_messages(group_id, limit=500):
        group_messages[group_id].append(message)

@client.on(events.NewMessage(incoming=True))
async def store_messages(event):
    """ذخیره پیام‌های جدید در گروه"""
    group_id = event.chat_id
    if group_id not in group_messages:
        group_messages[group_id] = []
    group_messages[group_id].append(event.message)

@client.on(events.NewMessage(pattern=r'^rtag$'))
async def rtag_handler(event):
    """اجرای تگ گروهی"""
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
    """متوقف کردن فرآیند تگ و حذف پیام‌های ربات"""
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
    """حذف لیست کاربران تگ شده"""
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
    """اضافه کردن ادمین جدید"""
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        new_admin_id = reply_msg.sender_id
        admins.add(new_admin_id)
        await event.reply(f"✅ کاربر {new_admin_id} به لیست ادمین‌ها اضافه شد.")
    else:
        await event.reply("❌ برای اضافه کردن ادمین، روی پیام کاربر ریپلای کنید.")

@client.on(events.NewMessage(pattern=r'^settext$'))
async def settext_handler(event):
    """تغییر متن جوین شو"""
    global join_text
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        join_text = reply_msg.text  # ذخیره متن جدید
        await event.reply("✅ متن جوین شو تغییر کرد.")
    else:
        await event.reply("❌ برای تغییر متن جوین شو، روی پیام دلخواه ریپلای کنید.")

@client.on(events.NewMessage(pattern=r'^help$'))
async def help_handler(event):
    """نمایش راهنما"""
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

async def run_client():
    """اجرای کلاینت تلگرام"""
    await client.start(phone_number)
    me = await client.get_me()
    admins.add(me.id)
    await client.run_until_disconnected()

# اجرای Telethon در یک ترد جداگانه
def start_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_client())

threading.Thread(target=start_telethon, daemon=True).start()

# راه‌اندازی وب‌سرور فیک برای Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# تابع برای ارسال درخواست به خود سرور هر ۳۰ ثانیه
def keep_awake():
    url = "https://tag-1.onrender.com"  # لینک وب سرور در Render (جایگزین کن)
    while True:
        try:
            requests.get(url)
            print("✅ Ping sent to prevent shutdown")
        except Exception as e:
            print(f"⚠️ Ping failed: {e}")
        time.sleep(30)  # هر ۳۰ ثانیه درخواست ارسال شود

# اجرای self-ping در یک ترد جداگانه
threading.Thread(target=keep_awake, daemon=True).start()

# اجرای وب سرور روی پورت 10000
app.run(host="0.0.0.0", port=10000)
