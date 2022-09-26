from helper import DPrinter
from discord.ext import commands
from main import Mammoth
from storage import safe_edit, safe_read
from discord.ui import Button, View, Select
from shared_classes import HashBlacklistButton
import discord
import helper
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


class ReflectionDismissButton(Button):
    def __init__(
        self, message: discord.Message, appended_messages: list[discord.Message]
    ):
        super().__init__(label="Close", style=discord.ButtonStyle.blurple)

        self.message = message
        self.appended_messages = appended_messages

    async def callback(self, interaction: discord.Interaction):
        if not self.message.channel.permissions_for(interaction.user).manage_messages:
            return await interaction.response.send_message(
                f"You do not have permission to manage messages in {self.message.channel.mention}!"
            )

        await interaction.response.edit_message(
            content="Reflection dismissed!", embed=None, view=None
        )
        await interaction.message.delete(delay=5)

        for additional_alert in self.appended_messages:
            try:
                await additional_alert.delete()
            except:
                pass


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
        self.appended_messages = []

        self.dismiss_button = ReflectionDismissButton(self.message, self.appended_messages)
        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.delete_button = ReflectionDeleteButton(self.message, self.jump_button)
        self.blacklist_button = HashBlacklistButton(self.message, self.hash)

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)

        if hash:
            self.add_item(self.blacklist_button)

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

        self.dismiss_button = ReflectionDismissButton(self.message, [])
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

            self.blacklist_button = HashBlacklistButton(
                self.message, self.value_to_part["0"].hash
            )

            async def media_select_callback(interaction: discord.Interaction):
                self.blacklist_button.hash = self.value_to_part[
                    self.media_select.values[0]
                ].hash

                self.blacklist_button.update_mode()

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
        else:
            self.blacklist_button = HashBlacklistButton(
                self.message, compact_reflection_parts[0].hash
            )

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)
        self.add_item(self.blacklist_button)
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
        compact_image_reflection_view = CompactImageReflectionView(
            message, compact_image_reflection_parts
        )
        compact_image_reflection = await reflect_channel.send(
            embed=compact_image_reflection_parts[0].embed,
            view=compact_image_reflection_view,
        )
        return compact_image_reflection, compact_image_reflection_view

    async def send_parent_reflection(
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

        parent_reflection_view = ReflectionView(message, hash)
        parent_reflect_message = await reflect_channel.send(
            content=content,
            embed=embed,
            view=parent_reflection_view,
        )

        return parent_reflect_message, parent_reflection_view

    async def send_additional_reflection(
        self,
        *,
        parent_reflection: discord.Message,
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

        additional_reflection_view = ReflectionView(message, hash)
        additional_reflection = await parent_reflection.reply(
            content=content,
            embed=embed,
            view=additional_reflection_view,
        )

        return additional_reflection, additional_reflection_view

    @commands.Cog.listener(name="on_message")
    async def reflect_on_message(self, message: discord.Message):
        channel = message.channel

        if not (guild := message.guild):
            return
        if not isinstance(message.author, discord.Member):
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

        results, urls = await helper.get_media_hashes_from_message(message)
        image_urls, video_urls, audio_urls, standard_urls, content_urls = urls
        handled_urls = []
        parent_reflection = None
        compact_image_reflection_parts = []

        parent_reflection = await self.send_compact_image_reflections(message, guild, reflect_channel, results, image_urls, handled_urls, compact_image_reflection_parts, parent_reflection)
        parent_reflection = await self.send_video_reflections(message, guild, reflect_channel, results, video_urls, handled_urls, parent_reflection)
        parent_reflection = await self.send_audio_reflections(message, guild, reflect_channel, results, audio_urls, handled_urls, parent_reflection)
        await self.send_content_url_reflections(message, guild, reflect_channel, content_urls, handled_urls, parent_reflection)

        dprint(f"Image URLs: {json.dumps(image_urls, indent=4)}")
        dprint(f"Video URLs: {json.dumps(video_urls, indent=4)}")
        dprint(f"Audio URLs: {json.dumps(audio_urls, indent=4)}")
        dprint(f"Standard URLs: {json.dumps(standard_urls, indent=4)}")
        dprint(f"Handled URLs: {json.dumps(handled_urls, indent=4)}")

    async def send_content_url_reflections(self, message, guild, reflect_channel, content_urls, handled_urls, parent_reflection):
        for url in content_urls:
            dprint(
                f"Processing content URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            if url in handled_urls:
                continue

            if not parent_reflection:
                dprint(
                    f"Sending parent content reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                (
                    parent_reflection,
                    parent_reflection_view,
                ) = await self.send_parent_reflection(
                    reflect_channel=reflect_channel, message=message, hash=None, url=url
                )

                parent_reflection_view.appended_messages.append(
                    await parent_reflection.reply(f"{url}")
                )
            else:
                dprint(
                    f"Sending additional content reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                (
                    additional_reflection_message,
                    additional_reflection_view,
                ) = await self.send_additional_reflection(
                    parent_reflection=parent_reflection,
                    message=message,
                    hash=None,
                    url=url,
                )

                additional_reflection_view.appended_messages.append(
                    await additional_reflection_message.reply(f"{url}")
                )

            handled_urls.append(url)

    async def send_audio_reflections(self, message, guild, reflect_channel, results, audio_urls, handled_urls, parent_reflection):
        for url in audio_urls:
            dprint(
                f"Processing audio URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            if url in handled_urls:
                continue

            hash = results[url]

            if not parent_reflection:
                dprint(
                    f"Sending parent audio reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                parent_reflection, reflection_view = await self.send_parent_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    hash=hash,
                    url=url,
                )

                reflection_view.appended_messages.append(
                    await parent_reflection.reply(f"{url}")
                )
            else:
                dprint(
                    f"Sending additional audio reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                (
                    additional_reflection_message,
                    additional_reflection_view,
                ) = await self.send_additional_reflection(
                    parent_reflection=parent_reflection,
                    message=message,
                    hash=hash,
                    url=url,
                )

                additional_reflection_view.appended_messages.append(
                    await additional_reflection_message.reply(f"{url}")
                )

            handled_urls.append(url)
        return parent_reflection

    async def send_video_reflections(self, message, guild, reflect_channel, results, video_urls, handled_urls, parent_reflection):
        for url in video_urls:
            dprint(
                f"Processing video URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
            )

            if url in handled_urls:
                continue

            hash = results[url]

            if not parent_reflection:
                dprint(
                    f"Sending parent video reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                parent_reflection, reflection_view = await self.send_parent_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    hash=hash,
                    url=url,
                )

                reflection_view.appended_messages.append(
                    await parent_reflection.reply(f"{url}")
                )
            else:
                dprint(
                    f"Sending additional video reflection URL: [{url}] Guild: [{guild}] Message: [{message.id}]"
                )

                (
                    additional_reflection_message,
                    additional_reflection_view,
                ) = await self.send_additional_reflection(
                    parent_reflection=parent_reflection,
                    message=message,
                    hash=hash,
                    url=url,
                )

                additional_reflection_view.appended_messages.append(
                    await additional_reflection_message.reply(f"{url}")
                )

            handled_urls.append(url)
        return parent_reflection

    async def send_compact_image_reflections(self, message, guild, reflect_channel, results, image_urls, handled_urls, compact_image_reflection_parts, parent_reflection):
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

            parent_reflection = await self.send_compact_image_reflection(
                reflect_channel=reflect_channel,
                message=message,
                compact_image_reflection_parts=compact_image_reflection_parts,
            )
            
        return parent_reflection

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
