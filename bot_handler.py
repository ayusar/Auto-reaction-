# © [2026] Malith-Rukshan. All rights reserved.
# Repository: https://github.com/Malith-Rukshan/Auto-Reaction-Bot

import os
import time
import random
from datetime import datetime

import psutil

from constants import (
    START_MESSAGE,
    DONATE_MESSAGE,
    CLONE_MESSAGE,
)
from helper import get_random_positive_reaction
import database as db

# ── Bot start time ────────────────────────────────────────────────────────────
_BOT_START_TIME = time.time()

# ── Clone waiting state ───────────────────────────────────────────────────────
# Tracks users who are in the middle of the clone flow
# { user_id: "awaiting_token" }
_clone_pending: dict = {}

# ── DC ID MAP ─────────────────────────────────────────────────────────────────
_DC_RANGES = [
    (1,          999999999,   1),
    (1000000000, 1999999999,  2),
    (2000000000, 2999999999,  3),
    (3000000000, 3999999999,  4),
    (4000000000, 9999999999,  5),
]

def get_dc_id(user_id: int) -> int:
    for low, high, dc in _DC_RANGES:
        if low <= user_id <= high:
            return dc
    return 1


def format_datetime() -> tuple:
    now = datetime.now()
    return now.strftime("%d %b %Y"), now.strftime("%I:%M:%S %p")


def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days,    seconds = divmod(seconds, 86400)
    hours,   seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


async def log_to_group(bot_api, log_group_id, text: str):
    if not log_group_id:
        return
    try:
        await bot_api.send_message(int(log_group_id), text)
    except Exception as e:
        print(f"[LOG] Failed: {e}")


def get_server_stats() -> dict:
    disk = psutil.disk_usage("/")
    ram  = psutil.virtual_memory()
    cpu  = psutil.cpu_percent(interval=0.5)
    return {
        "disk_total": round(disk.total   / (1024**3), 2),
        "disk_used":  round(disk.used    / (1024**3), 2),
        "disk_free":  round(disk.free    / (1024**3), 2),
        "cpu_pct":    cpu,
        "ram_pct":    ram.percent,
        "ram_total":  round(ram.total    / (1024**3), 2),
        "ram_used":   round(ram.used     / (1024**3), 2),
        "ram_free":   round(ram.available / (1024**3), 2),
    }


# ── DONATE HANDLER ────────────────────────────────────────────────────────────

async def handle_donate(chat_id, bot_api, is_clone_bot, main_bot_username, bot_username):
    # On clone bot — only redirect if main_bot_username is actually set and different
    if is_clone_bot and main_bot_username and main_bot_username != bot_username:
        await bot_api.send_message(
            chat_id,
            f"💝 *Support Us!*\n\n"
            f"Donations are handled by the main bot.\n"
            f"Tap the button below to donate and unlock more clone slots!",
            [[{"text": "💝 Donate on Main Bot", "url": f"https://t.me/{main_bot_username}?start=donate"}]],
        )
        return

    await bot_api.send_message(
        chat_id,
        "💝 *Why Donate to RoyalityBots?*\n\n"
        "• It helps to cover the cost of the servers.\n"
        "• It motivates us to make an update or create a new bot.\n"
        "• Help me to buy a cup of tea from starbucks (does starbucks provides tea ?)\n\n"
        "-\n\n"
        "👇 *Choose an amount to donate:*",
        [
            [
                {"text": "⭐ 5",  "callback_data": "donate_5"},
                {"text": "⭐ 10", "callback_data": "donate_10"},
                {"text": "⭐ 20", "callback_data": "donate_20"},
            ],
            [
                {"text": "⭐ 30", "callback_data": "donate_30"},
                {"text": "⭐ 50", "callback_data": "donate_50"},
            ],
            [{"text": "💳 Generate Bill", "callback_data": "donate_custom"}],
            [{"text": "↩️ Back",          "callback_data": "donate_back"}],
        ],
    )


# ── BROADCAST ─────────────────────────────────────────────────────────────────

