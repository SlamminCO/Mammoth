from discord.ext import commands
from main import Mammoth
from utils.storage import safe_read, safe_edit, update_dict_defaults
from discord.ui import Button, View, Select
from lib.ui import HashBlacklistButton
from utils.hash import LinkHash, get_media_sorted_link_hashes_from_message
from utils.link import get_media_sorted_links_from_message
import traceback
import discord
import json
import asyncio
import logging


COG = __name__
DEFAULT_ALERTS_COG_SETTINGS = {
    "enabled": False,
    "ignored_channel_ids": [],
    "trusted_role_ids": [],
    "trusted_member_ids": [],
    "alerts_channel_id": None,
    "mod_role_id": [],
    "alert_emoji_str": None,
    "alert_threshold": None,
}

log = logging.getLogger(COG)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


class CompactImageAlertPart:
    def __init__(
        self,
        link_hash: LinkHash,
        message: discord.Message,
        flaggers: list[discord.User],
    ):
        self.link_hash = link_hash
        self.message = message
        self.embed = discord.Embed()

        self.embed.add_field(name="User", value=self.message.author.mention)
        self.embed.add_field(name="Channel", value=self.message.channel.mention)

        if flaggers:
            self.embed.add_field(
                name="Flagged By",
                value="".join([f"{user.mention} " for user in flaggers]),
                inline=False,
            )

        self.embed.add_field(name="URL", value=self.link_hash.link, inline=False)

        if link_hash.md5:
            self.embed.add_field(name="MD5", value=link_hash.md5, inline=False)
        if link_hash.image_hash:
            self.embed.add_field(
                name="Image Hash", value=link_hash.image_hash, inline=False
            )

        if len(message.content) != 0:
            self.embed.add_field(name="Content", value=message.content, inline=False)

        self.embed.set_image(url=self.link_hash.link)


class AlertDeleteButton(Button):
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


class AlertDismissButton(Button):
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
            content="Alert dismissed!", embed=None, view=None
        )
        await interaction.message.delete(delay=5)

        for additional_alert in self.appended_messages:
            try:
                await additional_alert.delete()
            except:
                pass


class AlertView(View):
    def __init__(self, message: discord.Message, link_hash: LinkHash = None):
        super().__init__(timeout=None)

        self.appended_messages = []
        self.message = message
        self.link_hash = link_hash

        self.dismiss_button = AlertDismissButton(self.message, self.appended_messages)
        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.delete_button = AlertDeleteButton(self.message, self.jump_button)
        self.blacklist_button = HashBlacklistButton(self.message, self.link_hash)

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)

        if self.link_hash.md5 or self.link_hash.image_hash:
            self.add_item(self.blacklist_button)

        self.add_item(self.jump_button)


class CompactImageSelect(Select):
    def __init__(
        self,
        compact_image_alert_parts: list[CompactImageAlertPart],
        blacklist_button: HashBlacklistButton,
    ):
        super().__init__(placeholder="Select an image to view.")

        self.value_to_part = {}
        self.blacklist_button = blacklist_button

        for i, part in enumerate(compact_image_alert_parts):
            new_select_option = discord.SelectOption(
                label=f"Image {i + 1}",
                value=f"{i}",
                default=True if i == 0 else False,
            )
            self.append_option(new_select_option)
            self.value_to_part[f"{i}"] = part
            if i == 0:
                self.blacklist_button.link_hash = part.link_hash

    async def callback(self, interaction: discord.Interaction):
        self.blacklist_button.link_hash = self.value_to_part[self.values[0]].link_hash

        self.blacklist_button.update_mode()

        for option in self.options:
            option.default = True if option.value == self.values[0] else False

        await interaction.response.edit_message(
            embed=self.value_to_part[self.values[0]].embed,
            view=self.view,
        )


class CompactImageAlertView(View):
    def __init__(
        self,
        message: discord.Message,
        compact_image_alert_parts: list[CompactImageAlertPart],
    ):
        super().__init__(timeout=None)

        self.message = message
        self.parts = compact_image_alert_parts
        self.value_to_part = {}

        self.jump_button = Button(
            label="Jump", style=discord.ButtonStyle.link, url=message.jump_url
        )
        self.dismiss_button = AlertDismissButton(self.message, [])
        self.delete_button = AlertDeleteButton(self.message, self.jump_button)
        self.blacklist_button = HashBlacklistButton(
            self.message, compact_image_alert_parts[0].link_hash
        )

        if len(compact_image_alert_parts) > 1:
            self.media_select = CompactImageSelect(
                compact_image_alert_parts, self.blacklist_button
            )
            self.add_item(self.media_select)

        self.add_item(self.dismiss_button)
        self.add_item(self.delete_button)
        self.add_item(self.blacklist_button)
        self.add_item(self.jump_button)


