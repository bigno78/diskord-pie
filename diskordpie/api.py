import json

from .http import HttpClient
from .commands import SlashCommand
from .entities import Application

class DiscordAPI:

    def __init__(self, http: HttpClient, app: Application) -> None:
        self._http = http
        self._app = app

    async def create_slash_command(self, cmd: SlashCommand) -> SlashCommand:
        url = f"/applications/{self._app.id}/commands"
        payload = {
            "name": cmd.name,
            "description": cmd.description,
            "options": [],
        }

        for opt in cmd.options:
            assert opt.type is not None
            opt_data = {
                "type": opt.type,
                "name": opt.name,
                "description": opt.description,
                "required": opt.required,
                "min_value": opt.min_value,
                "max_value": opt.max_value,
            }
            payload["options"].append(opt_data)
        
        print("creating cmd: ")
        print(json.dumps(payload, indent=4))

        resp = await self._http.post(url, payload)

        cmd._id = resp["id"]

        return cmd
