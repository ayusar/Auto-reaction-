# © [2026] Malith-Rukshan. All rights reserved.

import re
import random


def get_random_positive_reaction(reactions: list) -> str:
    return random.choice(reactions)


def split_emojis(emoji_string: str) -> list:
    if not emoji_string:
        return []
    pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F004-\U0001F0CF"
        "]+",
        flags=re.UNICODE,
    )
    return pattern.findall(emoji_string)


def get_chat_ids(chats_env: str) -> list:
    if not chats_env:
        return []
    result = []
    for item in chats_env.split(","):
        item = item.strip()
        if item:
            try:
                result.append(int(item))
            except ValueError:
                pass
    return result
