# © [2026] Malith-Rukshan. All rights reserved.

import asyncio
import httpx
from datetime import datetime

_active_clones: dict = {}


async def validate_token(token: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = r.json()
            if data.get("ok"):
                return data["result"]
    except Exception:
        pass
    return None


async def delete_webhook_for_token(token: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook",
                              json={"drop_pending_updates": True})
    except Exception:
        pass


async def get_updates_for_token(token: str, offset=None) -> list:
    params = {"timeout": 30, "limit": 100}
    if offset:
        params["offset"] = offset
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params)
            data = r.json()
            if data.get("ok"):
                return data["result"]
    except Exception:
        pass
    return []


async def run_clone_polling(token, bot_username, owner_id, reactions, random_level, main_bot_username, log_group_id):
    from telegram_bot_api import TelegramBotAPI
    from bot_handler_clone import on_update, on_callback_query

    bot_api         = TelegramBotAPI(token)
    broadcast_state = {"waiting": False}
    offset          = None
    print(f"[CLONE] @{bot_username} polling started")

    while token in _active_clones:
        try:
            updates = await get_updates_for_token(token, offset)
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    if "callback_query" in update:
                        await on_callback_query(update, bot_api, bot_username, str(owner_id))
                    else:
                        await on_update(update, bot_api, reactions, [], bot_username,
                                        random_level, str(owner_id), main_bot_username,
                                        True, broadcast_state, "")
                except Exception as e:
                    print(f"[CLONE] @{bot_username} handler error: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[CLONE] @{bot_username} polling error: {e}")
            await asyncio.sleep(3)

    print(f"[CLONE] @{bot_username} stopped")


async def start_clone(token, owner_id, reactions, random_level, main_bot_username, log_group_id):
    if token in _active_clones:
        info = _active_clones[token]
        return {"ok": False, "error": f"@{info['username']} is already running!"}

    bot_info = await validate_token(token)
    if not bot_info:
        return {"ok": False, "error": "❌ Invalid token. Please check and try again."}

    bot_username = bot_info["username"]
    await delete_webhook_for_token(token)

    task = asyncio.create_task(
        run_clone_polling(token, bot_username, owner_id, reactions,
                          random_level, main_bot_username, log_group_id)
    )

    _active_clones[token] = {
        "task": task, "username": bot_username, "owner_id": owner_id,
        "started_at": datetime.utcnow(), "token": token,
    }

    return {"ok": True, "username": bot_username, "bot_info": bot_info}


async def stop_clone(token: str) -> bool:
    if token not in _active_clones:
        return False
    info = _active_clones.pop(token)
    info["task"].cancel()
    return True


def get_active_clones() -> list:
    return list(_active_clones.values())


def get_clone_by_owner(owner_id: int) -> list:
    return [v for v in _active_clones.values() if v["owner_id"] == owner_id]
