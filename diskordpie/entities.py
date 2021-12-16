
class User:

    def __init__(self, **kwargs) -> None:
        # TODO: add all the other fields
        self.id = kwargs.get("id")
        self.username = kwargs.get("username")
        self.discriminator = kwargs.get("discriminator")
        self.bot = kwargs.get("bot")


class Application:

    def __init__(self, **kwargs) -> None:
        self.id = kwargs.get("id")
        self.flags = kwargs.get("flags")
