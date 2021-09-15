
class HttpClient:

    def __init__(self) -> None:
        pass

    async def post(self, url, data):
        self.send_request("POST", url, data)

    async def get(self, url, data):
        self.send_request("GET", url, data)

    async def send_request(method: str, url: str, data: str):
        pass