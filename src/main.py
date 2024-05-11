import json
from asyncio import ensure_future, get_event_loop, gather
from os import getenv

from client import start_clients
from bot import start_bots

ACCOUNTS_PATH = getenv("ACCOUNTS_PATH", "/data/accounts.json")


async def main():
    with open(ACCOUNTS_PATH, "r") as file:
        accounts = json.load(file)

        await gather(
            start_clients(accounts),
            start_bots(accounts),
        )


if __name__ == "__main__":
    ensure_future(main())
    get_event_loop().run_forever()
