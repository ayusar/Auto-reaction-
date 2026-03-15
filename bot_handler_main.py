# © [2026] Malith-Rukshan. All rights reserved.
# Main bot handler — full features

import time
import random
import psutil
from datetime import datetime

import database as db
from constants import START_MESSAGE, DONATE_MESSAGE
from helper import get_random_positive_reaction

_BOT_START_TIME = time.time()
_clone_pending: dict = {}

_DC_RANGES = [
    (1, 999999999, 1), (1000000000, 1999999999, 2),
    (2000000000, 2999999999, 3), (3000000000, 3999999999, 4),
    (4000000000, 9999999999, 5),
]

def get_dc_id(user_id):
    for low, high, dc in _DC_RANGES:
        if low <= user_id <= high:
            return dc
    return 1

def format_datetime():
    now = datetime.now()
    return now.strftime("%d %b %Y"), now.strftime("%I:%M:%S %p")

def format_uptime(seconds):
    seconds = int(seconds)
    d, s = divmod(seconds, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def get_server_stats():
    disk = psutil.disk_usage("/")
    ram  = psutil.virtual_memory()
    return {
        "disk_total": round(disk.total  / (1024**3), 2),
        "disk_used":  round(disk.used   / (1024**3), 2),
        "disk_free":  round(disk.free   / (1024**3), 2),
        "cpu_pct":    psutil.cpu_percent(interval=0.5),
        "ram_pct":    ram.percent,
        "ram_total":  round(ram.total   / (1024**3), 2),
        "ram_used":   round(ram.used    / (1024**3), 2),
        "ram_free":   round(ram.available / (1024**3), 2),
    }

async def log_to_group(bot_api, log_group_id, text):
    if not log_group_id:
        return
    try:
        await bot_api.send_message(int(log_group_id), text)
    except Exception as e:
        print(f"[LOG] Failed: {e}")

async def send_refer_info(chat_id, user_id, bot_api, bot_username):
    stats    = await db.get_refer_stats(user_id)
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share    = f"https://t.me/share/url?url={ref_link}&text=Join%20Auto%20Reaction%20Bot!"
    await bot_api.send_message(
        chat_id,
        f"🔗 *Refer & Earn*\n\n"
        f"Earn *+1 bot slot* for every *{db.REFERS_NEEDED} new referrals*!\n"
        f"Max bonus: *{db.REFER_MAX_BONUS} slots*\n\n"
        f"👥 Total Referrals    : *{stats['refer_count']}*\n"
        f"🎁 Bonus Slots Earned : *{stats['bonus_bots']}*\n"
        f"⏳ Next Bonus In      : *{stats['next_bonus_in']} more*\n\n"
        f"🔗 Your Link:\n`{ref_link}`",
        [[{"text": "📤 Share", "url": share}]],
    )

async def handle_donate(chat_id, bot_api):
    await bot_api.send_message(
        chat_id,
        "💝 *Why Donate to RoyalityBots?*\n\n"
        "• Helps cover server costs\n"
        "• Motivates us to build new bots\n"
        "• Helps buy a cup of tea from Starbucks ☕\n\n"
        "👇 *Choose an amount:*",
        [
            [{"text": "⭐ 5", "callback_data": "donate_5"},
             {"text": "⭐ 10", "callback_data": "donate_10"},
             {"text": "⭐ 20", "callback_data": "donate_20"}],
            [{"text": "⭐ 30", "callback_data": "donate_30"},
             {"text": "⭐ 50", "callback_data": "donate_50"}],
            [{"text": "💳 Custom Amount", "callback_data": "donate_custom"}],
            [{"text": "↩️ Back", "callback_data": "donate_back"}],
        ],
    )

async def handle_clone_command(chat_id, user_id, bot_api, bot_username, reactions, random_level, main_bot_username, log_group_id):
    user  = await db.get_user(user_id)
    limit = await db.get_user_limit(user_id)
    if user["clone_count"] >= limit:
        if user["is_donor"]:
            msg = f"⚠️ You reached your donor limit of *{limit} bots*.\n\nContact owner for help."
        else:
            msg = (f"⚠️ You reached the free limit of *{db.NORMAL_CLONE_LIMIT} bots*.\n\n"
                   f"💝 Donate to unlock up to *{db.DONOR_CLONE_LIMIT} bots*!\n"
                   f"🔗 Or refer friends — /refer\n\nUse /donate to support us.")
        await bot_api.send_message(chat_id, msg)
        return

    _clone_pending[user_id] = "awaiting_token"
    await bot_api.send_message(
        chat_id,
        "🤖 *Clone Bot — Step 1 of 2*\n\n"
        "1️⃣ Open [@BotFather](https://t.me/BotFather)\n"
        "2️⃣ Send `/newbot` and follow the steps\n"
        "3️⃣ Copy your *Bot Token*\n\n"
        "Then *paste your Bot Token here* 👇\n\n"
        "_Example: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`_\n\n"
        "Send /cancel to abort.",
        [[{"text": "👉 Open BotFather", "url": "https://t.me/BotFather"}]],
    )

async def handle_token_input(chat_id, user_id, from_, token, bot_api, bot_username, reactions, random_level, main_bot_username, log_group_id, owner_id_str):
    from clone_manager import start_clone
    _clone_pending.pop(user_id, None)

    await bot_api.send_message(chat_id, "⏳ *Validating your token...*")

    result = await start_clone(
        token=token, owner_id=user_id, reactions=reactions,
        random_level=random_level, main_bot_username=bot_username,
        log_group_id=log_group_id,
    )

    if not result["ok"]:
        await bot_api.send_message(chat_id, f"❌ *Failed*\n\n{result['error']}\n\nCheck your token and try again.")
        return

    await db.save_clone_token(user_id, token, result["username"])
    user  = await db.increment_clone(user_id)
    limit = await db.get_user_limit(user_id)

    await bot_api.send_message(
        chat_id,
        f"✅ *Your bot is now live!*\n\n"
        f"🤖 Bot      : @{result['username']}\n"
        f"📊 Clones   : {user['clone_count']}/{limit}\n\n"
        f"Add @{result['username']} to your groups or channels!\n\n"
        f"_Use /mybots to manage your bots_",
        [[{"text": f"👉 Open @{result['username']}", "url": f"https://t.me/{result['username']}"}]],
    )

    date, time_str = format_datetime()
    dc_id = get_dc_id(user_id)
    uname = f"@{from_.get('username')}" if from_.get("username") else "ɴᴏɴᴇ"
    await log_to_group(bot_api, log_group_id,
        f"👁️‍🗨️ 𝘜𝘚𝘌𝘙 𝘋𝘌𝘛𝘈𝘐𝘓𝘚\n\n"
        f"○ 𝘐𝘋 : `{user_id}`\n○ 𝘋𝘊 : DC{dc_id}\n"
        f"○ 𝘍𝘪𝘳𝘴𝘵 𝘕𝘢𝘮𝘦 : {from_.get('first_name', '')}\n"
        f"○ 𝘜𝘴𝘦𝘳𝘕𝘢𝘮𝘦 : {uname}\n"
        f"• Cloned Bot : @{result['username']}\n"
        f"• Donor : {'✅ Yes' if user['is_donor'] else '❌ No'}\n\n"
        f"𝘉𝘺 = @{bot_username}")

    if owner_id_str:
        try:
            await bot_api.send_message(int(owner_id_str),
                f"🤖 *New Clone*\n\n👤 User: {from_.get('first_name')} (`{user_id}`)\n"
                f"🤖 Bot: @{result['username']}\n📅 {date} {time_str}")
        except Exception:
            pass

async def handle_mybots(chat_id, user_id, bot_api):
    from clone_manager import get_clone_by_owner
    clones = get_clone_by_owner(user_id)
    if not clones:
        await bot_api.send_message(chat_id,
            "🤖 *Your Bots*\n\nYou have no active bots.\n\nUse /clone to create one!")
        return
    msg = "🤖 *Your Active Bots*\n\n"
    buttons = []
    for c in clones:
        uptime = int((datetime.utcnow() - c["started_at"]).total_seconds())
        msg += f"• @{c['username']} — {format_uptime(uptime)}\n"
        buttons.append([{"text": f"🛑 Stop @{c['username']}", "callback_data": f"stop_{c['token'][:10]}"}])
    await bot_api.send_message(chat_id, msg, buttons)

async def do_broadcast(bot_api, text, owner_id):
    all_targets = list(set(await db.get_all_chat_ids() + await db.get_all_user_ids()))
    sent = failed = 0
    for tid in all_targets:
        try:
            await bot_api.send_message(tid, text)
            sent += 1
        except Exception:
            failed += 1
    await bot_api.send_message(owner_id,
        f"📣 *Broadcast Done*\n\n✅ Sent: {sent}\n❌ Failed: {failed}\n📊 Total: {len(all_targets)}")


async def on_update(data, bot_api, reactions, restricted_chats, bot_username,
                    random_level, owner_id_str, main_bot_username, is_clone_bot,
                    broadcast_state, log_group_id):

    owner_id = int(owner_id_str) if owner_id_str else None
    content  = data.get("message") or data.get("channel_post")

    if content:
        chat_id    = content["chat"]["id"]
        message_id = content["message_id"]
        text       = content.get("text", "")
        chat_type  = content["chat"]["type"]
        is_message = "message" in data
        from_      = content.get("from", {})
        user_id    = from_.get("id", 0)
        user_name  = from_.get("first_name", "") if chat_type == "private" else content["chat"].get("title", "")

        await db.register_chat(chat_id, chat_type, content["chat"].get("title", ""))

        # ── Owner broadcast capture ───────────────────────────────────────────
        if (is_message and owner_id and chat_id == owner_id
                and broadcast_state.get("waiting") and not text.startswith("/")):
            broadcast_state["waiting"] = False
            await do_broadcast(bot_api, text, owner_id)
            return

        # ── Token capture ─────────────────────────────────────────────────────
        if (is_message and chat_type == "private" and user_id in _clone_pending
                and _clone_pending[user_id] == "awaiting_token" and not text.startswith("/")):
            await handle_token_input(chat_id, user_id, from_, text.strip(),
                bot_api, bot_username, reactions, random_level,
                main_bot_username, log_group_id, owner_id_str)
            return

        # ── /start ────────────────────────────────────────────────────────────
        if is_message and (text == "/start" or text == f"/start@{bot_username}" or text == "/start clone"):
            await db.get_user(user_id)
            date, time_str = format_datetime()
            dc_id = get_dc_id(user_id)
            uname = f"@{from_.get('username')}" if from_.get("username") else "ɴᴏɴᴇ"
            await log_to_group(bot_api, log_group_id,
                f"👁️‍🗨️ 𝘜𝘚𝘌𝘙 𝘋𝘌𝘛𝘈𝘐𝘓𝘚\n\n"
                f"○ 𝘐𝘋 : `{user_id}`\n○ 𝘋𝘊 : DC{dc_id}\n"
                f"○ 𝘍𝘪𝘳𝘴𝘵 𝘕𝘢𝘮𝘦 : {from_.get('first_name', '')}\n"
                f"○ 𝘜𝘴𝘦𝘳𝘕𝘢𝘮𝘦 : {uname}\n"
                f"• Date : {date}\n• Time : {time_str}\n\n𝘉𝘺 = @{bot_username}")

            if text == "/start clone":
                await handle_clone_command(chat_id, user_id, bot_api, bot_username,
                    reactions, random_level, main_bot_username, log_group_id)
                return

            await bot_api.send_message(
                chat_id,
                START_MESSAGE.format(name=user_name),
                [
                    [{"text": "➕ Add to Channel ➕", "url": f"https://t.me/{bot_username}?startchannel=botstart"},
                     {"text": "➕ Add to Group ➕",   "url": f"https://t.me/{bot_username}?startgroup=botstart"}],
                    [{"text": "📢 Updates Channel", "url": "https://t.me/RoyalityBots"}],
                    [{"text": "💝 Support Us - Donate 🤝", "url": f"https://t.me/{bot_username}?start=donate"}],
                    [{"text": "🤖 Clone This Bot", "callback_data": "clone_bot"},
                     {"text": "🔗 Refer & Earn",   "callback_data": "refer_earn"}],
                ],
            )

        # ── /start ref_<id> ───────────────────────────────────────────────────
        elif is_message and text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1])
                await db.process_referral(user_id, referrer_id)
            except Exception:
                pass
            await db.get_user(user_id)
            await bot_api.send_message(
                chat_id, START_MESSAGE.format(name=user_name),
                [[{"text": "➕ Add to Channel ➕", "url": f"https://t.me/{bot_username}?startchannel=botstart"},
                  {"text": "➕ Add to Group ➕",   "url": f"https://t.me/{bot_username}?startgroup=botstart"}],
                 [{"text": "📢 Updates Channel", "url": "https://t.me/RoyalityBots"}],
                 [{"text": "💝 Support Us - Donate 🤝", "url": f"https://t.me/{bot_username}?start=donate"}],
                 [{"text": "🤖 Clone This Bot", "callback_data": "clone_bot"},
                  {"text": "🔗 Refer & Earn",   "callback_data": "refer_earn"}]],
            )

        elif is_message and (text == "/start donate" or text in ("/donate", f"/donate@{bot_username}")):
            await handle_donate(chat_id, bot_api)

        elif is_message and text in ("/reactions", f"/reactions@{bot_username}"):
            await bot_api.send_message(chat_id, "✅ Enabled Reactions :\n\n" + ", ".join(reactions))

        elif is_message and text in ("/refer", f"/refer@{bot_username}"):
            await send_refer_info(chat_id, user_id, bot_api, bot_username)

        elif is_message and text in ("/clone", f"/clone@{bot_username}"):
            await handle_clone_command(chat_id, user_id, bot_api, bot_username,
                reactions, random_level, main_bot_username, log_group_id)

        elif is_message and text in ("/mybots", f"/mybots@{bot_username}"):
            await handle_mybots(chat_id, user_id, bot_api)

        elif is_message and text == "/cancel":
            if user_id in _clone_pending:
                _clone_pending.pop(user_id, None)
                await bot_api.send_message(chat_id, "❌ Clone cancelled.")
            elif broadcast_state.get("waiting"):
                broadcast_state["waiting"] = False
                await bot_api.send_message(chat_id, "❌ Broadcast cancelled.")

        elif is_message and text.lower() in ("/statusbot", f"/statusbot@{bot_username}"):
            if owner_id and chat_id == owner_id:
                from clone_manager import get_active_clones
                stats  = await db.get_bot_stats()
                uptime = format_uptime(time.time() - _BOT_START_TIME)
                await bot_api.send_message(chat_id,
                    "📊 *Bot Status*\n\n"
                    f"🤖 Total Bots Cloned : `{stats['total_clones']}`\n"
                    f"🟢 Currently Running : `{len(get_active_clones())}`\n"
                    f"👥 Total Users        : `{stats['total_users']}`\n"
                    f"📅 Monthly Users      : `{stats['monthly_users']}`\n"
                    f"📆 Yearly Users       : `{stats['yearly_users']}`\n"
                    f"💬 Total Traffic      : `{stats['total_traffic']}`\n"
                    f"⏱️ Uptime             : `{uptime}`")
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        elif is_message and text.lower() in ("/statusserver", f"/statusserver@{bot_username}"):
            if owner_id and chat_id == owner_id:
                s = get_server_stats()
                await bot_api.send_message(chat_id,
                    "╔════❰ sᴇʀᴠᴇʀ sᴛᴀᴛs  ❱═❍⊱❁۪۪\n"
                    "║╭━━━━━━━━━━━━━━━➣\n"
                    f"║┣⪼ ᴛᴏᴛᴀʟ ᴅɪsᴋ: `{s['disk_total']} GB`\n"
                    f"║┣⪼ ᴜsᴇᴅ: `{s['disk_used']} GB`\n"
                    f"║┣⪼ ꜰʀᴇᴇ: `{s['disk_free']} GB`\n"
                    f"║┣⪼ ᴄᴘᴜ: `{s['cpu_pct']}%`\n"
                    f"║┣⪼ ʀᴀᴍ: `{s['ram_pct']}%`\n"
                    f"║┣⪼ ᴛᴏᴛᴀʟ ʀᴀᴍ: `{s['ram_total']} GB`\n"
                    f"║┣⪼ ᴜsᴇᴅ ʀᴀᴍ: `{s['ram_used']} GB`\n"
                    f"║┣⪼ ꜰʀᴇᴇ ʀᴀᴍ: `{s['ram_free']} GB`\n"
                    "║╰━━━━━━━━━━━━━━━➣\n"
                    "╚══════════════════❍⊱❁۪۪")
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        elif is_message and text.lower().startswith("/adddonor"):
            if owner_id and chat_id == owner_id:
                parts = text.strip().split()
                if len(parts) < 2:
                    await bot_api.send_message(chat_id, "⚠️ Usage: `/adddonor <user_id>`")
                else:
                    try:
                        tid   = int(parts[1])
                        user  = await db.add_donor(tid)
                        limit = await db.get_user_limit(tid)
                        await bot_api.send_message(chat_id,
                            f"✅ *Donor Added*\n\n🆔 ID: `{tid}`\n🤖 Limit: *{limit} bots*")
                        try:
                            await bot_api.send_message(tid,
                                f"🎉 *Congratulations!*\n\n"
                                f"You've been added to the donor list!\n"
                                f"You can now create up to *{limit} bots*! 💝")
                        except Exception:
                            pass
                    except ValueError:
                        await bot_api.send_message(chat_id, "❌ Invalid user ID.")
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        elif is_message and text in ("/broadcast", f"/broadcast@{bot_username}"):
            if owner_id and chat_id == owner_id:
                broadcast_state["waiting"] = True
                await bot_api.send_message(chat_id,
                    "📣 *Broadcast Mode*\n\nSend your message now.\n\n_/cancel to abort._")
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        else:
            threshold = 1 - (random_level / 10)
            if chat_id not in restricted_chats:
                await db.record_traffic(chat_id)
                if chat_type in ("group", "supergroup"):
                    if random.random() <= threshold:
                        await bot_api.set_message_reaction(chat_id, message_id, get_random_positive_reaction(reactions))
                else:
                    await bot_api.set_message_reaction(chat_id, message_id, get_random_positive_reaction(reactions))

    elif "my_chat_member" in data:
        update  = data["my_chat_member"]
        chat_id = update["chat"]["id"]
        status  = update["new_chat_member"]["status"]
        if status in ("member", "administrator"):
            await db.register_chat(chat_id, update["chat"]["type"], update["chat"].get("title", ""))
        elif status in ("kicked", "left"):
            await db.deregister_chat(chat_id)

    elif "pre_checkout_query" in data:
        query = data["pre_checkout_query"]
        await bot_api.answer_pre_checkout_query(query["id"], True)
        await bot_api.send_message(query["from"]["id"],
            "⏳ *Processing your donation...*\n\nThank you! 💝")

    elif data.get("message", {}).get("successful_payment"):
        message  = data["message"]
        payment  = message["successful_payment"]
        from_    = message["from"]
        user_id  = from_["id"]
        amount   = payment["total_amount"]
        currency = payment["currency"]
        date, time_str = format_datetime()

        await db.mark_donor(user_id)
        limit = await db.get_user_limit(user_id)

        await bot_api.send_message(user_id,
            f"✅ *Donation Confirmed!* 💝\n\n"
            f"Thank you {from_['first_name']}! *{amount} {currency}* received.\n\n"
            f"🎁 Your limit is now *{limit} bots*! 🌟")

        if owner_id:
            uname = f"@{from_.get('username')}" if from_.get("username") else "N/A"
            fname = f"{from_['first_name']} {from_.get('last_name', '')}".strip()
            await bot_api.send_message(owner_id,
                "📣 *Donation Initiative*\n\n"
                f"👤 Name     : {fname}\n🆔 ID       : `{from_['id']}`\n"
                f"👤 Username : {uname}\n📅 Date     : {date}\n🕐 Time     : {time_str}\n"
                f"💰 Amount   : {amount} {currency}\n✅ Status   : Payment Successful\n"
                f"🤖 Bot Name : Auto Reaction Clone")


