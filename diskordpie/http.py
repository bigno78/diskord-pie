
class HttpClient:

    def __init__(self) -> None:
        pass

    def post(self, url, data):
        self.send_request("POST", url, data)

    def get(self, url, data):
        self.send_request("GET", url, data)

    def send_request(method: str, url: str, data: str):
        pass