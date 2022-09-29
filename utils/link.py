import re
import discord
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaSortedLinks:
    image_links: list[str]
    video_links: list[str]
    audio_links: list[str]
    other_links: list[str]


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


def has_complex_extension(link: str, extensions: list):
    for ext in extensions:
        if link.find(f"{ext}?") != -1:
            return True

    return False


def get_links_from_string(string: str):
    try:
        string = str(string)
    except:
        return []

    return re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        string,
    )


def get_media_sorted_links_from_list(links: list[str]):
    image_links = []
    video_links = []
    audio_links = []
    other_links = []

    for link in links:
        if link_is_image(link):
            if link in image_links:
                continue

            image_links.append(link)
        elif link_is_video(link):
            if link in video_links:
                continue

            video_links.append(link)
        elif link_is_audio(link):
            if link in audio_links:
                continue

            audio_links.append(link)
        else:
            if link in other_links:
                continue

            other_links.append(link)

    return MediaSortedLinks(image_links, video_links, audio_links, other_links)


def get_media_sorted_links_from_message(message: discord.Message):
    links = []

    for attachment in message.attachments:
        if attachment.url not in links:
            links.append(attachment.url)

    for embed in message.embeds:
        if embed.title:
            for link in get_links_from_string(embed.title):
                if link not in links:
                    links.append(link)
        if embed.description:
            for link in get_links_from_string(embed.description):
                if link not in links:
                    links.append(link)
        if embed.url:
            if embed.url not in links:
                links.append(embed.url)
        if embed.footer:
            for link in get_links_from_string(embed.footer):
                if link not in links:
                    links.append(link)
        if embed.image:
            if embed.image.url:
                if embed.image.url not in links:
                    links.append(embed.image.url)
        if embed.thumbnail:
            if embed.thumbnail.url:
                if embed.thumbnail.url not in links:
                    links.append(embed.thumbnail.url)
        if embed.video:
            if embed.video.url:
                if embed.video.url not in links:
                    links.append(embed.video.url)
        if embed.provider:
            if embed.provider.name:
                for link in get_links_from_string(embed.provider.name):
                    if link not in links:
                        links.append(link)
            if embed.provider.url:
                if embed.provider.url not in links:
                    links.append(embed.provider.url)
        if embed.fields:
            for field in embed.fields:
                if field.name:
                    for link in get_links_from_string(field.name):
                        if link not in links:
                            links.append(link)
                if field.value:
                    for link in get_links_from_string(field.value):
                        if link not in links:
                            links.append(link)

    for link in get_links_from_string(message.content):
        if link not in links:
            links.append(link)

    return get_media_sorted_links_from_list(links)