async def on_callback_query(data, bot_api, bot_username, owner_id_str):
    query   = data["callback_query"]
    chat_id = query["from"]["id"]
    user_id = query["from"]["id"]
    cb_data = query.get("data", "")

    await bot_api.answer_callback_query(query["id"])

    amount_map = {"donate_5": 5, "donate_10": 10, "donate_20": 20, "donate_30": 30, "donate_50": 50}

    if cb_data == "clone_bot":
        await handle_clone_command(chat_id, user_id, bot_api, bot_username,
            [], 0, "", "")

    elif cb_data == "refer_earn":
        await send_refer_info(chat_id, user_id, bot_api, bot_username)

    elif cb_data == "donate_back":
        await bot_api.send_message(chat_id, "↩️ Use /start to go back.")

    elif cb_data == "donate_custom":
        await bot_api.send_message(chat_id,
            "💳 *Custom Donation*\n\nType the amount of ⭐ Stars (e.g. `15`).")

    elif cb_data in amount_map:
        stars = amount_map[cb_data]
        await bot_api.send_invoice(chat_id,
            "Donate and make a difference.",
            f"Contribute {stars} Stars ❤️\n\n{DONATE_MESSAGE}",
            "{}", "", "donate", "XTR",
            [{"label": f"Pay ⭐{stars}", "amount": stars}])

    elif cb_data.startswith("stop_"):
        from clone_manager import _active_clones, stop_clone
        prefix = cb_data.replace("stop_", "")
        token  = next((t for t in _active_clones if t.startswith(prefix)), None)
        if token:
            info = _active_clones.get(token, {})
            await stop_clone(token)
            await db.remove_clone_token(token)
            await bot_api.send_message(chat_id,
                f"🛑 @{info.get('username', 'bot')} has been stopped.")
        else:
            await bot_api.send_message(chat_id, "⚠️ Bot not found or already stopped.")
