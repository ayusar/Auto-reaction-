# © [2026] Malith-Rukshan. All rights reserved.
# Clone bot — auto reactions ONLY. No DB, no logs, no management.

import os
import random
from constants import CLONE_MESSAGE
from helper import get_random_positive_reaction


async def on_update(data, bot_api, reactions, restricted_chats, bot_username,
                    random_level, owner_id_str, main_bot_username, is_clone_bot,
                    broadcast_state, log_group_id):

    content = data.get("message") or data.get("channel_post")
    if not content:
        return

    chat_id    = content["chat"]["id"]
    message_id = content["message_id"]
    text       = content.get("text", "")
    chat_type  = content["chat"]["type"]
    is_message = "message" in data
    from_      = content.get("from", {})
    user_name  = from_.get("first_name", "") if chat_type == "private" else content["chat"].get("title", "")

    main = main_bot_username if (main_bot_username and main_bot_username != bot_username) else bot_username

    if is_message and text in ("/start", f"/start@{bot_username}"):
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
                    {"text": "💝 Donate",       "url": f"https://t.me/{main}?start=donate"},
                    {"text": "🤖 RoyalityBots", "url": "https://t.me/RoyalityBots"},
                ],
                [{"text": "🤖 Clone This Bot", "url": f"https://t.me/{main}?start=clone"}],
            ],
        )

    elif is_message and text in ("/reactions", f"/reactions@{bot_username}"):
        await bot_api.send_message(chat_id, "✅ Enabled Reactions :\n\n" + ", ".join(reactions))

    elif is_message and (text in ("/donate", f"/donate@{bot_username}") or text == "/start donate"):
        await bot_api.send_message(
            chat_id,
            "💝 *Support Us!*\n\nDonations are handled on the main bot.",
            [[{"text": "💝 Donate on Main Bot", "url": f"https://t.me/{main}?start=donate"}]],
        )

    elif is_message and text in ("/clone", f"/clone@{bot_username}"):
        await bot_api.send_message(
            chat_id,
            "🤖 *Clone This Bot*\n\nCloning is done on the main bot.",
            [[{"text": "🤖 Clone on Main Bot", "url": f"https://t.me/{main}?start=clone"}]],
        )

    elif is_message and text in ("/mybots", "/refer", "/broadcast", "/statusbot", "/statusserver") or \
         (is_message and text.startswith("/adddonor")):
        await bot_api.send_message(
            chat_id,
            "⛔ This command is only available on the main bot.",
            [[{"text": "🤖 Go to Main Bot", "url": f"https://t.me/{main}"}]],
        )

    else:
        threshold = 1 - (random_level / 10)
        if chat_id not in restricted_chats:
            if chat_type in ("group", "supergroup"):
                if random.random() <= threshold:
                    await bot_api.set_message_reaction(chat_id, message_id, get_random_positive_reaction(reactions))
            else:
                await bot_api.set_message_reaction(chat_id, message_id, get_random_positive_reaction(reactions))


async def on_callback_query(data, bot_api, bot_username, owner_id_str):
    query   = data["callback_query"]
    chat_id = query["from"]["id"]
    await bot_api.answer_callback_query(query["id"])
    main = os.getenv("MAIN_BOT_USERNAME", "") or bot_username
    await bot_api.send_message(
        chat_id,
        "👉 Please use the main bot for this action.",
        [[{"text": "🤖 Go to Main Bot", "url": f"https://t.me/{main}"}]],
    )
