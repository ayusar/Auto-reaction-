# © [2026] Malith-Rukshan. All rights reserved.

import os
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI", "")

# ── Limits ────────────────────────────────────────────────────────────────────
NORMAL_CLONE_LIMIT = 10
DONOR_CLONE_LIMIT  = 50
REFERS_NEEDED      = 2
REFER_BONUS        = 1
REFER_MAX_BONUS    = 20


def _calc_limit(user: dict) -> int:
    if user.get("is_donor"):
        return DONOR_CLONE_LIMIT
    refer_pts = user.get("refer_count", 0) // REFERS_NEEDED
    bonus = min(refer_pts * REFER_BONUS, REFER_MAX_BONUS)
    return NORMAL_CLONE_LIMIT + bonus


if MONGO_URI:
    print("[DB] Using MongoDB backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    _client = AsyncIOMotorClient(MONGO_URI)
    _db     = _client["auto_reaction_bot"]
    _users  = _db["users"]
    _chats  = _db["chats"]
    _traffic = _db["traffic"]
    _clones_col = _db["clone_tokens"]

    async def get_user(user_id: int) -> dict:
        doc = await _users.find_one({"_id": user_id})
        if not doc:
            doc = {"_id": user_id, "clone_count": 0, "is_donor": False,
                   "refer_count": 0, "referred_by": None, "joined_at": datetime.utcnow()}
            await _users.insert_one(doc)
        return doc

    async def save_user(user: dict):
        await _users.replace_one({"_id": user["_id"]}, user, upsert=True)

    async def get_user_limit(user_id: int) -> int:
        return _calc_limit(await get_user(user_id))

    async def increment_clone(user_id: int) -> dict:
        user = await get_user(user_id)
        user["clone_count"] += 1
        await save_user(user)
        return user

    async def mark_donor(user_id: int):
        user = await get_user(user_id)
        user["is_donor"] = True
        await save_user(user)

    async def add_donor(user_id: int) -> dict:
        user = await get_user(user_id)
        user["is_donor"] = True
        await save_user(user)
        return user

    async def process_referral(new_user_id: int, referrer_id: int):
        if new_user_id == referrer_id:
            return
        existing = await _users.find_one({"_id": new_user_id})
        if existing:
            return
        new_user = await get_user(new_user_id)
        if new_user.get("referred_by"):
            return
        new_user["referred_by"] = referrer_id
        await save_user(new_user)
        referrer = await get_user(referrer_id)
        referrer["refer_count"] = referrer.get("refer_count", 0) + 1
        await save_user(referrer)

    async def get_refer_stats(user_id: int) -> dict:
        user = await get_user(user_id)
        rc = user.get("refer_count", 0)
        completed = rc // REFERS_NEEDED
        bonus = min(completed * REFER_BONUS, REFER_MAX_BONUS)
        return {"refer_count": rc, "bonus_bots": bonus, "next_bonus_in": REFERS_NEEDED - (rc % REFERS_NEEDED)}

    async def register_chat(chat_id: int, chat_type: str, title: str = ""):
        await _chats.update_one({"_id": chat_id},
            {"$set": {"type": chat_type, "title": title, "active": True}}, upsert=True)

    async def deregister_chat(chat_id: int):
        await _chats.update_one({"_id": chat_id}, {"$set": {"active": False}})

    async def get_all_chat_ids() -> list:
        return [doc["_id"] async for doc in _chats.find({"active": True}, {"_id": 1})]

    async def get_all_user_ids() -> list:
        return [doc["_id"] async for doc in _users.find({}, {"_id": 1})]

    async def record_traffic(chat_id: int):
        await _traffic.update_one({"_id": chat_id}, {"$inc": {"count": 1}}, upsert=True)

    async def get_total_traffic() -> int:
        result = await _traffic.aggregate([{"$group": {"_id": None, "total": {"$sum": "$count"}}}]).to_list(1)
        return result[0]["total"] if result else 0

    async def get_bot_stats() -> dict:
        now = datetime.utcnow()
        ms = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ys = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        total_users   = await _users.count_documents({})
        monthly_users = await _users.count_documents({"joined_at": {"$gte": ms}})
        yearly_users  = await _users.count_documents({"joined_at": {"$gte": ys}})
        total_chats   = await _chats.count_documents({"active": True})
        res = await _users.aggregate([{"$group": {"_id": None, "total": {"$sum": "$clone_count"}}}]).to_list(1)
        total_clones  = res[0]["total"] if res else 0
        total_traffic = await get_total_traffic()
        return {"total_clones": total_clones, "total_users": total_users,
                "monthly_users": monthly_users, "yearly_users": yearly_users,
                "total_chats": total_chats, "total_traffic": total_traffic}

    async def save_clone_token(user_id: int, token: str, bot_username: str):
        await _clones_col.update_one({"token": token},
            {"$set": {"user_id": user_id, "token": token, "bot_username": bot_username,
                      "active": True, "created_at": datetime.utcnow()}}, upsert=True)

    async def remove_clone_token(token: str):
        await _clones_col.update_one({"token": token}, {"$set": {"active": False}})

    async def get_all_clone_tokens() -> list:
        return [doc async for doc in _clones_col.find({"active": True})]

else:
    print("[DB] MONGO_URI not set — using in-memory storage (data lost on restart)")
    _users_mem: dict = {}
    _chats_mem: dict = {}
    _traffic_mem: dict = {}
    _clone_tokens_mem: list = []

    async def get_user(user_id: int) -> dict:
        if user_id not in _users_mem:
            _users_mem[user_id] = {"_id": user_id, "clone_count": 0, "is_donor": False,
                                   "refer_count": 0, "referred_by": None, "joined_at": datetime.utcnow()}
        return _users_mem[user_id]

    async def save_user(user: dict):
        _users_mem[user["_id"]] = user

    async def get_user_limit(user_id: int) -> int:
        return _calc_limit(await get_user(user_id))

    async def increment_clone(user_id: int) -> dict:
        user = await get_user(user_id)
        user["clone_count"] += 1
        return user

    async def mark_donor(user_id: int):
        user = await get_user(user_id)
        user["is_donor"] = True

    async def add_donor(user_id: int) -> dict:
        user = await get_user(user_id)
        user["is_donor"] = True
        return user

    async def process_referral(new_user_id: int, referrer_id: int):
        if new_user_id == referrer_id:
            return
        if new_user_id in _users_mem:
            return
        new_user = await get_user(new_user_id)
        if new_user.get("referred_by"):
            return
        new_user["referred_by"] = referrer_id
        referrer = await get_user(referrer_id)
        referrer["refer_count"] = referrer.get("refer_count", 0) + 1

    async def get_refer_stats(user_id: int) -> dict:
        user = await get_user(user_id)
        rc = user.get("refer_count", 0)
        completed = rc // REFERS_NEEDED
        bonus = min(completed * REFER_BONUS, REFER_MAX_BONUS)
        return {"refer_count": rc, "bonus_bots": bonus, "next_bonus_in": REFERS_NEEDED - (rc % REFERS_NEEDED)}

    async def register_chat(chat_id: int, chat_type: str, title: str = ""):
        _chats_mem[chat_id] = {"type": chat_type, "title": title, "active": True}

    async def deregister_chat(chat_id: int):
        if chat_id in _chats_mem:
            _chats_mem[chat_id]["active"] = False

    async def get_all_chat_ids() -> list:
        return [cid for cid, v in _chats_mem.items() if v.get("active")]

    async def get_all_user_ids() -> list:
        return list(_users_mem.keys())

    async def record_traffic(chat_id: int):
        _traffic_mem[chat_id] = _traffic_mem.get(chat_id, 0) + 1

    async def get_total_traffic() -> int:
        return sum(_traffic_mem.values())

    async def get_bot_stats() -> dict:
        now = datetime.utcnow()
        ms = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ys = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return {
            "total_clones":  sum(u.get("clone_count", 0) for u in _users_mem.values()),
            "total_users":   len(_users_mem),
            "monthly_users": sum(1 for u in _users_mem.values() if u.get("joined_at", now) >= ms),
            "yearly_users":  sum(1 for u in _users_mem.values() if u.get("joined_at", now) >= ys),
            "total_chats":   sum(1 for v in _chats_mem.values() if v.get("active")),
            "total_traffic": sum(_traffic_mem.values()),
        }

    async def save_clone_token(user_id: int, token: str, bot_username: str):
        _clone_tokens_mem.append({"user_id": user_id, "token": token,
                                   "bot_username": bot_username, "active": True})

    async def remove_clone_token(token: str):
        for doc in _clone_tokens_mem:
            if doc["token"] == token:
                doc["active"] = False

    async def get_all_clone_tokens() -> list:
        return [d for d in _clone_tokens_mem if d["active"]]