async def do_broadcast(bot_api, text: str, owner_id: int):
    chat_ids    = await db.get_all_chat_ids()
    user_ids    = await db.get_all_user_ids()
    all_targets = list(set(chat_ids + user_ids))
    sent = failed = 0
    for target_id in all_targets:
        try:
            await bot_api.send_message(target_id, text)
            sent += 1
        except Exception:
            failed += 1
    await bot_api.send_message(
        owner_id,
        f"📣 *Broadcast Complete*\n\n"
        f"✅ Sent    : {sent}\n"
        f"❌ Failed  : {failed}\n"
        f"📊 Total   : {len(all_targets)}",
    )


# ── REFER INFO ────────────────────────────────────────────────────────────────

async def send_refer_info(chat_id, user_id, bot_api, bot_username):
    stats    = await db.get_refer_stats(user_id)
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share    = f"https://t.me/share/url?url={ref_link}&text=Join%20Auto%20Reaction%20Bot!"
    await bot_api.send_message(
        chat_id,
        f"🔗 *Refer & Earn*\n\n"
        f"Share your link and earn *+1 bot slot* for every *{db.REFERS_NEEDED} successful referrals*!\n"
        f"Maximum bonus: *{db.REFER_MAX_BONUS} extra slots*\n\n"
        f"👥 Total Referrals    : *{stats['refer_count']}*\n"
        f"🎁 Bonus Slots Earned : *{stats['bonus_bots']}*\n"
        f"⏳ Next Bonus In      : *{stats['next_bonus_in']} more referral(s)*\n\n"
        f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
        "_When a friend starts the bot using your link, it counts as a referral!_",
        [[{"text": "📤 Share Referral Link", "url": share}]],
    )


# ── CLONE FLOW ────────────────────────────────────────────────────────────────

async def handle_clone_command(chat_id, user_id, from_, bot_api, bot_username, reactions, random_level, main_bot_username, log_group_id):
    """Start the clone flow — ask user for their bot token."""
    from clone_manager import get_clone_by_owner

    user  = await db.get_user(user_id)
    limit = await db.get_user_limit(user_id)
    count = user["clone_count"]

    if count >= limit:
        msg = (
            f"⚠️ You have reached your clone limit of *{limit} bots*.\n\n"
            + ("Please contact the owner for assistance." if user["is_donor"] else
               f"💝 Donate to unlock up to *{db.DONOR_CLONE_LIMIT} clones*!\n\n"
               "🔗 Or refer friends to earn more — use /refer\n\n"
               "Use /donate to support us.")
        )
        await bot_api.send_message(chat_id, msg)
        return

    # Set user as pending token input
    _clone_pending[user_id] = "awaiting_token"

    await bot_api.send_message(
        chat_id,
        "🤖 *Clone Bot — Step 1 of 2*\n\n"
        "To create your own clone bot:\n\n"
        "1️⃣ Open [@BotFather](https://t.me/BotFather) on Telegram\n"
        "2️⃣ Send `/newbot`\n"
        "3️⃣ Follow the steps and get your *Bot Token*\n\n"
        "Then *paste your Bot Token here* 👇\n\n"
        "_Example: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`_\n\n"
        "Send /cancel to abort.",
        [[{"text": "👉 Open BotFather", "url": "https://t.me/BotFather"}]],
    )


