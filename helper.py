from PIL import Image
from storage import safe_read, safe_edit
from shared_classes import HashBlacklistObject, URLToHashCache
import sys
import aiohttp
import hashlib
import imagehash
import io
import re
import datetime
import json
import discord
import threading
import asyncio


SUPPORTED_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".JPG",
    ".JPEG",
    ".png",
    ".PNG",
    ".gif",
    ".gifv",
]
SUPPORTED_VIDEO_EXTENSIONS = [".webm", ".mp4", ".mov"]
SUPPORTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".ogg", ".flac"]

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


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
    return link.endswith(tuple(SUPPORTED_IMAGE_EXTENSIONS)) or has_complex_extension(
        link, SUPPORTED_IMAGE_EXTENSIONS
    )


def link_is_video(link: str):
    return link.endswith(tuple(SUPPORTED_VIDEO_EXTENSIONS)) or has_complex_extension(
        link, SUPPORTED_VIDEO_EXTENSIONS
    )


def link_is_audio(link: str):
    return link.endswith(tuple(SUPPORTED_AUDIO_EXTENSIONS)) or has_complex_extension(
        link, SUPPORTED_AUDIO_EXTENSIONS
    )


def get_media_urls_from_message(message: discord.Message):
    image_urls = []
    video_urls = []
    audio_urls = []
    standard_urls = []
    content_urls = []

    def sort_url(url: str):
        if link_is_image(url):
            if url in image_urls:
                return

            image_urls.append(url)
        elif link_is_video(url):
            if url in video_urls:
                return

            video_urls.append(url)
        elif link_is_audio(url):
            if url in audio_urls:
                return

            audio_urls.append(url)
        else:
            if url in standard_urls:
                return

            standard_urls.append(url)

    # Sort Attachment URLs

    for attachment in message.attachments:
        if attachment.content_type.find("image") != -1:
            if attachment.url in image_urls:
                continue

            image_urls.append(attachment.url)
        elif attachment.content_type.find("video") != -1:
            if attachment.url in video_urls:
                continue

            video_urls.append(attachment.url)
        elif attachment.content_type.find("audio") != -1:
            if attachment.url in audio_urls:
                continue

            audio_urls.append(attachment.url)
        else:
            sort_url(attachment.url)

    # Sort Embed URLs

    for embed in message.embeds:
        if embed.title:
            for url in get_links(embed.title):
                sort_url(url)
        if embed.description:
            for url in get_links(embed.description):
                sort_url(url)
        if embed.url:
            sort_url(embed.url)
        if embed.footer:
            for url in get_links(embed.footer):
                sort_url(url)
        if embed.image:
            if embed.image.url:
                sort_url(embed.image.url)
        if embed.thumbnail:
            if embed.thumbnail.url:
                sort_url(embed.thumbnail.url)
        if embed.video:
            if embed.video.url:
                sort_url(embed.video.url)
        if embed.provider:
            if embed.provider.name:
                for url in get_links(embed.provider.name):
                    sort_url(url)
            if embed.provider.url:
                sort_url(embed.provider.url)
        if embed.fields:
            for field in embed.fields:
                if field.name:
                    for url in get_links(field.name):
                        sort_url(url)
                if field.value:
                    for url in get_links(field.value):
                        sort_url(url)

    # Sort Content URLs

    for url in get_links(message.content):
        content_urls.append(url)
        sort_url(url)

    return image_urls, video_urls, audio_urls, standard_urls, content_urls


async def get_media_hashes_from_message(message: discord.Message):
    dprint = DPrinter(__name__).dprint
    sdprint_dprinter = DPrinter(__name__)
    sdprint_dprinter.allow_printing = SETTINGS["spammyDebugPrinting"]
    sdprint = sdprint_dprinter.dprint

    guild = message.guild
    (
        image_urls,
        video_urls,
        audio_urls,
        standard_urls,
        content_urls,
    ) = get_media_urls_from_message(message)
    media_urls = image_urls + video_urls + audio_urls

    threads = []
    results = {}

    async def hash_external_link(link: str):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as response:
                        data = await response.read()

                        try:
                            image = Image.open(io.BytesIO(data))
                            hash = imagehash.average_hash(image)
                            return f"{hash}"
                        except:
                            pass

                        try:
                            hash = hashlib.md5(data).hexdigest()
                            return f"{hash}"
                        except:
                            pass
            except asyncio.TimeoutError:
                pass

    def generate_hash(*, url):
        loop = asyncio.new_event_loop()

        results[url] = loop.run_until_complete(hash_external_link(url))

    url_to_hash = safe_read("global", guild, "url_to_hash")

    if not (url_to_hash := url_to_hash.get()):
        url_to_hash = URLToHashCache()
    if not isinstance(url_to_hash, URLToHashCache):
        url_to_hash = URLToHashCache()

    for url in media_urls:
        if not (hash := url_to_hash.get(url)):
            if SETTINGS["threading"] and len(media_urls) > 1:
                thread = threading.Thread(target=generate_hash, kwargs={"url": url})
                threads.append(thread)
                thread.start()
            else:
                results[url] = await hash_external_link(url)

            dprint(
                f"No cache found. Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
            )
            continue

        dprint(
            f"Cache found! Hash: [{hash}] Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
        )

        results[url] = hash

    if threads:
        while True:
            threads_still_alive = False

            for thread in threads:
                if thread.is_alive():
                    threads_still_alive = True
                    break

            if not threads_still_alive:
                dprint(f"Threads completed! Guild: [{guild}] Message: [{message.id}]")
                break

            sdprint(f"Waiting for threads. Guild: [{guild}] Message: [{message.id}]")

            await asyncio.sleep(1)

    # Cache Hashes

    async with safe_edit("global", guild, "url_to_hash") as url_to_hash_storage_object:
        if not (url_to_hash := url_to_hash_storage_object.get()):
            url_to_hash = URLToHashCache()
        if not isinstance(url_to_hash, URLToHashCache):
            url_to_hash = URLToHashCache()

        for url in results:
            if not url_to_hash.get(url):
                url_to_hash.set(url, results[url])

        url_to_hash_storage_object.set(url_to_hash)

    # Return Results

    return (results, (image_urls, video_urls, audio_urls, standard_urls, content_urls))


class DPrinter:
    def __init__(self, name) -> None:
        self.name = name
        self.allow_printing = SETTINGS["debugPrinting"]

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
