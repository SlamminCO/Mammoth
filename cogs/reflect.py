from time import time
from discord.ext import commands
from main import Mammoth
from utils.storage import safe_read, safe_edit
from discord.ui import Button, View, Select
from lib.ui import HashBlacklistButton
from utils.hash import get_media_sorted_link_hashes_from_message, LinkHash
import logging
import discord
import json


COG = __name__
DEFAULT_REFLECT_COG_SETTINGS = {
    "enabled": False,
    "ignored_channel_ids": [],
    "ignored_role_ids": [],
    "ignored_member_ids": [],
    "reflect_channel_id": None,
}

log = logging.getLogger(COG)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


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
    def __init__(self, message: discord.Message, link_hash: LinkHash):
        super().__init__(timeout=None)

        self.message = message
        self.link_hash = link_hash
        self.appended_messages = []

        self.dismiss_button = ReflectionDismissButton(
            self.message, self.appended_messages
        )
        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.delete_button = ReflectionDeleteButton(self.message, self.jump_button)
        self.blacklist_button = HashBlacklistButton(self.message, self.link_hash)

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)

        if self.link_hash.md5 or self.link_hash.image_hash:
            self.add_item(self.blacklist_button)

        self.add_item(self.jump_button)


class CompactImageReflectionPart:
    def __init__(self, link_hash: LinkHash, message: discord.Message):
        self.link_hash = link_hash
        self.message = message
        self.embed = discord.Embed()

        self.embed.add_field(name="User", value=self.message.author.mention)
        self.embed.add_field(name="Channel", value=self.message.channel.mention)
        self.embed.add_field(name="URL", value=self.link_hash.link, inline=False)
        if self.link_hash.md5:
            self.embed.add_field(name="MD5", value=self.link_hash.md5, inline=False)
        if self.link_hash.image_hash:
            self.embed.add_field(name="Image Hash", value=self.link_hash.image_hash)

        if len(message.content) != 0:
            self.embed.add_field(name="Content", value=message.content, inline=False)

        self.embed.set_image(url=self.link_hash.link)


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
                self.message, self.value_to_part["0"].link_hash
            )

            async def media_select_callback(interaction: discord.Interaction):
                self.blacklist_button.link_hash = self.value_to_part[
                    self.media_select.values[0]
                ].link_hash

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
                self.message, compact_reflection_parts[0].link_hash
            )

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)
        self.add_item(self.blacklist_button)
        self.add_item(self.jump_button)