async def handle_token_input(chat_id, user_id, from_, token: str, bot_api, bot_username, reactions, random_level, main_bot_username, log_group_id, owner_id):
    """User sent a token — validate and start the clone."""
    from clone_manager import start_clone, get_clone_by_owner

    # Clear pending state
    _clone_pending.pop(user_id, None)

    await bot_api.send_message(chat_id, "⏳ *Validating your token and starting your bot...*")

    result = await start_clone(
        token=token,
        owner_id=user_id,
        reactions=reactions,
        random_level=random_level,
        main_bot_username=bot_username,   # cloned bots redirect donate to main bot
        log_group_id=log_group_id,
    )

    if not result["ok"]:
        await bot_api.send_message(
            chat_id,
            f"❌ *Failed to start your bot*\n\n{result['error']}\n\nPlease check your token and try again.",
        )
        return

    # Save token to DB
    await db.save_clone_token(user_id, token, result["username"])
    await db.increment_clone(user_id)

    user  = await db.get_user(user_id)
    limit = await db.get_user_limit(user_id)

    await bot_api.send_message(
        chat_id,
        f"✅ *Your bot is now live!*\n\n"
        f"🤖 Bot : @{result['username']}\n"
        f"📊 Your clones : {user['clone_count']}/{limit}\n\n"
        f"Your bot is running with all the same features:\n"
        f"• Auto emoji reactions ✅\n"
        f"• Works in groups & channels ✅\n"
        f"• All commands active ✅\n\n"
        f"Just add @{result['username']} to your groups or channels!\n\n"
        f"_To stop your bot use /mybots_",
        [[{"text": f"👉 Open @{result['username']}", "url": f"https://t.me/{result['username']}"}]],
    )

    # Log to group
    date, time_str = format_datetime()
    dc_id        = get_dc_id(user_id)
    username_str = f"@{from_.get('username')}" if from_.get("username") else "ɴᴏɴᴇ"
    await log_to_group(
        bot_api, log_group_id,
        f"👁️‍🗨️ 𝘜𝘚𝘌𝘙 𝘋𝘌𝘛𝘈𝘐𝘓𝘚\n\n"
        f"○ 𝘐𝘋 : `{user_id}`\n"
        f"○ 𝘋𝘊 : DC{dc_id}\n"
        f"○ 𝘍𝘪𝘳𝘴𝘵 𝘕𝘢𝘮𝘦 : {from_.get('first_name', '')}\n"
        f"○ 𝘜𝘴𝘦𝘳𝘕𝘢𝘮𝘦 : {username_str}\n"
        f"• Cloned Bot : @{result['username']}\n"
        f"• Donation User : {'✅ Yes' if user['is_donor'] else '❌ No'}\n\n"
        f"𝘉𝘺 = @{bot_username}",
    )

    # Notify owner
    if owner_id:
        await bot_api.send_message(
            int(owner_id),
            f"🤖 *New Clone Created*\n\n"
            f"👤 User : {from_.get('first_name')} (`{user_id}`)\n"
            f"🤖 Bot  : @{result['username']}\n"
            f"📅 Date : {date} {time_str}",
        )


# ── MY BOTS ───────────────────────────────────────────────────────────────────

async def handle_mybots(chat_id, user_id, bot_api):
    """Show user their running clone bots."""
    from clone_manager import get_clone_by_owner
    clones = get_clone_by_owner(user_id)

    if not clones:
        await bot_api.send_message(
            chat_id,
            "🤖 *Your Bots*\n\nYou have no active clone bots.\n\nUse /clone to create one!",
        )
        return

    msg = "🤖 *Your Active Bots*\n\n"
    buttons = []
    for c in clones:
        uptime = int((datetime.utcnow() - c["started_at"]).total_seconds())
        msg += f"• @{c['username']} — uptime {format_uptime(uptime)}\n"
        buttons.append([{"text": f"🛑 Stop @{c['username']}", "callback_data": f"stop_clone_{c['token'][:10]}"}])

    await bot_api.send_message(chat_id, msg, buttons)


# ── MAIN UPDATE HANDLER ───────────────────────────────────────────────────────

