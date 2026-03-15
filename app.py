# © [2026] Malith-Rukshan. All rights reserved.

import os
import asyncio
import httpx

from dotenv import load_dotenv

# ── MUST load env first ───────────────────────────────────────────────────────
load_dotenv()

from telegram_bot_api import TelegramBotAPI
from helper import split_emojis, get_chat_ids

IS_CLONE_BOT = os.getenv("IS_CLONE_BOT", "false").lower() == "true"

if IS_CLONE_BOT:
    from bot_handler_clone import on_update, on_callback_query
else:
    from bot_handler_main import on_update, on_callback_query

BOT_TOKEN         = os.getenv("BOT_TOKEN", "")
BOT_USERNAME      = os.getenv("BOT_USERNAME", "")
EMOJI_LIST        = os.getenv("EMOJI_LIST", "👍❤🔥🥰👏😁🎉🤩🙏")
RESTRICTED_CHATS  = os.getenv("RESTRICTED_CHATS", "")
RANDOM_LEVEL      = int(os.getenv("RANDOM_LEVEL", "0"))
OWNER_ID          = os.getenv("OWNER_ID", "")
MAIN_BOT_USERNAME = os.getenv("MAIN_BOT_USERNAME", "")
MONGO_URI         = os.getenv("MONGO_URI", "")
LOG_GROUP_ID      = os.getenv("LOG_GROUP_ID", "")

reactions        = split_emojis(EMOJI_LIST)
restricted_chats = get_chat_ids(RESTRICTED_CHATS)
bot_api          = TelegramBotAPI(BOT_TOKEN)
broadcast_state  = {"waiting": False}


async def delete_webhook():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": True},
            )
        print("[INFO] Webhook deleted — polling mode active")
    except Exception as e:
        print(f"[WARN] Could not delete webhook: {e}")


async def get_updates(offset=None) -> list:
    params = {"timeout": 30, "limit": 100}
    if offset:
        params["offset"] = offset
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r    = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params=params)
            data = r.json()
            if data.get("ok"):
                return data["result"]
    except Exception as e:
        print(f"[ERROR] getUpdates failed: {e}")
    return []


async def process_update(update: dict):
    try:
        if "callback_query" in update:
            await on_callback_query(update, bot_api, BOT_USERNAME, OWNER_ID)
        else:
            await on_update(
                update, bot_api, reactions, restricted_chats,
                BOT_USERNAME, RANDOM_LEVEL, OWNER_ID,
                MAIN_BOT_USERNAME, IS_CLONE_BOT,
                broadcast_state, LOG_GROUP_ID,
            )
    except Exception as e:
        print(f"[ERROR] process_update: {e}")


async def restore_clones():
    if IS_CLONE_BOT:
        return
    import database as db
    from clone_manager import start_clone
    saved = await db.get_all_clone_tokens()
    if not saved:
        return
    print(f"[INFO] Restoring {len(saved)} clone bots...")
    for doc in saved:
        result = await start_clone(
            token=doc["token"], owner_id=doc["user_id"],
            reactions=reactions, random_level=RANDOM_LEVEL,
            main_bot_username=BOT_USERNAME, log_group_id=LOG_GROUP_ID,
        )
        status = f"✅ @{result['username']}" if result["ok"] else f"❌ {result['error']}"
        print(f"[INFO] Restore: {status}")


async def polling_loop():
    await delete_webhook()
    await restore_clones()
    offset = None
    print("[INFO] Bot is running in polling mode... Press CTRL+C to stop")
    while True:
        try:
            updates = await get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                await process_update(update)
        except Exception as e:
            print(f"[ERROR] Polling: {e}")
            await asyncio.sleep(3)


if __name__ == "__main__":
    print(
        f"[INFO] Starting | Mode: {'Clone Bot' if IS_CLONE_BOT else 'Main Bot'} | "
        f"Storage: {'MongoDB' if MONGO_URI else 'In-Memory'} | "
        f"Log Group: {'Yes' if LOG_GROUP_ID else 'No'}"
    )
    asyncio.run(polling_loop())