@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
class ReflectCog(commands.GroupCog, name="reflect"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        log.info(f"Loaded")

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

    async def send_parent_reflection(
        self,
        *,
        reflect_channel: discord.TextChannel,
        message: discord.Message,
        link_hash: LinkHash,
        content: str = None,
    ):
        embed = discord.Embed()

        embed.add_field(name="User", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="URL", value=link_hash.link, inline=False)

        if link_hash.md5:
            embed.add_field(name="MD5", value=link_hash.md5, inline=False)
        if link_hash.image_hash:
            embed.add_field(name="Image Hash", value=link_hash.image_hash, inline=False)
        if content:
            embed.add_field(name="Content", value=message.content, inline=False)

        parent_reflection_view = ReflectionView(message, link_hash)
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
        link_hash: LinkHash,
        content: str = None,
    ):
        embed = discord.Embed(title="Additional Media")

        embed.add_field(name="URL", value=link_hash.link, inline=False)

        if link_hash.md5:
            embed.add_field(name="MD5", value=link_hash.md5, inline=False)
        if link_hash.image_hash:
            embed.add_field(name="Image Hash", value=link_hash.image_hash, inline=False)

        additional_reflection_view = ReflectionView(message, link_hash)
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

        if not (settings_data := safe_read(COG, guild, "settings")):
            return
        if not settings_data.get("enabled", DEFAULT_REFLECT_COG_SETTINGS["enabled"]):
            return
        if channel.id in settings_data.get("ignored_channel_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_channel_ids"]):
            return
        if channel.id == (reflect_channel_id := settings_data.get("reflect_channel_id", DEFAULT_REFLECT_COG_SETTINGS["reflect_channel_id"])):
            return
        if message.author.id in settings_data.get("ignored_member_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_member_ids"]):
            return
        for role in message.author.roles:
            if role.id in settings_data.get("ignored_role_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_role_ids"]):
                return
        if not (reflect_channel := guild.get_channel(reflect_channel_id)):
            return

        time_start = time()
        media_sorted_link_hashes = await get_media_sorted_link_hashes_from_message(
            message
        )
        time_total = time() - time_start
        log.debug(
            f"Hashing took {time_total} second{'' if time_total == 1 else 's'} for Guild: [{guild}] Message: [{message.id}]"
        )

        handled_urls = []
        parent_reflection = None
        compact_image_reflection_parts = []

        parent_reflection = await self.send_compact_image_reflections(
            message,
            reflect_channel,
            media_sorted_link_hashes.image_link_hashes,
            handled_urls,
            compact_image_reflection_parts,
            parent_reflection,
        )
        parent_reflection = await self.send_non_embeddable_media_reflections(
            message=message,
            reflect_channel=reflect_channel,
            link_hashes=media_sorted_link_hashes.video_link_hashes
            + media_sorted_link_hashes.audio_link_hashes,
            handled_urls=handled_urls,
            parent_reflection=parent_reflection,
        )
        await self.send_non_media_url_reflections(
            message,
            reflect_channel,
            media_sorted_link_hashes.other_link_hashes,
            handled_urls,
            parent_reflection,
        )

    async def send_non_media_url_reflections(
        self,
        message: discord.Message,
        reflect_channel: discord.TextChannel,
        link_hashes: list[LinkHash],
        handled_urls: list[str],
        parent_reflection: discord.Message,
    ):
        for link_hash in link_hashes:
            if link_hash.link in handled_urls:
                continue

            if not parent_reflection:
                (
                    parent_reflection,
                    parent_reflection_view,
                ) = await self.send_parent_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    link_hash=link_hash,
                )

                parent_reflection_view.appended_messages.append(
                    await parent_reflection.reply(f"{link_hash.link}")
                )
            else:
                (
                    additional_reflection_message,
                    additional_reflection_view,
                ) = await self.send_additional_reflection(
                    parent_reflection=parent_reflection,
                    message=message,
                    link_hash=link_hash,
                )

                additional_reflection_view.appended_messages.append(
                    await additional_reflection_message.reply(f"{link_hash.link}")
                )

            handled_urls.append(link_hash.link)

    async def send_non_embeddable_media_reflections(
        self,
        *,
        message: discord.Message,
        reflect_channel: discord.TextChannel,
        link_hashes: list[LinkHash],
        handled_urls: list[str],
        parent_reflection: discord.Message,
    ):
        for link_hash in link_hashes:
            if link_hash.link in handled_urls:
                continue

            if not parent_reflection:
                parent_reflection, reflection_view = await self.send_parent_reflection(
                    reflect_channel=reflect_channel,
                    message=message,
                    link_hash=link_hash,
                )

                reflection_view.appended_messages.append(
                    await parent_reflection.reply(f"{link_hash.link}")
                )
            else:
                (
                    additional_reflection_message,
                    additional_reflection_view,
                ) = await self.send_additional_reflection(
                    parent_reflection=parent_reflection,
                    message=message,
                    link_hash=link_hash,
                )

                additional_reflection_view.appended_messages.append(
                    await additional_reflection_message.reply(f"{link_hash.link}")
                )

            handled_urls.append(link_hash.link)

        return parent_reflection

    async def send_compact_image_reflections(
        self,
        message: discord.Message,
        reflect_channel: discord.TextChannel,
        link_hashes: list[LinkHash],
        handled_urls: list[str],
        compact_image_reflection_parts: list[CompactImageReflectionPart],
        parent_reflection: discord.Message,
    ):
        for link_hash in link_hashes:
            if link_hash.link in handled_urls:
                continue

            compact_image_reflection_parts.append(
                CompactImageReflectionPart(link_hash, message)
            )

            handled_urls.append(link_hash.link)

        if compact_image_reflection_parts:
            parent_reflection = await self.send_compact_image_reflection(
                reflect_channel=reflect_channel,
                message=message,
                compact_image_reflection_parts=compact_image_reflection_parts,
            )

        return parent_reflection

    @discord.app_commands.command(
        name="enable", description="Enables media reflecting."
    )
    @discord.app_commands.describe(reflect_channel="Where to send media reflections.")
    async def reflect_enable(
        self, interaction: discord.Interaction, reflect_channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                settings = ReflectCogSettingsObject()
            if not isinstance(settings, ReflectCogSettingsObject):
                settings = ReflectCogSettingsObject()
            if settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is already enabled!", ephemeral=True
                )
                return

            settings.set("enabled", True)
            settings.set("reflect_channel_id", reflect_channel.id)
            storage_object.set(settings)

        await interaction.followup.send("Reflect enabled!", ephemeral=True)

    @discord.app_commands.command(
        name="disable", description="Disable media reflecting."
    )
    async def reflect_disable(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return

            settings.set("enabled", False)
            storage_object.set(settings)

        await interaction.followup.send("Reflect disabled!", ephemeral=True)

    @discord.app_commands.command(
        name="channel", description="Change where to send media reflections."
    )
    @discord.app_commands.describe(reflect_channel="Where to send media reflections.")
    async def reflect_channel(
        self, interaction: discord.Interaction, reflect_channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return

            settings.set("reflect_channel_id", reflect_channel.id)
            storage_object.set(settings)

        await interaction.followup.send(
            f"Reflect channel changed to {reflect_channel.mention}!", ephemeral=True
        )

    reflect_ignore_group = discord.app_commands.Group(
        name="ignore",
        description="Exclude members, channels and roles from reflection.",
    )

    @reflect_ignore_group.command(
        name="list", description="List ignored members, channels and roles."
    )
    async def reflect_ignore_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        if not (settings_data := safe_read(COG, guild, "settings")):
            await interaction.response.send_message(
                "Reflect is not enabled!", ephemeral=True
            )
            return
        if not settings_data.get("enabled", DEFAULT_REFLECT_COG_SETTINGS["enabled"]):
            await interaction.response.send_message(
                "Reflect is not enabled!", ephemeral=True
            )
            return

        ignored_channels = ", ".join(
            [f"<#{channel_id}>" for channel_id in settings_data.get("ignored_channel_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_channel_ids"])]
        )
        ignored_roles = ", ".join(
            [f"<@&{role_id}>" for role_id in settings_data.get("ignored_role_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_role_ids"])]
        )
        ignored_members = ", ".join(
            [f"<@{member_id}>" for member_id in settings_data.get("ignored_member_ids", DEFAULT_REFLECT_COG_SETTINGS["ignored_member_ids"])]
        )

        await interaction.response.send_message(
            f"Ignored Channels: {ignored_channels}\nIgnored Roles: {ignored_roles}\nIgnored Members: {ignored_members}",
            ephemeral=True,
        )

    @reflect_ignore_group.command(
        name="member", description="Exclude a member from reflection."
    )
    @discord.app_commands.describe(member="Member to exclude from reflection.")
    async def reflect_ignore_member(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if member.id in (ignored_member_ids := settings.get("ignored_member_ids")):
                await interaction.followup.send(
                    f"{member.mention} is already ignored!", ephemeral=True
                )
                return

            ignored_member_ids.append(member.id)
            settings.set("ignored_member_ids", ignored_member_ids)
            storage_object.set(settings)

        await interaction.followup.send(
            f"Now ignoring {member.mention}!", ephemeral=True
        )

    @reflect_ignore_group.command(
        name="channel", description="Exclude a channel from reflection."
    )
    @discord.app_commands.describe(channel="Channel to exclude from reflection.")
    async def reflect_ignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if channel.id in (
                ignored_channel_ids := settings.get("ignored_channel_ids")
            ):
                await interaction.followup.send(
                    f"{channel.mention} is already ignored!", ephemeral=True
                )
                return

            ignored_channel_ids.append(channel.id)
            settings.set("ignored_channel_ids", ignored_channel_ids)
            storage_object.set(settings)

        await interaction.followup.send(
            f"Now ignoring {channel.mention}!", ephemeral=True
        )

    @reflect_ignore_group.command(
        name="role", description="Exclude a role from reflection."
    )
    @discord.app_commands.describe(role="Role to exclude from reflection.")
    async def reflect_ignore_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if role.id in (ignored_role_ids := settings.get("ignored_role_ids")):
                await interaction.followup.send(
                    f"{role.mention} is already ignored!", ephemeral=True
                )
                return

            ignored_role_ids.append(role.id)
            settings.set("ignored_role_ids", ignored_role_ids)
            storage_object.set(settings)

        await interaction.followup.send(f"Now ignoring {role.mention}!", ephemeral=True)

    reflect_unignore_group = discord.app_commands.Group(
        name="unignore",
        description="Stop excluding members, channels and roles from reflection.",
    )

    @reflect_unignore_group.command(
        name="member", description="Stop excluding a member from reflection."
    )
    @discord.app_commands.describe(member="Member to stop excluding from reflection.")
    async def reflect_unignore_member(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not member.id in (
                ignored_member_ids := settings.get("ignored_member_ids")
            ):
                await interaction.followup.send(
                    f"{member.mention} is not ignored!", ephemeral=True
                )
                return

            ignored_member_ids.remove(member.id)
            settings.set("ignored_member_ids", ignored_member_ids)
            storage_object.set(settings)

        await interaction.followup.send(
            f"No longer ignoring {member.mention}!", ephemeral=True
        )

    @reflect_unignore_group.command(
        name="channel", description="Stop excluding a channel from reflection."
    )
    @discord.app_commands.describe(channel="Channel to stop excluding from reflection.")
    async def reflect_unignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not channel.id in (
                ignored_channel_ids := settings.get("ignored_channel_ids")
            ):
                await interaction.followup.send(
                    f"{channel.mention} is not ignored!", ephemeral=True
                )
                return

            ignored_channel_ids.remove(channel.id)
            settings.set("ignored_channel_ids", ignored_channel_ids)
            storage_object.set(settings)

        await interaction.followup.send(
            f"No longer ignoring {channel.mention}!", ephemeral=True
        )

    @reflect_unignore_group.command(
        name="role", description="Stop excluding a role from reflection."
    )
    @discord.app_commands.describe(role="Role to stop excluding from reflection.")
    async def reflect_unignore_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as storage_object:
            if not (settings := storage_object.get()):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not isinstance(settings, ReflectCogSettingsObject):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not settings.get("enabled"):
                await interaction.followup.send(
                    "Reflect is not enabled!", ephemeral=True
                )
                return
            if not role.id in (ignored_role_ids := settings.get("ignored_role_ids")):
                await interaction.followup.send(
                    f"{role.mention} is not ignored!", ephemeral=True
                )
                return

            ignored_role_ids.remove(role.id)
            settings.set("ignored_role_ids", ignored_role_ids)
            storage_object.set(settings)

        await interaction.followup.send(
            f"No longer ignoring {role.mention}!", ephemeral=True
        )


async def setup(bot: Mammoth):
    await bot.add_cog(ReflectCog(bot))
