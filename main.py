from discord.ext.commands import Bot
from discord import Intents
from logging.handlers import RotatingFileHandler
from utils.storage import migrate_storage
import json
import os
import contextlib
import logging
import discord
import traceback


log = logging.getLogger()


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


"""

This logging wrapper comes from Rapptz's RoboDanny launcher, the source for which can be found here:

Source: https://github.com/Rapptz/RoboDanny
Author: https://github.com/Rapptz

It has been slightly modified to fit this project.
I am not knowledgeable on licensing, so please do contact me if there are any issues.

"""


@contextlib.contextmanager
def logging_wrapper():
    try:
        discord.utils.setup_logging()
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)

        log.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            filename="mammoth.log",
            encoding="utf-8",
            mode="w",
            maxBytes=67108864,
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        fmt = logging.Formatter(
            "[{asctime}] [{levelname:<7}] {name}: {message}", dt_fmt, style="{"
        )
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        handlers = log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)


class Mammoth(Bot):
    def __init__(self):
        super().__init__("mm!", intents=Intents.all())

    async def on_ready(self):
        log.info(f"Logged in as {self.user}")
        log.info(
            f"Invite: https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=8&scope=bot%20applications.commands"
        )

    async def setup_hook(self):
        migrate_storage()
        
        await self.load_cogs()

    async def load_cogs(self):
        for cog in [
            f'cogs.{x[:x.find(".py")]}'
            for x in os.listdir("./cogs")
            if x.endswith(".py")
        ]:
            try:
                await self.load_extension(cog)
            except Exception:
                log.exception(traceback.format_exc())


if __name__ == "__main__":
    with open("./token.json", "r") as r:
        token = json.load(r)

    with logging_wrapper():
        Mammoth().run(token["token"])
