# © [2026] Malith-Rukshan. All rights reserved.

import httpx


class TelegramBotAPI:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}/"

    async def _call(self, action: str, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(self.api_url + action, json=body)
                data = r.json()
                if not r.is_success:
                    print(f"[API ERROR] {action} → {data.get('description', 'Unknown')}")
                    raise Exception(f"Telegram API error: {data.get('description', 'Unknown')}")
                return data
        except httpx.TimeoutException:
            print(f"[API TIMEOUT] {action}")
            raise
        except Exception as e:
            if "Telegram API error" not in str(e):
                print(f"[API NETWORK ERROR] {action}: {e}")
            raise

    async def send_message(self, chat_id: int, text: str, inline_keyboard: list = None):
        body = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if inline_keyboard:
            body["reply_markup"] = {"inline_keyboard": inline_keyboard}
        await self._call("sendMessage", body)

    async def set_message_reaction(self, chat_id: int, message_id: int, emoji: str):
        await self._call("setMessageReaction", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
            "is_big": True,
        })

    async def send_invoice(self, chat_id, title, description, payload, provider_token, start_parameter, currency, prices):
        await self._call("sendInvoice", {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "provider_token": provider_token,
            "start_parameter": start_parameter,
            "currency": currency,
            "prices": prices,
        })

    async def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool):
        await self._call("answerPreCheckoutQuery", {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": ok,
        })

    async def answer_callback_query(self, callback_query_id: str, text: str = ""):
        body = {"callback_query_id": callback_query_id}
        if text:
            body["text"] = text
        await self._call("answerCallbackQuery", body)
