from __future__ import annotations

import httpx


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        """텔레그램 봇 토큰/채팅방 ID로 알림 전송기를 초기화한다."""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.client = httpx.Client(timeout=5.0)

    def send(self, text: str) -> None:
        """설정이 있을 때만 텔레그램 메시지를 전송한다."""
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.client.post(url, json={"chat_id": self.chat_id, "text": text})
