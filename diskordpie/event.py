
class DiscordEvent:

    def __init__(self, event_json) -> None:
        if event_json["op"] != 0:
            raise Exception("Can't create Event from not DISPATCH message.")

        self.type = event_json["t"]
        self.data = event_json["d"]
