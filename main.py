from diskordpie.bot import Bot
import asyncio
import aiohttp
import json

from diskordpie.http import Route

def main():
    b = Bot()
    b.run("NzE4MDAyNzczMzA3OTQ5MTE3.XtiiMQ.6kzS27RWzHPW7Q-DCAYocl_OQtI")

async def test_aio():
    async with aiohttp.ClientSession() as session:
        async with session.request("GET", "https://diskcord.com/apii/v9") as r:
            print(f"STATUS: {r.status} {r.reason}")
            print(await r.read())


if __name__ == "__main__":
    #main()
    asyncio.run(test_aio())
