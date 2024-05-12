from asyncio import sleep
import random
import nodriver as uc
import aiocron
from os import path, listdir, getenv, remove
from dataclasses import dataclass

BROWSER_PATH = getenv("BROWSER_PATH", "/usr/bin/chromium")
PROFILE_BASE_DIR = getenv("PROFILES_PATH", "/srv/profiles")


def remove_locks():
    for d in listdir(PROFILE_BASE_DIR):
        dir_path = path.join(PROFILE_BASE_DIR, d)
        if not path.isdir(dir_path):
            continue
        for f in listdir(dir_path):
            if f.startswith("Singleton"):
                remove(path.join(PROFILE_BASE_DIR, d, f))


@dataclass
class AvatarCycleConfig:
    enable: bool
    cron: str
    dir: str

    @staticmethod
    def Null():
        return AvatarCycleConfig(False, "", "")


class Client:
    i = 0

    browser: uc.Browser
    tab: uc.Tab
    name: str
    activity_cron: aiocron.Cron
    avatar_cycle_config: AvatarCycleConfig
    avatar_cycle_cron: aiocron.Cron
    last_avatar_cycle_path: str | None

    def __init__(self, name: str, avatar_cycle_config: AvatarCycleConfig):
        self.name = name
        self.avatar_cycle_config = avatar_cycle_config
        self.last_avatar_cycle_path = None

    def __del__(self):
        if hasattr(self, "avatar_cycle_cron"):
            self.avatar_cycle_cron.stop()

        self.browser.stop()

    async def create_tab(self):
        Client.i += 1
        self.browser = await uc.start(
            browser_executable_path=BROWSER_PATH,
            user_data_dir=path.join(PROFILE_BASE_DIR, "profile-" + self.name),
            sandbox=False,
            headless=True,
            port=9224 + Client.i,
        )

        self.tab = await self.browser.get("https://discord.com/app")

        if self.avatar_cycle_config.enable:
            self.avatar_cycle_cron = aiocron.crontab(
                self.avatar_cycle_config.cron, func=self.cycle_avatar
            )

        print(f"Client {self.name} connected!")

    def get_random_avatar_path(self, d: str) -> str:
        files = listdir(d)
        avatar_path = random.choice(
            [
                path.join(d, f)
                for f in files
                if path.isfile(path.join(d, f))
                and (path.join(d, f) != self.last_avatar_cycle_path or len(files) <= 1)
            ]
        )
        self.last_avatar_cycle_path = avatar_path
        return avatar_path

    async def cycle_avatar(self):
        await (await self.tab.select('button[aria-label="User Settings"]')).click()
        await (await self.tab.find("edit user profile", best_match=True)).click()
        await (await self.tab.find("change avatar", best_match=True)).click()

        avatar_path = self.get_random_avatar_path(self.avatar_cycle_config.dir)
        print(f"Setting {self.name} avatar to {avatar_path}")

        await (await self.tab.select('input[class="file-input"]')).send_file(
            avatar_path
        )
        await (await self.tab.find("apply", best_match=True)).click()
        await (await self.tab.find("save changes", best_match=True)).click()

        await sleep(3)
        await (await self.tab.select('div[aria-label="Close"]')).click()


async def start_clients(accounts):
    remove_locks()

    for account in accounts:
        avatar_cycle_config = (
            AvatarCycleConfig(
                account["avatarCycle"]["enable"],
                account["avatarCycle"]["cron"],
                account["avatarCycle"]["directory"],
            )
            if account.get("avatarCycle")
            else AvatarCycleConfig.Null()
        )

        await Client(account["name"], avatar_cycle_config).create_tab()
