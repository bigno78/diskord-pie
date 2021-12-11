#from diskordpie.bot import Bot
import asyncio
import aiohttp
import json

import diskordpie

#from diskordpie.http import Route

def main():
    b = diskordpie.bot.Bot()
    b.run("NzE4MDAyNzczMzA3OTQ5MTE3.XtiiMQ.6kzS27RWzHPW7Q-DCAYocl_OQtI")

async def test_aio():
    http = diskordpie.http.HttpClient()
    http._token = "NzE4MDAyNzczMzA3OTQ5MTE3.XtiiMQ.6kzS27RWzHPW7Q-DCAYocl_OQtI"

    for i in range(5):
        r = await http.get("/gateway/bot")
        if not r:
            break
        print()

    await http.close_session()


if __name__ == "__main__":
    # headers = {"X-RateLimit-Limit": "25.6"}
    # c = diskordpie.http.parse_rate_header(headers, "X-RateLimit-Limit", float)
    # print(c)
    main()
    #asyncio.run(test_aio())
