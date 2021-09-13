import diskordpie.gateway
import asyncio

async def main():
    g = diskordpie.gateway.Gateway()
    g.connect("NzE4MDAyNzczMzA3OTQ5MTE3.XtiiMQ.6kzS27RWzHPW7Q-DCAYocl_OQtI")
    g.close()

if __name__ == "__main__":
    asyncio.run(main())