async def on_update(
    data: dict,
    bot_api,
    reactions: list,
    restricted_chats: list,
    bot_username: str,
    random_level: int,
    owner_id_str: str,
    main_bot_username: str,
    is_clone_bot: bool,
    broadcast_state: dict,
    log_group_id: str,
):
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

        await db.register_chat(chat_id, chat_type, content["chat"].get("title", ""))

        user_name = (
            from_.get("first_name", "")
            if chat_type == "private"
            else content["chat"].get("title", "")
        )

        # ── Owner broadcast capture ───────────────────────────────────────────
        if (
            is_message
            and owner_id
            and chat_id == owner_id
            and broadcast_state.get("waiting")
            and not text.startswith("/")
        ):
            broadcast_state["waiting"] = False
            await do_broadcast(bot_api, text, owner_id)
            return

        # ── Clone token capture — user is in clone flow ───────────────────────
        if (
            is_message
            and chat_type == "private"
            and user_id in _clone_pending
            and _clone_pending[user_id] == "awaiting_token"
            and not text.startswith("/")
        ):
            await handle_token_input(
                chat_id, user_id, from_, text.strip(),
                bot_api, bot_username, reactions, random_level,
                main_bot_username, log_group_id, owner_id_str,
            )
            return

        # ── /start ────────────────────────────────────────────────────────────
        if is_message and text in ("/start", f"/start@{bot_username}"):
            await db.get_user(user_id)
            date, time_str = format_datetime()
            dc_id        = get_dc_id(user_id)
            username_str = f"@{from_.get('username')}" if from_.get("username") else "ɴᴏɴᴇ"

            await log_to_group(
                bot_api, log_group_id,
                f"👁️‍🗨️ 𝘜𝘚𝘌𝘙 𝘋𝘌𝘛𝘈𝘐𝘓𝘚\n\n"
                f"○ 𝘐𝘋 : `{user_id}`\n"
                f"○ 𝘋𝘊 : DC{dc_id}\n"
                f"○ 𝘍𝘪𝘳𝘴𝘵 𝘕𝘢𝘮𝘦 : {from_.get('first_name', '')}\n"
                f"○ 𝘜𝘴𝘦𝘳𝘕𝘢𝘮𝘦 : {username_str}\n"
                f"• Date : {date}\n"
                f"• Time : {time_str}\n\n"
                f"𝘉𝘺 = @{bot_username}",
            )

            if is_clone_bot:
                # Clone bot start — "Clone This Bot" sends user to MAIN bot
                main_or_self = main_bot_username if (main_bot_username and main_bot_username != bot_username) else bot_username
                await bot_api.send_message(
                    chat_id,
                    CLONE_MESSAGE.format(name=user_name),
                    [
                        [
                            {"text": "➕ Add to Channel ➕", "url": f"https://t.me/{bot_username}?startchannel=botstart"},
                            {"text": "➕ Add to Group ➕",   "url": f"https://t.me/{bot_username}?startgroup=botstart"},
                        ],
                        [{"text": "📢 Updates Channel", "url": "https://t.me/RoyalityBots"}],
                        [
                            {"text": "💝 Donate",       "url": f"https://t.me/{main_or_self}?start=donate"},
                            {"text": "🤖 RoyalityBots", "url": "https://t.me/RoyalityBots"},
                        ],
                        # Redirect to main bot to clone — clone bots don't host cloning
                        [{"text": "🤖 Clone This Bot", "url": f"https://t.me/{main_or_self}?start=clone"}],
                    ],
                )
            else:
                await bot_api.send_message(
                    chat_id,
                    START_MESSAGE.format(name=user_name),
                    [
                        [
                            {"text": "➕ Add to Channel ➕", "url": f"https://t.me/{bot_username}?startchannel=botstart"},
                            {"text": "➕ Add to Group ➕",   "url": f"https://t.me/{bot_username}?startgroup=botstart"},
                        ],
                        [{"text": "📢 Updates Channel", "url": "https://t.me/RoyalityBots"}],
                        [{"text": "💝 Support Us - Donate 🤝", "url": f"https://t.me/{bot_username}?start=donate"}],
                        [
                            {"text": "🤖 Clone This Bot", "callback_data": "clone_bot"},
                            {"text": "🔗 Refer & Earn",   "callback_data": "refer_earn"},
                        ],
                    ],
                )

        # ── /start clone — deep link from clone bot button ──────────────────
        elif is_message and text == "/start clone":
            if not is_clone_bot:
                await handle_clone_command(
                    chat_id, user_id, from_, bot_api, bot_username,
                    reactions, random_level, main_bot_username, log_group_id,
                )
            else:
                await bot_api.send_message(chat_id, "Please use the main bot to clone.")

        # ── /start ref_<id> ───────────────────────────────────────────────────
        elif is_message and text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1])
                await db.process_referral(user_id, referrer_id)
            except (ValueError, IndexError):
                pass
            await db.get_user(user_id)
            await bot_api.send_message(
                chat_id,
                START_MESSAGE.format(name=user_name),
                [
                    [
                        {"text": "➕ Add to Channel ➕", "url": f"https://t.me/{bot_username}?startchannel=botstart"},
                        {"text": "➕ Add to Group ➕",   "url": f"https://t.me/{bot_username}?startgroup=botstart"},
                    ],
                    [{"text": "📢 Updates Channel", "url": "https://t.me/RoyalityBots"}],
                    [{"text": "💝 Support Us - Donate 🤝", "url": f"https://t.me/{bot_username}?start=donate"}],
                    [
                        {"text": "🤖 Clone This Bot", "callback_data": "clone_bot"},
                        {"text": "🔗 Refer & Earn",   "callback_data": "refer_earn"},
                    ],
                ],
            )

        # ── /start donate ─────────────────────────────────────────────────────
        elif is_message and text == "/start donate":
            await handle_donate(chat_id, bot_api, is_clone_bot, main_bot_username, bot_username)

        # ── /donate ───────────────────────────────────────────────────────────
        elif is_message and text in ("/donate", f"/donate@{bot_username}"):
            await handle_donate(chat_id, bot_api, is_clone_bot, main_bot_username, bot_username)

        # ── /reactions ────────────────────────────────────────────────────────
        elif is_message and text in ("/reactions", f"/reactions@{bot_username}"):
            await bot_api.send_message(chat_id, "✅ Enabled Reactions :\n\n" + ", ".join(reactions))

        # ── /refer ────────────────────────────────────────────────────────────
        elif is_message and text in ("/refer", f"/refer@{bot_username}"):
            await send_refer_info(chat_id, user_id, bot_api, bot_username)

        # ── /clone ────────────────────────────────────────────────────────────
        elif is_message and text in ("/clone", f"/clone@{bot_username}"):
            await handle_clone_command(
                chat_id, user_id, from_, bot_api, bot_username,
                reactions, random_level, main_bot_username, log_group_id,
            )

        # ── /mybots ───────────────────────────────────────────────────────────
        elif is_message and text in ("/mybots", f"/mybots@{bot_username}"):
            await handle_mybots(chat_id, user_id, bot_api)

        # ── /cancel ───────────────────────────────────────────────────────────
        elif is_message and text == "/cancel":
            if user_id in _clone_pending:
                _clone_pending.pop(user_id, None)
                await bot_api.send_message(chat_id, "❌ Clone cancelled.")
            elif broadcast_state.get("waiting"):
                broadcast_state["waiting"] = False
                await bot_api.send_message(chat_id, "❌ Broadcast cancelled.")

        # ── /statusbot (owner only) ───────────────────────────────────────────
        elif is_message and text.lower() in ("/statusbot", f"/statusbot@{bot_username}"):
            if owner_id and chat_id == owner_id:
                from clone_manager import get_active_clones
                stats  = await db.get_bot_stats()
                uptime = format_uptime(time.time() - _BOT_START_TIME)
                active = get_active_clones()
                await bot_api.send_message(
                    chat_id,
                    "📊 *Bot Status*\n\n"
                    f"🤖 Total Bots Cloned  : `{stats['total_clones']}`\n"
                    f"🟢 Currently Running  : `{len(active)}`\n"
                    f"👥 Total Users         : `{stats['total_users']}`\n"
                    f"📅 Monthly Users       : `{stats['monthly_users']}`\n"
                    f"📆 Yearly Users        : `{stats['yearly_users']}`\n"
                    f"💬 Total Traffic       : `{stats['total_traffic']}` messages\n"
                    f"⏱️ Bot Uptime          : `{uptime}`",
                )
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        # ── /statusserver (owner only) ────────────────────────────────────────
        elif is_message and text.lower() in ("/statusserver", f"/statusserver@{bot_username}"):
            if owner_id and chat_id == owner_id:
                s = get_server_stats()
                await bot_api.send_message(
                    chat_id,
                    "╔════❰ sᴇʀᴠᴇʀ sᴛᴀᴛs  ❱═❍⊱❁۪۪\n"
                    "║╭━━━━━━━━━━━━━━━➣\n"
                    f"║┣⪼ ᴛᴏᴛᴀʟ ᴅɪsᴋ sᴘᴀᴄᴇ: `{s['disk_total']} GB`\n"
                    f"║┣⪼ ᴜsᴇᴅ: `{s['disk_used']} GB`\n"
                    f"║┣⪼ ꜰʀᴇᴇ: `{s['disk_free']} GB`\n"
                    f"║┣⪼ ᴄᴘᴜ: `{s['cpu_pct']}%`\n"
                    f"║┣⪼ ʀᴀᴍ: `{s['ram_pct']}%`\n"
                    f"║┣⪼ ᴛᴏᴛᴀʟ ʀᴀᴍ: `{s['ram_total']} GB`\n"
                    f"║┣⪼ ᴜsᴇᴅ ʀᴀᴍ: `{s['ram_used']} GB`\n"
                    f"║┣⪼ ꜰʀᴇᴇ ʀᴀᴍ: `{s['ram_free']} GB`\n"
                    "║╰━━━━━━━━━━━━━━━➣\n"
                    "╚══════════════════❍⊱❁۪۪",
                )
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        # ── /adddonor (owner only) ────────────────────────────────────────────
        elif is_message and text.lower().startswith("/adddonor"):
            if owner_id and chat_id == owner_id:
                parts = text.strip().split()
                if len(parts) < 2:
                    await bot_api.send_message(
                        chat_id,
                        "⚠️ Usage: `/adddonor <user_id>`\n\nExample: `/adddonor 123456789`",
                    )
                else:
                    try:
                        target_id = int(parts[1])
                        user      = await db.add_donor(target_id)
                        limit     = await db.get_user_limit(target_id)
                        # Notify the owner
                        await bot_api.send_message(
                            chat_id,
                            f"✅ *Donor Added*\n\n"
                            f"🆔 User ID : `{target_id}`\n"
                            f"🤖 New Limit : *{limit} bots*\n"
                            f"💝 Status : Donor ✅",
                        )
                        # Notify the user
                        try:
                            await bot_api.send_message(
                                target_id,
                                f"🎉 *Congratulations!*\n\n"
                                f"You have been added to the donor list by the owner!\n\n"
                                f"🤖 You can now create up to *{limit} bots*!\n\n"
                                f"Thank you for your support! 💝",
                            )
                        except Exception:
                            pass   # user may not have started bot yet
                    except ValueError:
                        await bot_api.send_message(
                            chat_id,
                            "❌ Invalid user ID. Please provide a valid numeric ID.\n\nExample: `/adddonor 123456789`",
                        )
            else:
                await bot_api.send_message(chat_id, "⛔ Owner only command.")

        # ── /broadcast (owner only) ───────────────────────────────────────────
        elif is_message and text in ("/broadcast", f"/broadcast@{bot_username}"):
            if owner_id and chat_id == owner_id and not is_clone_bot:
                broadcast_state["waiting"] = True
                await bot_api.send_message(
                    chat_id,
                    "📣 *Broadcast Mode*\n\nSend your message now.\n\n_Send /cancel to abort._",
                )
            else:
                await bot_api.send_message(chat_id, "⛔ Not authorized.")

        # ── Auto-react ────────────────────────────────────────────────────────
        else:
            threshold = 1 - (random_level / 10)
            if chat_id not in restricted_chats:
                await db.record_traffic(chat_id)
                if chat_type in ("group", "supergroup"):
                    if random.random() <= threshold:
                        await bot_api.set_message_reaction(
                            chat_id, message_id, get_random_positive_reaction(reactions)
                        )
                else:
                    await bot_api.set_message_reaction(
                        chat_id, message_id, get_random_positive_reaction(reactions)
                    )

    # ── Bot added / removed ───────────────────────────────────────────────────
    elif "my_chat_member" in data:
        update  = data["my_chat_member"]
        chat_id = update["chat"]["id"]
        status  = update["new_chat_member"]["status"]
        if status in ("member", "administrator"):
            await db.register_chat(chat_id, update["chat"]["type"], update["chat"].get("title", ""))
        elif status in ("kicked", "left"):
            await db.deregister_chat(chat_id)

    # ── Pre-Checkout Query ────────────────────────────────────────────────────
    elif "pre_checkout_query" in data:
        query       = data["pre_checkout_query"]
        pay_user_id = query["from"]["id"]
        await bot_api.answer_pre_checkout_query(query["id"], True)
        await bot_api.send_message(
            pay_user_id,
            "⏳ *Processing your donation...*\n\nYour payment is being confirmed. 💝",
        )

    # ── Successful Payment ────────────────────────────────────────────────────
    elif data.get("message", {}).get("successful_payment"):
        message  = data["message"]
        payment  = message["successful_payment"]
        from_    = message["from"]
        user_id  = from_["id"]
        amount   = payment["total_amount"]
        currency = payment["currency"]
        date, time_str = format_datetime()
        owner_id = int(owner_id_str) if owner_id_str else None

        await db.mark_donor(user_id)
        limit = await db.get_user_limit(user_id)

        await bot_api.send_message(
            user_id,
            f"✅ *Donation Confirmed!* 💝\n\n"
            f"Thank you {from_['first_name']}! "
            f"Your *{amount} {currency}* has been received.\n\n"
            f"🎁 Your clone limit is now *{limit} bots*!\n\n"
            "We truly appreciate your support. 🌟",
        )

        if owner_id:
            username  = f"@{from_['username']}" if from_.get("username") else "N/A"
            full_name = f"{from_['first_name']} {from_.get('last_name', '')}".strip()
            await bot_api.send_message(
                owner_id,
                "📣 *Donation Initiative*\n\n"
                f"👤 Name     : {full_name}\n"
                f"🆔 ID       : `{from_['id']}`\n"
                f"👤 Username : {username}\n"
                f"📅 Date     : {date}\n"
                f"🕐 Time     : {time_str}\n"
                f"💰 Amount   : {amount} {currency}\n"
                "✅ Status   : Payment Successful\n"
                "🤖 Bot Name : Auto Reaction Clone",
            )


