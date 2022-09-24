from time import time
from helper import DPrinter
from discord.ext import commands
from main import Mammoth
from storage import safe_edit, safe_read
from discord.ui import Button, View, Select
# from shared_classes import HashBlacklistButton
import discord
import helper
import threading
import asyncio
import json


COG = __name__
DEFAULT_REFLECT_COG_SETTINGS = {
    "enabled": False,
    "ignored_channel_ids": [],
    "ignored_role_ids": [],
    "reflect_channel_id": None,
}

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


dprint = DPrinter(COG).dprint
spammy_dprint_instance = DPrinter(COG)
spammy_dprint_instance.allow_printing = SETTINGS["spammyDebugPrinting"]
sdprint = spammy_dprint_instance.dprint


class ReflectCogSettingsObject:
    def __init__(self):
        self.settings = DEFAULT_REFLECT_COG_SETTINGS

    def update(self):
        for key in DEFAULT_REFLECT_COG_SETTINGS:
            if key not in self.settings:
                self.settings[key] = DEFAULT_REFLECT_COG_SETTINGS[key]

    def get(self, key: str):
        self.update()

        return self.settings.get(key)

    def set(self, key: str, value):
        self.settings[key] = value


class URLToHashCache:
    def __init__(self):
        self.url_to_hash = {}

    def get(self, url: str):
        return self.url_to_hash.get(url)

    def set(self, url: str, hash: str):
        self.url_to_hash[url] = hash


class ReflectionDeleteButton(Button):
    def __init__(self, message: discord.Message, jump_button: Button):
        super().__init__(label="Delete", style=discord.ButtonStyle.red)

        self.message = message
        self.jump_button = jump_button

    async def callback(self, interaction: discord.Interaction):
        if not self.message.channel.permissions_for(interaction.user).manage_messages:
            return await interaction.response.send_message(
                f"You do not have permission to manage messages in {self.message.channel.mention}!"
            )

        try:
            await self.message.delete()

            self.disable()

            await interaction.response.edit_message(view=self.view)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to delete the message!"
            )
        except discord.NotFound:
            self.disable()

            await interaction.response.edit_message(view=self.view)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"I could not delete the message!\n\n```{e}```"
            )

    def disable(self):
        self.disabled = True
        self.jump_button.disabled = True
        self.label = "Message Deleted"


class ReflectionView(View):
    def __init__(self, message: discord.Message, hash: str = None):
        super().__init__(timeout=None)

        self.message = message
        self.hash = hash

        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.delete_button = ReflectionDeleteButton(self.message, self.jump_button)
        # self.blacklist_button = HashBlacklistButton(self.message, self.hash)

        self.add_item(self.delete_button)

        # if hash:
        #     self.add_item(self.blacklist_button)

        self.add_item(self.jump_button)


class CompactImageReflectionPart:
    def __init__(self, url: str, hash: str, message: discord.Message):
        self.url = url
        self.hash = hash
        self.message = message
        self.embed = discord.Embed()

        self.embed.add_field(name="User", value=self.message.author.mention)
        self.embed.add_field(name="Channel", value=self.message.channel.mention)
        self.embed.add_field(name="URL", value=self.url, inline=False)
        self.embed.add_field(name="Hash", value=hash, inline=False)

        if len(message.content) != 0:
            self.embed.add_field(name="Content", value=message.content, inline=False)

        self.embed.set_image(url=url)


