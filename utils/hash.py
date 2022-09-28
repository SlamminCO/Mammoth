from dataclasses import dataclass
from typing import Optional
from utils.link import get_media_sorted_links_from_message, MediaSortedLinks
from PIL import Image
import imagehash
import discord
import aiohttp
import asyncio
import hashlib
import io


@dataclass(frozen=True)
class LinkHash:
    link: str
    md5: Optional[str]
    image_hash: Optional[str]


@dataclass(frozen=True)
class MediaSortedLinkHashes:
    image_links: list[LinkHash]
    video_links: list[LinkHash]
    audio_links: list[LinkHash]
    other_links: list[LinkHash]


async def get_link_hash(link: str):
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

    return LinkHash(link, md5_hash, image_hash)


async def get_media_sorted_link_hashes_from_media_sorted_links(
    media_sorted_links: MediaSortedLinks,
):
    image_link_hashes = []
    video_link_hashes = []
    audio_link_hashes = []
    other_link_hashes = []

    for link in media_sorted_links.image_links:
        image_link_hashes.append(await get_link_hash(link))
    for link in media_sorted_links.video_links:
        video_link_hashes.append(await get_link_hash(link))
    for link in media_sorted_links.audio_links:
        audio_link_hashes.append(await get_link_hash(link))
    for link in media_sorted_links.other_links:
        other_link_hashes.append(LinkHash(link, None, None))

    return MediaSortedLinkHashes(
        image_link_hashes, video_link_hashes, audio_link_hashes, other_link_hashes
    )


async def get_media_sorted_link_hashes_from_message(message: discord.Message):
    media_sorted_links = get_media_sorted_links_from_message(message)
    media_sorted_link_hashes = (
        await get_media_sorted_link_hashes_from_media_sorted_links(media_sorted_links)
    )

    return media_sorted_link_hashes