class SubmitButton(Button):
    def __init__(
        self,
        message: discord.Message,
        reporter: discord.Member,
        alerts_channel: discord.TextChannel,
        flaggers: list[discord.Member],
        alert_threshold: int,
        mod_role: discord.Role,
    ):
        super().__init__(label="Submit", style=discord.ButtonStyle.green)

        self.message = message
        self.reporter = reporter
        self.alerts_channel = alerts_channel
        self.flaggers = flaggers
        self.alert_threshold = alert_threshold
        self.mod_role = mod_role

        self.parent_alert_view = None
        self.parent_alert_message = None
        self.handled_urls = []

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.reporter.id:
            return await interaction.response.send_message(
                "This is not your report!", ephemeral=True
            )

        await interaction.message.delete()

        await interaction.response.defer(ephemeral=True, thinking=True)

        media_sorted_link_hashes = await get_media_sorted_link_hashes_from_message(
            self.message
        )

        try:
            await self.send_compact_image_alert(
                media_sorted_link_hashes.image_link_hashes
            )
            await self.send_non_embeddable_media_alerts(
                media_sorted_link_hashes.video_link_hashes
                + media_sorted_link_hashes.audio_link_hashes
            )
            await self.send_non_media_url_alerts(
                media_sorted_link_hashes.other_link_hashes
            )

            await interaction.followup.send(
                "Your report has been submitted, thank you!", ephemeral=True
            )
        except Exception:
            log.exception(traceback.format_exc())

            await interaction.followup.send(
                "There was an issue submitting your report, please try again later...",
                ephemeral=True,
            )

    async def send_non_media_url_alerts(self, link_hashes: list[LinkHash]):
        for link_hash in link_hashes:
            if link_hash.link in self.handled_urls:
                continue

            if not self.parent_alert_message:
                (
                    self.parent_alert_message,
                    alert_message_view,
                ) = await self.send_parent_alert(
                    alerts_channel=self.alerts_channel,
                    message=self.message,
                    link_hash=link_hash,
                    content=f"🚨 {self.mod_role.mention}"
                    if len(self.flaggers) >= self.alert_threshold
                    else "",
                )
                alert_message_view.appended_messages.append(
                    await self.parent_alert_message.reply(f"{link_hash.link}")
                )
            else:
                alert_message, alert_message_view = await self.send_additional_alert(
                    message=self.message, link_hash=link_hash
                )
                alert_message_view.appended_messages.append(
                    await alert_message.reply(f"{link_hash.link}")
                )

            self.handled_urls.append(link_hash.link)

    async def send_non_embeddable_media_alerts(self, link_hashes: list[LinkHash]):
        for link_hash in link_hashes:
            if link_hash.link in self.handled_urls:
                continue

            if not self.parent_alert_message:
                (
                    self.parent_alert_message,
                    alert_message_view,
                ) = await self.send_parent_alert(
                    alerts_channel=self.alerts_channel,
                    message=self.message,
                    link_hash=link_hash,
                    content=f"🚨 {self.mod_role.mention}"
                    if len(self.flaggers) >= self.alert_threshold
                    else "",
                )
                alert_message_view.appended_messages.append(
                    await self.parent_alert_message.reply(f"{link_hash.link}")
                )
            else:
                alert_message, alert_message_view = await self.send_additional_alert(
                    message=self.message, link_hash=link_hash
                )
                alert_message_view.appended_messages.append(
                    await alert_message.reply(f"{link_hash.link}")
                )

            self.handled_urls.append(link_hash.link)

    async def send_compact_image_alert(self, link_hashes: list[LinkHash]):
        compact_image_alert_parts = []

        for link_hash in link_hashes:
            if link_hash.link in self.handled_urls:
                continue

            compact_image_alert_parts.append(
                CompactImageAlertPart(link_hash, self.message, self.flaggers)
            )

            self.handled_urls.append(link_hash.link)

        if compact_image_alert_parts:
            self.parent_alert_view = CompactImageAlertView(
                self.message, compact_image_alert_parts
            )
            self.parent_alert_message = await self.alerts_channel.send(
                content=f"🚨 {self.mod_role.mention}"
                if len(self.flaggers) >= self.alert_threshold
                else "",
                embed=compact_image_alert_parts[0].embed,
                view=self.parent_alert_view,
            )

    async def send_parent_alert(
        self,
        *,
        alerts_channel: discord.TextChannel,
        message: discord.Message,
        link_hash: LinkHash,
        content: str = None,
    ):
        embed = discord.Embed()

        embed.add_field(name="User", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)

        if self.flaggers:
            embed.add_field(
                name="Flagged By",
                value="".join([f"{user.mention} " for user in self.flaggers]),
                inline=False,
            )

        embed.add_field(name="URL", value=link_hash.link, inline=False)

        if link_hash.md5:
            embed.add_field(name="MD5", value=link_hash.md5, inline=False)
        if link_hash.image_hash:
            embed.add_field(name="Image Hash", value=link_hash.image_hash, inline=False)
        if len(message.content) != 0:
            embed.add_field(name="Content", value=message.content, inline=False)

        self.parent_alert_view = AlertView(message, hash)
        alert_message = await alerts_channel.send(
            content=content,
            embed=embed,
            view=self.parent_alert_view,
        )

        return alert_message, self.parent_alert_view

    async def send_additional_alert(
        self,
        *,
        message: discord.Message,
        link_hash: LinkHash,
        content: str = None,
    ):
        embed = discord.Embed(title="Additional Media")

        if self.flaggers:
            embed.add_field(
                name="Flagged By",
                value="".join([f"{user.mention} " for user in self.flaggers]),
                inline=False,
            )

        embed.add_field(name="URL", value=link_hash.link, inline=False)

        if link_hash.md5:
            embed.add_field(name="MD5", value=link_hash.md5, inline=False)
        if link_hash.image_hash:
            embed.add_field(name="Image Hash", value=link_hash.image_hash, inline=False)

        additional_alert_view = AlertView(message, link_hash)
        additional_alert = await self.parent_alert_message.reply(
            content=content,
            embed=embed,
            view=additional_alert_view,
        )

        return additional_alert, additional_alert_view


