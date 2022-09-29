from discord.ext.commands import Bot
from discord import Intents
from utils.debug import DebugPrinter
import json
import os


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


debug_printer = DebugPrinter(__name__, SETTINGS["debugPrinting"])
dprint = debug_printer.dprint


class Mammoth(Bot):
    def __init__(self):
        super().__init__("mm!", intents=Intents.all())

    async def on_ready(self):
        dprint(
            f"Logged in as {self.user}\nInvite: https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=8&scope=bot%20applications.commands"
        )

    async def setup_hook(self):
        await self.load_cogs()

    async def load_cogs(self):
        for cog in [
            f'cogs.{x[:x.find(".py")]}'
            for x in os.listdir("./cogs")
            if x.endswith(".py")
        ]:
            try:
                await self.load_extension(cog)
            except Exception as e:
                dprint(e)


if __name__ == "__main__":
    with open("./token.json", "r") as r:
        token = json.load(r)

    Mammoth().run(token["token"])