class CompactImageReflectionView(View):
    def __init__(
        self,
        message: discord.Message,
        compact_reflection_parts: list[CompactImageReflectionPart],
    ):
        super().__init__(timeout=None)

        self.message = message
        self.parts = compact_reflection_parts
        self.value_to_part = {}

        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.delete_button = ReflectionDeleteButton(self.message, self.jump_button)

        if len(compact_reflection_parts) > 1:
            self.media_select = Select(placeholder="Select an image to view.")

            for i, part in enumerate(compact_reflection_parts):
                new_select_option = discord.SelectOption(
                    label=f"Image {i + 1}",
                    value=f"{i}",
                    default=True if i == 0 else False,
                )
                self.media_select.append_option(new_select_option)
                self.value_to_part[f"{i}"] = part

            # self.blacklist_button = HashBlacklistButton(
            #     self.message, self.value_to_part["0"].hash
            # )

            async def media_select_callback(interaction: discord.Interaction):
                # self.blacklist_button.hash = self.value_to_part[
                #     self.media_select.values[0]
                # ].hash

                # self.blacklist_button.update_mode()

                for option in self.media_select.options:
                    if option.value != self.media_select.values[0]:
                        option.default = False
                    else:
                        option.default = True

                await interaction.response.edit_message(
                    embed=self.value_to_part[self.media_select.values[0]].embed,
                    view=self,
                )

            self.media_select.callback = media_select_callback

            self.add_item(self.media_select)
        # else:
        #     self.blacklist_button = HashBlacklistButton(
        #         self.message, compact_reflection_parts[0].hash
        #     )

        self.add_item(self.delete_button)
        # self.add_item(self.blacklist_button)
        self.add_item(self.jump_button)


