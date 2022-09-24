from discord.ext.commands import Bot
from discord import Intents
from helper import DPrinter
import json
import os


dprint = DPrinter(__name__).dprint


class Mammoth(Bot):
    def __init__(self):
        super().__init__("mm!", intents=Intents.all())

    async def on_ready(self):
        dprint(f"Logged in as {self.user}")

    async def setup_hook(self) -> None:
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
