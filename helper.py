from PIL import Image
from storage import safe_read
from shared_classes import HashBlacklistObject
import sys
import aiohttp
import hashlib
import imagehash
import io
import re
import datetime
import json
import discord


SUPPORTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG", ".gif", ".gifv"]
SUPPORTED_VIDEO_EXTENSIONS = [".webm", ".mp4", ".mov"]
SUPPORTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".ogg", ".flac"]


def get_links(string: str):
    try:
        string = str(string)
    except:
        return []

    return re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        string,
    )


def has_complex_extension(link: str, extensions: list):
    for ext in extensions:
        if link.find(f"{ext}?") != -1:
            return True

    return False

def link_is_image(link: str):
    return link.endswith(tuple(SUPPORTED_IMAGE_EXTENSIONS)) or has_complex_extension(link, SUPPORTED_IMAGE_EXTENSIONS)


def link_is_video(link: str):
    return link.endswith(tuple(SUPPORTED_VIDEO_EXTENSIONS)) or has_complex_extension(link, SUPPORTED_VIDEO_EXTENSIONS)


def link_is_audio(link: str):
    return link.endswith(tuple(SUPPORTED_AUDIO_EXTENSIONS)) or has_complex_extension(link, SUPPORTED_AUDIO_EXTENSIONS)


def is_blacklisted(guild: discord.Guild, hash: str):
    hash_blacklist = safe_read("global", guild, "hash_blacklist")

    if not (hash_blacklist := hash_blacklist.get()):
        return False
    if not isinstance(hash_blacklist, HashBlacklistObject):
        return False

    return hash_blacklist.blacklisted(hash)


async def hash_external_link(link: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(link) as response:
            try:
                image = Image.open(io.BytesIO(await response.read()))
                hash = imagehash.average_hash(image)
                return f"{hash}"
            except:
                pass

            try:
                hash = hashlib.md5(await response.read()).hexdigest()
                return f"{hash}"
            except:
                pass


class DPrinter:
    def __init__(self, name) -> None:
        self.name = name

        with open("./settings.json", "r") as r:
            settings = json.load(r)

        self.allow_printing = settings["debugPrinting"]

    def dprint(self, *objects, sep=" ", end="\n", file=sys.stdout, flush=False):
        if not self.allow_printing:
            return

        d = datetime.date.today()
        t = datetime.datetime.now()
        prefix = (
            f"{d.year}-{d.month}-{d.day} {t.hour}:{t.minute}:{t.second} | {self.name} |"
        )
        objects = [prefix, *objects]

        print(*objects, sep=sep, end=end, file=file, flush=flush)