class CancelButton(Button):
    def __init__(
        self, message: discord.Message, reporter: discord.Member, alert_emoji_str: str
    ):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red)

        self.message = message
        self.reporter = reporter
        self.alert_emoji_str = alert_emoji_str

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.reporter.id:
            return await interaction.response.send_message(
                "This is not your report!", ephemeral=True
            )

        await interaction.message.delete()

        await interaction.response.send_message("Report cancelled!", ephemeral=True)

        try:
            await self.message.remove_reaction(self.alert_emoji_str, self.reporter)
        except:
            return


class SubmitReportView(View):
    def __init__(
        self,
        message: discord.Message,
        reporter: discord.Member,
        alerts_channel: discord.TextChannel,
        alert_emoji_str: str,
        flaggers: list[discord.User],
        alert_threshold: int,
        mod_role: discord.Role,
    ):
        super().__init__(timeout=None)

        self.add_item(
            SubmitButton(
                message, reporter, alerts_channel, flaggers, alert_threshold, mod_role
            )
        )
        self.add_item(CancelButton(message, reporter, alert_emoji_str))


@discord.app_commands.guild_only()
class AlertsCog(commands.GroupCog, name="alerts"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        log.info("Loaded")

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def handle_alert_reactions(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        if payload.user_id == self.bot.user.id:
            return
        if not (guild := self.bot.get_guild(payload.guild_id)):
            return
        if not (channel := self.bot.get_channel(payload.channel_id)):
            return
        if not (message := await channel.fetch_message(payload.message_id)):
            return
        if not isinstance(message.author, discord.Member):
            return
        if not (reporter := guild.get_member(payload.user_id)):
            return

        settings_data = safe_read(COG, guild, "settings")

        if not settings_data:
            return
        if not settings_data.get("enabled", DEFAULT_ALERTS_COG_SETTINGS["enabled"]):
            return
        if str(payload.emoji) != (
            alert_emoji_str := settings_data.get(
                "alert_emoji_str", DEFAULT_ALERTS_COG_SETTINGS["alert_emoji_str"]
            )
        ):
            return
        if payload.channel_id in settings_data.get(
            "ignored_channel_ids", DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"]
        ):
            return
        if not (
            alerts_channel_id := settings_data.get(
                "alerts_channel_id", DEFAULT_ALERTS_COG_SETTINGS["alerts_channel_id"]
            )
        ):
            return
        if alerts_channel_id == payload.channel_id:
            return
        if not (alerts_channel := self.bot.get_channel(alerts_channel_id)):
            return

        for role in message.author.roles:
            if role.id in settings_data.get(
                "trusted_role_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_role_ids"]
            ):
                return

        if message.author.id in settings_data.get(
            "trusted_member_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_member_ids"]
        ):
            return
        if message.channel.id in settings_data.get(
            "ignored_channel_ids", DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"]
        ):
            return
        if not isinstance(
            (
                alert_threshold := settings_data.get(
                    "alert_threshold", DEFAULT_ALERTS_COG_SETTINGS["alert_threshold"]
                )
            ),
            int,
        ):
            return
        if not (
            mod_role_id := settings_data.get(
                "mod_role_id", DEFAULT_ALERTS_COG_SETTINGS["mod_role_id"]
            )
        ):
            return
        if not (mod_role := guild.get_role(mod_role_id)):
            return

        flaggers = []

        for reaction in [
            reaction
            for reaction in message.reactions
            if str(reaction.emoji) == alert_emoji_str
        ]:
            flaggers = [
                user async for user in reaction.users() if user != self.bot.user
            ]

        submit_report_view = SubmitReportView(
            message,
            reporter,
            alerts_channel,
            alert_emoji_str,
            flaggers,
            alert_threshold,
            mod_role,
        )
        report_prompt = await message.reply(
            f"{reporter.mention} You have initiated a report on this message.\n\nDo you believe the contents of this message violate the server rules?",
            mention_author=False,
            view=submit_report_view,
        )

        await asyncio.sleep(30)

        try:
            await report_prompt.delete()
            await message.remove_reaction(alert_emoji_str, reporter)
        except:
            pass

    @commands.Cog.listener(name="on_message")
    async def handle_alertable_messages(self, message: discord.Message):
        if not (guild := message.guild):
            return
        if not isinstance(message.author, discord.Member):
            return

        settings_data = safe_read(COG, guild, "settings")

        if not settings_data:
            return
        if not settings_data.get("enabled", DEFAULT_ALERTS_COG_SETTINGS["enabled"]):
            return
        if not (
            alerts_channel_id := settings_data.get(
                "alerts_channel_id", DEFAULT_ALERTS_COG_SETTINGS["alerts_channel_id"]
            )
        ):
            return
        if message.channel.id == alerts_channel_id:
            return
        if not (
            alert_emoji_str := settings_data.get(
                "alert_emoji_str", DEFAULT_ALERTS_COG_SETTINGS["alert_emoji_str"]
            )
        ):
            return
        for role in message.author.roles:
            if role.id in settings_data.get(
                "trusted_role_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_role_ids"]
            ):
                return
        if message.author.id in settings_data.get(
            "trusted_member_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_member_ids"]
        ):
            return
        if message.channel.id in settings_data.get(
            "ignored_channel_ids", DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"]
        ):
            return

        media_sorted_links = get_media_sorted_links_from_message(message)

        if (
            media_sorted_links.image_links
            or media_sorted_links.video_links
            or media_sorted_links.audio_links
            or media_sorted_links.other_links
        ):
            await message.add_reaction(alert_emoji_str)

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(name="enable", description="Enable alerts.")
    @discord.app_commands.describe(
        alerts_channel="Where to send alerts.",
        mod_role="Which role to ping when the threshold is met.",
        alert_emoji="Which emoji to use for reporting.",
        alert_threshold="How many reports are needed before pinging the mod role.",
    )
    async def alerts_enable(
        self,
        interaction: discord.Interaction,
        alerts_channel: discord.TextChannel,
        mod_role: discord.Role,
        alert_emoji: str,
        alert_threshold: int,
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not settings_data:
                update_dict_defaults(DEFAULT_ALERTS_COG_SETTINGS, settings_data)
            if settings_data.get("enabled", DEFAULT_ALERTS_COG_SETTINGS["enabled"]):
                await interaction.followup.send(
                    "Alerts are already enabled!", ephemeral=True
                )
                return

            settings_data["enabled"] = True
            settings_data["alerts_channel_id"] = alerts_channel.id
            settings_data["mod_role_id"] = mod_role.id
            settings_data["alert_emoji_str"] = str(alert_emoji)
            settings_data["alert_threshold"] = alert_threshold

        await interaction.followup.send("Alerts enabled!", ephemeral=True)

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(name="disable", description="Disable alerts.")
    async def alerts_disable(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return

            settings_data["enabled"] = False

        await interaction.followup.send("Alerts disabled!", ephemeral=True)

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="channel", description="Change where to send alerts."
    )
    @discord.app_commands.describe(alerts_channel="Where to send alerts.")
    async def alerts_channel(
        self, interaction: discord.Interaction, alerts_channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return

            settings_data["alerts_channel_id"] = alerts_channel.id

        await interaction.followup.send(
            f"Alerts channel changed to {alerts_channel.mention}!", ephemeral=True
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="modrole",
        description="Change which role to ping when the threshold is met.",
    )
    @discord.app_commands.describe(
        mod_role="Which role to ping when the threshold is met."
    )
    async def alerts_modrole(
        self, interaction: discord.Interaction, mod_role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return

            settings_data["mod_role_id"] = mod_role.id

        await interaction.followup.send(
            f"Mod role changed to {mod_role.mention}!", ephemeral=True
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="emoji", description="Change which emoji to use for reporting."
    )
    @discord.app_commands.describe(alert_emoji="Which emoji to use for reporting.")
    async def alerts_emoji(self, interaction: discord.Interaction, alert_emoji: str):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return

            settings_data["alert_emoji_str"] = str(alert_emoji)

        await interaction.followup.send(
            f"Alert emoji changed to {str(alert_emoji)}!", ephemeral=True
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @discord.app_commands.command(
        name="threshold",
        description="Change how many reports are needed before pinging the mod role.",
    )
    @discord.app_commands.describe(
        alert_threshold="How many reports are needed before pinging the mod role."
    )
    async def alerts_threshold(
        self, interaction: discord.Interaction, alert_threshold: int
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return

            settings_data["alert_threshold"] = alert_threshold

        await interaction.followup.send(
            f"Alert threshold changed to ``{alert_threshold}``!", ephemeral=True
        )

    alerts_ignore_group = discord.app_commands.Group(
        name="ignore", description="Exclude channels from alerts."
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_ignore_group.command(name="list", description="List ignored channels.")
    async def alerts_ignore_list(self, interaction: discord.Interaction):
        guild = interaction.guild
        settings_data = safe_read(COG, guild, "settings")

        if not await self.cog_is_enabled(settings_data, interaction):
            return

        ignored_channels = ", ".join(
            [
                f"<#{channel_id}>"
                for channel_id in settings_data.get(
                    "ignored_channel_ids",
                    DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"],
                )
            ]
        )

        await interaction.response.send_message(
            f"Ignored Channels: {ignored_channels}",
            ephemeral=True,
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_ignore_group.command(
        name="channel", description="Exclude a channel from alerts."
    )
    @discord.app_commands.describe(channel="Channel to exclude from alerts.")
    async def alerts_ignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if channel.id in settings_data.get(
                "ignored_channel_ids",
                DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"],
            ):
                await interaction.followup.send(
                    f"{channel.mention} is already ignored!", ephemeral=True
                )
                return

            settings_data["ignored_channel_ids"].append(channel.id)

        await interaction.followup.send(
            f"Now ignoring {channel.mention}!", ephemeral=True
        )

    alerts_unignore_group = discord.app_commands.Group(
        name="unignore",
        description="Stop excluding channels from alerts.",
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_unignore_group.command(
        name="channel", description="Stop excluding a channel from alerts."
    )
    @discord.app_commands.describe(channel="Channel to stop excluding from alerts.")
    async def alerts_unignore_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if not channel.id in (
                settings_data.get(
                    "ignored_channel_ids",
                    DEFAULT_ALERTS_COG_SETTINGS["ignored_channel_ids"],
                )
            ):
                await interaction.followup.send(
                    f"{channel.mention} is not ignored!", ephemeral=True
                )
                return

            settings_data["ignored_channel_ids"].remove(channel.id)

        await interaction.followup.send(
            f"No longer ignoring {channel.mention}!", ephemeral=True
        )

    alerts_trust_group = discord.app_commands.Group(
        name="trust",
        description="Exclude members and roles from alerts.",
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_trust_group.command(
        name="list", description="List trusted members and roles."
    )
    async def alerts_trust_list(self, interaction: discord.Interaction):
        guild = interaction.guild
        settings_data = safe_read(COG, guild, "settings")

        if not await self.cog_is_enabled(settings_data, interaction):
            return

        trusted_members = ", ".join(
            [
                f"<@{member_id}>"
                for member_id in settings_data.get(
                    "trusted_member_ids",
                    DEFAULT_ALERTS_COG_SETTINGS["trusted_member_ids"],
                )
            ]
        )
        trusted_roles = ", ".join(
            [
                f"<@&{role_id}>"
                for role_id in settings_data.get(
                    "trusted_role_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_role_ids"]
                )
            ]
        )

        await interaction.response.send_message(
            f"Trusted Members: {trusted_members}\nTrusted Roles: {trusted_roles}",
            ephemeral=True,
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_trust_group.command(
        name="member", description="Exclude a member from alerts."
    )
    @discord.app_commands.describe(member="Member to exclude from alerts.")
    async def alerts_trust_member(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if member.id in (
                settings_data.get(
                    "trusted_member_ids",
                    DEFAULT_ALERTS_COG_SETTINGS["trusted_member_ids"],
                )
            ):
                await interaction.followup.send(
                    f"{member.mention} is already trusted!", ephemeral=True
                )
                return

            settings_data["trusted_member_ids"].append(member.id)

        await interaction.followup.send(
            f"{member.mention} is now trusted!", ephemeral=True
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_trust_group.command(name="role", description="Exclude a role from alerts.")
    @discord.app_commands.describe(role="Role to exclude from alerts.")
    async def alerts_trust_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if role.id in (
                settings_data.get(
                    "trusted_role_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_role_ids"]
                )
            ):
                await interaction.followup.send(
                    f"{role.mention} is already trusted!", ephemeral=True
                )
                return

            settings_data["trusted_role_ids"].append(role.id)

        await interaction.followup.send(
            f"{role.mention} is now trusted!", ephemeral=True
        )

    alerts_untrust_group = discord.app_commands.Group(
        name="untrust",
        description="Stop excluding members and roles from alerts.",
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_untrust_group.command(
        name="member", description="Stop excluding a member from alerts."
    )
    @discord.app_commands.describe(member="Member to stop excluding from alerts.")
    async def alerts_untrust_member(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if not member.id in (
                settings_data.get(
                    "trusted_member_ids",
                    DEFAULT_ALERTS_COG_SETTINGS["trusted_member_ids"],
                )
            ):
                await interaction.followup.send(
                    f"{member.mention} is not trusted!", ephemeral=True
                )
                return

            settings_data["trusted_member_ids"].remove(member.id)

        await interaction.followup.send(
            f"{member.mention} is no longer trusted!", ephemeral=True
        )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @alerts_untrust_group.command(
        name="role", description="Stop excluding a role from alerts."
    )
    @discord.app_commands.describe(role="Role to stop excluding from alerts.")
    async def alerts_untrust_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "settings") as settings_data:
            if not await self.cog_is_enabled(settings_data, interaction):
                return
            if not role.id in (
                settings_data.get(
                    "trusted_role_ids", DEFAULT_ALERTS_COG_SETTINGS["trusted_role_ids"]
                )
            ):
                await interaction.followup.send(
                    f"{role.mention} is not trusted!", ephemeral=True
                )
                return

            settings_data["trusted_role_ids"].remove(role.id)

        await interaction.followup.send(
            f"{role.mention} is no longer trusted!", ephemeral=True
        )

    @staticmethod
    async def cog_is_enabled(settings_data: dict, interaction: discord.Interaction):
        if not settings_data:
            await interaction.followup.send("Alerts are not enabled!", ephemeral=True)
            return False
        if not settings_data.get("enabled", DEFAULT_ALERTS_COG_SETTINGS["enabled"]):
            await interaction.followup.send("Alerts are not enabled!", ephemeral=True)
            return False

        return True


async def setup(bot: Mammoth):
    await bot.add_cog(AlertsCog(bot))
