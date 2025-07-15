from dataclasses import dataclass
from asyncio import Task, gather, sleep, create_task
from typing import Any
from websockets import connect, WebSocketClientProtocol, ConnectionClosed
from websockets.protocol import State
from random import random
from json import loads, dumps

GATEWAY_ADDRESS = "wss://gateway.discord.gg/?encoding=json&v=9"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class Emoji:
    id: str | None
    name: str


@dataclass
class ActivityButton:
    label: str
    url: str


@dataclass
class ActivityAssets:
    largeImage: str
    largeText: str
    smallImage: str
    smallText: str


@dataclass
class ActivityTimestamps:
    start: str
    end: str


@dataclass
class Activity:
    id: str
    details: str
    name: str
    assets: ActivityAssets
    timestamps: ActivityTimestamps
    type: str | None
    buttons: list[ActivityButton] | None


@dataclass
class Presence:
    emoji: Emoji | None
    text: str | None
    status: str
    activity: Activity | None


class Bot:
    name: str
    token: str
    presence: Presence
    ws: WebSocketClientProtocol
    last_sequence_number: int
    heartbeat_task: Task

    def __init__(self, name: str, token: str, presence: Presence):
        self.name = name
        self.token = token
        self.presence = presence

    def __del__(self):
        self.heartbeat_task.cancel()
        pass

    async def start(self):
        async for ws in connect(
            GATEWAY_ADDRESS, user_agent_header=USER_AGENT, max_size=1_000_000_000
        ):
            if hasattr(self, "ws") and self.ws.state == State.OPEN:
                await self.ws.close()
            try:
                self.ws = ws
                await gather(self.on_message(), self.ws_ready())
            except ConnectionClosed as e:
                print(f"Bot {self.name} disconnected ({e.code}), reconnecting...")

    async def ws_ready(self):
        await self.ws.send(dumps(self.get_identify_payload()))
        print(f"Bot {self.name} connected!")

    async def on_message(self):
        async for message in self.ws:
            data = loads(message)
            if not data:
                continue

            if isinstance(data.get("s"), int):
                self.last_sequence_number = data["s"]

            if data["op"] == 10:
                heartbeat_interval_ms: int = data["d"]["heartbeat_interval"]

                if hasattr(self, "heartbeat_task"):
                    self.heartbeat_task.cancel()
                self.heartbeat_task = create_task(
                    self.start_heartbeating(heartbeat_interval_ms)
                )

    async def start_heartbeating(self, heartbeat_interval_ms: int):
        await sleep(heartbeat_interval_ms / 1000 * random())
        while True:
            await self.send_heartbeat()
            await sleep(heartbeat_interval_ms / 1000)

    def get_presence_data(self):
        emoji = self.presence.emoji
        activity = self.presence.activity

        return {
            "status": self.presence.status,
            "afk": True,
            "since": 1000,
            "activities": [
                {
                    "type": 4,
                    "name": "Custom Status",
                    "state": self.presence.text,
                    "emoji": emoji
                    and {"id": emoji and emoji.id, "name": emoji and emoji.name},
                },
                activity
                and {
                    "type": 3,
                    "name": activity.name,
                    "application_id": activity.id,
                    "details": activity.details,
                    "assets": activity.assets
                    and {
                        "large_image": activity.assets.largeImage,
                        "large_text": activity.assets.largeText,
                        "small_image": activity.assets.smallImage,
                        "small_text": activity.assets.smallText,
                    },
                    "buttons": [b.label for b in activity.buttons or []],
                    "metadata": {
                        "button_urls": [b.url for b in activity.buttons or []]
                    },
                },
            ],
        }

    def get_presence_payload(self):
        return {"op": 3, "d": self.get_presence_data()}

    async def send_presence(self):
        await self.ws.send(dumps(self.get_presence_payload()))

    def get_identify_payload(self) -> dict[Any, Any]:
        return {
            "op": 2,
            "d": {
                "token": self.token,
                "capabilities": 16381,
                "properties": {
                    "os": "Windows",
                    "browser": "Chrome",
                    "device": "",
                    "system_locale": "en-US",
                    "browser_user_agent": USER_AGENT,
                    "browser_version": "120.0.0.0",
                    "os_version": "10",
                    "referrer": "",
                    "referring_domain": "",
                    "referrer_current": "",
                    "referrring_domain_current": "",
                    "release_channel": "stable",
                    "client_build_number": 291963,
                    "client_event_source": None,
                },
                "presence": self.get_presence_data(),
                "compress": False,
                "client_state": {"guild_versions": {}},
            },
        }

    async def send_heartbeat(self):
        await self.ws.send(dumps({"op": 1, "d": self.last_sequence_number}))


async def start_bots(accounts):
    bots = []
    for account in accounts:
        emoji = (
            (p := account.get("presence"))
            and (e := p.get("emoji"))
            and Emoji(e.get("id"), e["name"])
        )
        assets = (
            (p := account.get("presence"))
            and (a := p.get("activity"))
            and (a := p.get("assets"))
            and ActivityAssets(
                a["largeImage"],
                a["largeText"],
                a["smallImage"],
                a["smallText"],
            )
        )
        timestamps = (
            (p := account.get("presence"))
            and (a := p.get("activity"))
            and (t := p.get("timestamps"))
            and ActivityTimestamps(
                t["start"],
                t["end"],
            )
        )
        buttons = (
            [
                ActivityButton(b["label"], b["url"])
                for b in account["presence"]["buttons"]
            ]
            if (p := account.get("presence")) and p.get("buttons")
            else []
        )
        activity = (
            (p := account.get("presence"))
            and (a := p.get("activity"))
            and Activity(
                a["id"],
                a["details"],
                a["name"],
                assets,
                timestamps,
                a.get("type"),
                buttons,
            )
        )
        presence = (p := account.get("presence")) and Presence(
            emoji, p.get("text"), p["status"], activity
        )

        bots.append(Bot(account["name"], account["token"], presence))

    gather(*[bot.start() for bot in bots])