@discord.app_commands.guild_only()
class ReflectCog(commands.GroupCog, name="reflect"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        dprint(f"Loaded {COG}")

    async def send_compact_image_reflection(
        self,
        *,
        reflect_channel: discord.TextChannel,
        message: discord.Message,
        compact_image_reflection_parts: list[CompactImageReflectionPart],
    ):
        compact_image_reflection = await reflect_channel.send(
            embed=compact_image_reflection_parts[0].embed,
            view=CompactImageReflectionView(message, compact_image_reflection_parts),
        )
        return compact_image_reflection

    async def send_primary_reflection(
        self,
        *,
        reflect_channel: discord.TextChannel,
        message: discord.Message,
        url: str,
        hash: str = None,
        image_url: str = None,
        content: str = None,
    ):
        embed = discord.Embed()

        embed.add_field(name="User", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="URL", value=url, inline=False)

        if hash:
            embed.add_field(name="Hash", value=hash, inline=False)
        if len(message.content) != 0:
            embed.add_field(name="Content", value=message.content, inline=False)
        if image_url:
            embed.set_image(url=image_url)

        reflect_message = await reflect_channel.send(
            content=content,
            embed=embed,
            view=ReflectionView(message, hash),
        )

        return reflect_message

    async def send_additional_reflection(
        self,
        *,
        primary_reflection: discord.Message,
        message: discord.Message,
        url: str,
        hash: str = None,
        image_url: str = None,
        content: str = None,
    ):

        embed = discord.Embed(title="Additional Media")

        embed.add_field(name="URL", value=url, inline=False)

        if hash:
            embed.add_field(name="Hash", value=hash, inline=False)
        if image_url:
            embed.set_image(url=image_url)

        additional_reflection = await primary_reflection.reply(
            content=content,
            embed=embed,
            view=ReflectionView(message, hash),
        )

        return additional_reflection

    @commands.Cog.listener(name="on_message")
    async def reflect_on_message(self, message: discord.Message):
        timings = {}
        total_time_start = time()

        channel = message.channel

        if not (guild := message.guild):
            return

        settings = safe_read(COG, guild, "settings")

        if not (settings := settings.get()):
            return
        if not isinstance(settings, ReflectCogSettingsObject):
            return
        if not settings.get("enabled"):
            return
        if channel.id in settings.get("ignored_channel_ids"):
            return
        if channel.id == (reflect_channel_id := settings.get("reflect_channel_id")):
            return
        for role in message.author.roles:
            if role.id in settings.get("ignored_role_ids"):
                return
        if not (reflect_channel := guild.get_channel(reflect_channel_id)):
            return

        image_urls = []
        video_urls = []
        audio_urls = []
        standard_urls = []

        def sort_url(url: str):
            if helper.link_is_image(url):
                if url in image_urls:
                    return

                image_urls.append(url)
            elif helper.link_is_video(url):
                if url in video_urls:
                    return

                video_urls.append(url)
            elif helper.link_is_audio(url):
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
                for url in helper.get_links(embed.title):
                    sort_url(url)
            if embed.description:
                for url in helper.get_links(embed.description):
                    sort_url(url)
            if embed.url:
                sort_url(embed.url)
            if embed.footer:
                for url in helper.get_links(embed.footer):
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
                    for url in helper.get_links(embed.provider.name):
                        sort_url(url)
                if embed.provider.url:
                    sort_url(embed.provider.url)
            if embed.fields:
                for field in embed.fields:
                    if field.name:
                        for url in helper.get_links(field.name):
                            sort_url(url)
                    if field.value:
                        for url in helper.get_links(field.value):
                            sort_url(url)

        content_urls = []

        # Sort Content URLs

        for url in helper.get_links(message.content):
            content_urls.append(url)
            sort_url(url)

        handled_urls = []

        # Gather Hashes

        async def get_cached_hash(url):
            url_to_hash = safe_read(COG, guild, "url_to_hash")

            if not (url_to_hash := url_to_hash.get()):
                return
            if not isinstance(url_to_hash, URLToHashCache):
                return

            return url_to_hash.get(url)

        total_thread_time_start = time()

        threads = []
        results = {}

        def generate_hash(*, url):
            hash_generation_time_start = time()

            loop = asyncio.new_event_loop()

            results[url] = loop.run_until_complete(helper.hash_external_link(url))
            timings[f"HASH_{url}"] = time() - hash_generation_time_start

        for url in image_urls:
            if not (hash := await get_cached_hash(url)):
                threads.append(
                    threading.Thread(target=generate_hash, kwargs={"url": url})
                )

                dprint(
                    f"No cache found. Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
                )
                continue

            dprint(
                f"Cache found! Hash: [f{hash}] Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
            )

            results[url] = hash
        for url in video_urls:
            if not (hash := await get_cached_hash(url)):
                threads.append(
                    threading.Thread(target=generate_hash, kwargs={"url": url})
                )

                dprint(
                    f"No cache found. Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
                )
                continue

            dprint(
                f"Cache found! Hash: [f{hash}] Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
            )

            results[url] = hash
        for url in audio_urls:
            if not (hash := await get_cached_hash(url)):
                threads.append(
                    threading.Thread(target=generate_hash, kwargs={"url": url})
                )

                dprint(
                    f"No cache found. Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
                )
                continue

            dprint(
                f"Cache found! Hash: [f{hash}] Guild: [{guild}] Message: [{message.id}] URL: [{url}]"
            )

            results[url] = hash

        for thread in threads:
            thread.start()

        # Wait For Threads To Finish

        while True:
            threads_still_alive = False

            for thread in threads:
                if thread.is_alive():
                    threads_still_alive = True

            if not threads_still_alive:
                dprint(f"Threads completed! Guild: [{guild}] Message: [{message.id}]")
                break

            dprint(f"Waiting for threads. Guild: [{guild}] Message: [{message.id}]")

            await asyncio.sleep(1)

        timings["thread_total"] = time() - total_thread_time_start

        # Cache Hashes

        async with safe_edit(COG, guild, "url_to_hash") as url_to_hash_storage_object:
            if not (url_to_hash := url_to_hash_storage_object.get()):
                url_to_hash = URLToHashCache()
            if not isinstance(url_to_hash, URLToHashCache):
                url_to_hash = URLToHashCache()

            for url in results:
                if not url_to_hash.get(url):
                    url_to_hash.set(url, results[url])

            url_to_hash_storage_object.set(url_to_hash)

            sdprint(json.dumps(url_to_hash.url_to_hash, indent=4))

        # Send All Reflections

        send_reflection_total_start = time()

        primary_reflection = None

        # Process Images

        compact_image_reflection_parts = []

        for url in image_urls:
            dprint(
                f"Processing image URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            if url in handled_urls:
                continue

            hash = results[url]

            compact_image_reflection_parts.append(
                CompactImageReflectionPart(url, hash, message)
            )

            handled_urls.append(url)

        if compact_image_reflection_parts:
            dprint(
                f"Sending compact reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            primary_reflection = await self.send_compact_image_reflection(
                reflect_channel=reflect_channel,
                message=message,
                compact_image_reflection_parts=compact_image_reflection_parts,
            )

        # Process Videos

        for url in video_urls:
            dprint(
                f"Processing video URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            reflection_send_start = time()

            if url in handled_urls:
                continue

            hash = await helper.hash_external_link(url)

            if not primary_reflection:
                dprint(
                    f"Sending primary video reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_primary_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    hash=hash,
                    url=url,
                )
                primary_reflection = reflect_message
                await reflect_message.reply(f"{url}")
            else:
                dprint(
                    f"Sending additional video reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_additional_reflection(
                    primary_reflection=primary_reflection,
                    message=message,
                    hash=hash,
                    url=url,
                )
                await reflect_message.reply(f"{url}")

            handled_urls.append(url)

            timings[f"REFLECT_{url}"] = time() - reflection_send_start

        # Process Audio

        for url in audio_urls:
            dprint(
                f"Processing audio URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            reflection_send_start = time()

            if url in handled_urls:
                continue

            hash = await helper.hash_external_link(url)

            if not primary_reflection:
                dprint(
                    f"Sending primary audio reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_primary_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    hash=hash,
                    url=url,
                )
                primary_reflection = reflect_message
                await reflect_message.reply(f"{url}")
            else:
                dprint(
                    f"Sending additional audio reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_additional_reflection(
                    primary_reflection=primary_reflection,
                    message=message,
                    hash=hash,
                    url=url,
                )
                await reflect_message.reply(f"{url}")

            handled_urls.append(url)

            timings[f"REFLECT_{url}"] = time() - reflection_send_start

        # Process Content URLs

        for url in content_urls:
            dprint(
                f"Processing content URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            reflection_send_start = time()

            if url in handled_urls:
                continue

            if not primary_reflection:
                dprint(
                    f"Sending primary content reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_primary_reflection(
                    reflect_channel=reflect_channel, message=message, hash=None, url=url
                )
                primary_reflection = reflect_message
                await reflect_message.reply(f"{url}")
            else:
                dprint(
                    f"Sending additional content reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                reflect_message = await self.send_additional_reflection(
                    primary_reflection=primary_reflection,
                    message=message,
                    hash=None,
                    url=url,
                )
                await reflect_message.reply(f"{url}")

            handled_urls.append(url)

            timings[f"REFLECT_{url}"] = time() - reflection_send_start

        timings["send_reflection_total"] = time() - send_reflection_total_start

        dprint(f"Image URLs: {json.dumps(image_urls, indent=4)}")
        dprint(f"Video URLs: {json.dumps(video_urls, indent=4)}")
        dprint(f"Audio URLs: {json.dumps(audio_urls, indent=4)}")
        dprint(f"Standard URLs: {json.dumps(standard_urls, indent=4)}")
        dprint(f"Handled URLs: {json.dumps(handled_urls, indent=4)}")

        timings["total"] = time() - total_time_start

        dprint(
            f"Reflection timings for {guild} message {message.id}: {json.dumps(timings, indent=4)}"
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="enable", description="Enables media reflecting."
    )
    @discord.app_commands.describe(reflect_channel="Where to send media reflections.")
    async def reflect_enable(
        self, interaction: discord.Interaction, reflect_channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                settings = ReflectCogSettingsObject()
            if not isinstance(settings, ReflectCogSettingsObject):
                settings = ReflectCogSettingsObject()
            if settings.get("enabled"):
                await interaction.followup.send("Reflect is already enabled!")
                return

            settings.set("enabled", True)
            settings.set("reflect_channel_id", reflect_channel.id)
            settings_storage_object.set(settings)

        await interaction.followup.send("Reflect enabled!")

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="disable", description="Disable media reflecting."
    )
    async def reflect_disable(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return

            settings.set("enabled", False)
            settings_storage_object.set(settings)

        await interaction.followup.send("Reflect disabled!")

    reflect_ignore_group = discord.app_commands.Group(
        name="ignore", description="Exclude channels and roles from reflection."
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @reflect_ignore_group.command(
        name="list", description="List ignored channels and roles."
    )
    async def reflect_ignore_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return

            ignored_channels = ", ".join(
                [
                    f"<#{channel_id}>"
                    for channel_id in settings.get("ignored_channel_ids")
                ]
            )
            ignored_roles = ", ".join(
                [f"<@&{role_id}>" for role_id in settings.get("ignored_role_ids")]
            )

            await interaction.followup.send(
                f"Ignored Channels: {ignored_channels}\nIgnored Roles: {ignored_roles}",
                ephemeral=True,
            )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @reflect_ignore_group.command(
        name="channel", description="Exclude a channel from reflection."
    )
    @discord.app_commands.describe(channel="Channel to exclude from reflection.")
    async def reflect_ignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if channel.id in (
                ignored_channel_ids := settings.get("ignored_channel_ids")
            ):
                await interaction.followup.send(
                    f"{channel.mention} is already ignored!"
                )
                return

            ignored_channel_ids.append(channel.id)
            settings.set("ignored_channel_ids", ignored_channel_ids)
            settings_storage_object.set(settings)

        await interaction.followup.send(f"Now ignoring {channel.mention}!")

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @reflect_ignore_group.command(
        name="role", description="Exclude a role from reflection."
    )
    @discord.app_commands.describe(role="Role to exclude from reflection.")
    async def reflect_ignore_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if role.id in (ignored_role_ids := settings.get("ignored_role_ids")):
                await interaction.followup.send(f"{role.mention} is already ignored!")
                return

            ignored_role_ids.append(role.id)
            settings.set("ignored_role_ids", ignored_role_ids)
            settings_storage_object.set(settings)

        await interaction.followup.send(f"Now ignoring {role.mention}!")

    reflect_unignore_group = discord.app_commands.Group(
        name="unignore",
        description="Stop excluding channels and roles from reflection.",
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @reflect_unignore_group.command(
        name="channel", description="Stop excluding a channel from reflection."
    )
    @discord.app_commands.describe(channel="Channel to stop excluding from reflection.")
    async def reflect_unignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not channel.id in (
                ignored_channel_ids := settings.get("ignored_channel_ids")
            ):
                await interaction.followup.send(f"{channel.mention} is not ignored!")
                return

            ignored_channel_ids.remove(channel.id)
            settings.set("ignored_channel_ids", ignored_channel_ids)
            settings_storage_object.set(settings)

        await interaction.followup.send(f"No longer ignoring {channel.mention}!")

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @reflect_unignore_group.command(
        name="role", description="Stop excluding a role from reflection."
    )
    @discord.app_commands.describe(role="Role to stop excluding from reflection.")
    async def reflect_unignore_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(COG, guild, "settings") as settings_storage_object:
            if not (settings := settings_storage_object.get()):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not settings.get("enabled"):
                await interaction.followup.send("Reflect is not enabled!")
                return
            if not role.id in (ignored_role_ids := settings.get("ignored_role_ids")):
                await interaction.followup.send(f"{role.mention} is not ignored!")
                return

            ignored_role_ids.remove(role.id)
            settings.set("ignored_role_ids", ignored_role_ids)
            settings_storage_object.set(settings)

        await interaction.followup.send(f"No longer ignoring {role.mention}!")


async def setup(bot: Mammoth):
    await bot.add_cog(ReflectCog(bot))
