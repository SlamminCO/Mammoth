from dataclasses import dataclass
from typing import Optional, Tuple
from utils.link import get_media_sorted_links_from_message, MediaSortedLinks
from PIL import Image
from utils.storage import safe_read, safe_edit
import imagehash
import discord
import aiohttp
import asyncio
import hashlib
import io
import json


DEFAULT_URL_TO_LINK_HASH_CACHE = {
    "cache": {}
}


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


@dataclass(frozen=True)
class LinkHash:
    link: str
    md5: Optional[str]
    image_hash: Optional[str]
    media_type: str = None or "image" or "video" or "audio"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass(frozen=True)
class MediaSortedLinkHashes:
    image_link_hashes: list[LinkHash]
    video_link_hashes: list[LinkHash]
    audio_link_hashes: list[LinkHash]
    other_link_hashes: list[LinkHash]


# class URLToLinkHashCache:
#     def __init__(self):
#         self.url_to_link_hash_cache = {}

#     def get(self, url: str) -> Optional[LinkHash]:
#         return self.url_to_link_hash_cache.get(url)

#     def set(self, url: str, link_hash: LinkHash):
#         self.url_to_link_hash_cache[url] = link_hash

#     def all(self) -> list[Tuple[str, LinkHash]]:
#         return zip(
#             self.url_to_link_hash_cache.keys(), self.url_to_link_hash_cache.values()
#         )


async def get_link_hash(
    link: str, media_type: str = None or "image" or "video" or "audio"
):
    md5_hash = None
    image_hash = None

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as response:
                    data = await response.read()

                    try:
                        md5_hash = hashlib.md5(data).hexdigest()
                        md5_hash = f"{md5_hash}"
                    except:
                        pass

                    try:
                        image = Image.open(io.BytesIO(data))
                        image_hash = imagehash.average_hash(image)
                        image_hash = f"{image_hash}"
                    except:
                        pass

                    break
        except asyncio.TimeoutError:
            pass
        except Exception:
            break

    return LinkHash(link, md5_hash, image_hash, media_type)


async def get_media_sorted_link_hashes_from_media_sorted_links(
    media_sorted_links: MediaSortedLinks, guild: discord.Guild
):
    image_link_hashes = []
    video_link_hashes = []
    audio_link_hashes = []
    other_link_hashes = []
    tasks = []

    if SETTINGS["caching"]:
        if not (temp_url_to_link_hash_cache_data := safe_read("global", guild, "url_to_link_hash_cache")):
            temp_url_to_link_hash_cache_data = DEFAULT_URL_TO_LINK_HASH_CACHE.copy()
    else:
        temp_url_to_link_hash_cache_data = DEFAULT_URL_TO_LINK_HASH_CACHE.copy()

    for link in media_sorted_links.image_links:
        if not (link_hash_data := temp_url_to_link_hash_cache_data["cache"].get(link)):
            if SETTINGS["asyncio_gather"]:
                tasks.append(get_link_hash(link, "image"))
                continue

            link_hash = await get_link_hash(link, "image")
            temp_url_to_link_hash_cache_data["cache"][link] = link_hash
        else:
            link_hash = LinkHash.from_dict(link_hash_data)

        image_link_hashes.append(link_hash)
    for link in media_sorted_links.video_links:
        if not (link_hash_data := temp_url_to_link_hash_cache_data["cache"].get(link)):
            if SETTINGS["asyncio_gather"]:
                tasks.append(get_link_hash(link, "video"))
                continue

            link_hash = await get_link_hash(link, "video")
            temp_url_to_link_hash_cache_data["cache"][link] = link_hash
        else:
            link_hash = LinkHash.from_dict(link_hash_data)

        video_link_hashes.append(link_hash)
    for link in media_sorted_links.audio_links:
        if not (link_hash_data := temp_url_to_link_hash_cache_data["cache"].get(link)):
            if SETTINGS["asyncio_gather"]:
                tasks.append(get_link_hash(link, "audio"))
                continue

            link_hash = await get_link_hash(link, "audio")
            temp_url_to_link_hash_cache_data["cache"][link] = link_hash
        else:
            link_hash = LinkHash.from_dict(link_hash_data)

        audio_link_hashes.append(link_hash)
    for link in media_sorted_links.other_links:
        other_link_hashes.append(LinkHash(link, None, None, None))

    if SETTINGS["asyncio_gather"]:
        results = await asyncio.gather(*tasks)

        for result in results:
            temp_url_to_link_hash_cache_data["cache"][result.link] = result

            if result.media_type == "image":
                image_link_hashes.append(result)
                continue
            if result.media_type == "video":
                video_link_hashes.append(result)
                continue
            if result.media_type == "audio":
                audio_link_hashes.append(result)

    if SETTINGS["caching"]:
        async with safe_edit(
            "global", guild, "url_to_link_hash_cache"
        ) as url_to_link_hash_cache_data:
            if not url_to_link_hash_cache_data or not url_to_link_hash_cache_data.get(
                "cache", DEFAULT_URL_TO_LINK_HASH_CACHE["cache"]
            ):
                url_to_link_hash_cache_data = DEFAULT_URL_TO_LINK_HASH_CACHE.copy()

            for url, link_hash in temp_url_to_link_hash_cache_data["cache"]:
                if not url_to_link_hash_cache_data.get(url):
                    url_to_link_hash_cache_data["cache"][url] = link_hash
                    
    return MediaSortedLinkHashes(
        image_link_hashes, video_link_hashes, audio_link_hashes, other_link_hashes
    )


async def get_media_sorted_link_hashes_from_message(message: discord.Message):
    media_sorted_links = get_media_sorted_links_from_message(message)
    media_sorted_link_hashes = (
        await get_media_sorted_link_hashes_from_media_sorted_links(
            media_sorted_links, message.guild
        )
    )

    return media_sorted_link_hashes