# ── CALLBACK QUERY HANDLER ────────────────────────────────────────────────────

async def on_callback_query(data: dict, bot_api, bot_username: str, owner_id_str: str):
    query   = data["callback_query"]
    chat_id = query["from"]["id"]
    user_id = query["from"]["id"]
    cb_data = query.get("data", "")

    await bot_api.answer_callback_query(query["id"])

    amount_map = {
        "donate_5":  5,
        "donate_10": 10,
        "donate_20": 20,
        "donate_30": 30,
        "donate_50": 50,
    }

    if cb_data == "clone_bot":
        # Trigger clone flow from button
        _clone_pending[user_id] = "awaiting_token"
        await bot_api.send_message(
            chat_id,
            "🤖 *Clone Bot — Step 1 of 2*\n\n"
            "1️⃣ Open [@BotFather](https://t.me/BotFather)\n"
            "2️⃣ Send `/newbot` and follow steps\n"
            "3️⃣ Copy your *Bot Token*\n\n"
            "Then *paste your Bot Token here* 👇\n\n"
            "_Example: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`_\n\n"
            "Send /cancel to abort.",
            [[{"text": "👉 Open BotFather", "url": "https://t.me/BotFather"}]],
        )

    elif cb_data == "refer_earn":
        await send_refer_info(chat_id, user_id, bot_api, bot_username)

    elif cb_data.startswith("stop_clone_"):
        # Stop a clone bot
        from clone_manager import _active_clones, stop_clone
        token_prefix = cb_data.replace("stop_clone_", "")
        token_full   = next((t for t in _active_clones if t.startswith(token_prefix)), None)
        if token_full:
            info = _active_clones.get(token_full, {})
            await stop_clone(token_full)
            await db.remove_clone_token(token_full)
            await bot_api.send_message(
                chat_id,
                f"🛑 @{info.get('username', 'bot')} has been stopped.",
            )
        else:
            await bot_api.send_message(chat_id, "⚠️ Bot not found or already stopped.")

    elif cb_data == "donate_back":
        await bot_api.send_message(chat_id, "↩️ Use /start to go back to main menu.")

    elif cb_data == "donate_custom":
        await bot_api.send_message(
            chat_id,
            "💳 *Custom Donation*\n\nType the amount of ⭐ Stars (e.g. `15`).",
        )

    elif cb_data in amount_map:
        stars = amount_map[cb_data]
        await bot_api.send_invoice(
            chat_id,
            "Donate and made a difference.",
            f"Contribute {stars} Stars ❤️\n\n{DONATE_MESSAGE}",
            "{}",
            "",
            "donate",
            "XTR",
            [{"label": f"Pay ⭐{stars}", "amount": stars}],
        )
