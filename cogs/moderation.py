from typing import Optional
from discord.ext import commands, tasks
from main import Mammoth
from utils.storage import safe_edit, safe_read, update_dict_defaults
from utils.link import get_links_from_string
import discord
import json
import asyncio
import traceback
import datetime
import logging
import typing


COG = __name__
ONE_HOUR = 3600
DEFAULT_TRAP_ROLE_SETTINGS = {}
DEFAULT_AUTO_PURGE_SETTINGS = {}
DEFAULT_LINK_FILTER_SETTINGS = {}
DEFAULT_LINK_FILTER_CHANNEL_SETTINGS = {
    "enabled": False,
    "linklist": [],
    "mode": "whitelist",
}
DEFAULT_AUTO_PRUNE_SETTINGS = {"no_roles": False}

log = logging.getLogger(COG)

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


class PruneView(discord.ui.View):
    def __init__(
        self,
        members_to_prune: list[discord.Member],
        root_interaction: discord.Interaction,
    ):
        super().__init__(timeout=None)

        self.members_to_prune = members_to_prune
        self.root_interaction = root_interaction

    @discord.ui.button(label="Prune", style=discord.ButtonStyle.danger)
    async def prune_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.root_interaction.edit_original_response(
            content="Pruning...", view=None
        )

        pruned = 0
        embed = None

        for member in self.members_to_prune:
            try:
                await member.kick(reason="Pruned by moderator")
                pruned += 1
            except Exception as e:
                if embed is None:
                    embed = discord.Embed(
                        title="Failed to kick members", color=discord.Color.red()
                    )

                embed.add_field(name=str(member), value=f"Reason: ```{str(e)}```")

        await self.root_interaction.edit_original_response(
            content=f"Succesfully pruned {pruned}/{len(self.members_to_prune)} member{'' if len(self.members_to_prune) == 1 else 's'}",
            embed=embed,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.root_interaction.edit_original_response(
            content="Cancelled...", view=None
        )
        await asyncio.sleep(3)
        await self.root_interaction.delete_original_response()


class EditLinkFilterView(discord.ui.View):
    def __init__(
        self, root_interaction: discord.Interaction, channel: discord.TextChannel
    ):
        super().__init__(timeout=None)

        self.root_interaction = root_interaction
        self.channel = channel

    @discord.ui.button(label="Toggle State", style=discord.ButtonStyle.gray)
    async def toggle_state_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        async with safe_edit(
            COG, interaction.guild, "link_filters"
        ) as link_filter_data:
            if not link_filter_data:
                update_dict_defaults(DEFAULT_LINK_FILTER_SETTINGS, link_filter_data)
            if not link_filter_data.get(str(self.channel.id)):
                link_filter_data[str(self.channel.id)] = {}
                update_dict_defaults(
                    DEFAULT_LINK_FILTER_CHANNEL_SETTINGS,
                    link_filter_data[str(self.channel.id)],
                )

            link_filter_data[str(self.channel.id)]["enabled"] = not link_filter_data[
                str(self.channel.id)
            ]["enabled"]

        embed = discord.Embed()
        embed.description = f"> Channel: {self.channel.mention}\n> Enabled: ``{link_filter_data[str(self.channel.id)]['enabled']}``\n> Mode: ``{link_filter_data[str(self.channel.id)]['mode']}``\n\n**Link List**:\n```{', '.join(link for link in link_filter_data[str(self.channel.id)]['linklist'])}```"

        await self.root_interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="Toggle Mode", style=discord.ButtonStyle.gray)
    async def toggle_mode_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        async with safe_edit(
            COG, interaction.guild, "link_filters"
        ) as link_filter_data:
            if not link_filter_data:
                update_dict_defaults(DEFAULT_LINK_FILTER_SETTINGS, link_filter_data)
            if not link_filter_data.get(str(self.channel.id)):
                link_filter_data[str(self.channel.id)] = {}
                update_dict_defaults(
                    DEFAULT_LINK_FILTER_CHANNEL_SETTINGS,
                    link_filter_data[str(self.channel.id)],
                )

            link_filter_data[str(self.channel.id)]["mode"] = "whitelist" if link_filter_data[
                str(self.channel.id)
            ]["mode"] == "blacklist" else "blacklist"

        embed = discord.Embed()
        embed.description = f"> Channel: {self.channel.mention}\n> Enabled: ``{link_filter_data[str(self.channel.id)]['enabled']}``\n> Mode: ``{link_filter_data[str(self.channel.id)]['mode']}``\n\n**Link List**:\n```{', '.join(link for link in link_filter_data[str(self.channel.id)]['linklist'])}```"

        await self.root_interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="Edit Links", style=discord.ButtonStyle.gray)
    async def edit_links_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(EditLinksModal(self.root_interaction, self.channel))


class EditLinksModal(discord.ui.Modal):
    def __init__(self, root_interaction: discord.Interaction, channel: discord.TextChannel):
        super().__init__(title="Edit Link Filter")

        self.root_interaction = root_interaction
        self.channel = channel

        self.link_filter_data = safe_read(COG, self.channel.guild, "link_filters")

        self.link_list_input = discord.ui.TextInput(
            label="Link List (Comma Seperated)",
            style=discord.TextStyle.paragraph,
            required=True,
            default=", ".join(
                link
                for link in self.link_filter_data.get(
                    str(self.channel.id), DEFAULT_LINK_FILTER_CHANNEL_SETTINGS
                )["linklist"]
            ),
        )

        self.add_item(self.link_list_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async with safe_edit(
            COG, interaction.guild, "link_filters"
        ) as link_filter_data:
            if not link_filter_data:
                update_dict_defaults(DEFAULT_LINK_FILTER_SETTINGS, link_filter_data)
            if not link_filter_data.get(str(self.channel.id)):
                link_filter_data[str(self.channel.id)] = {}
                update_dict_defaults(
                    DEFAULT_LINK_FILTER_CHANNEL_SETTINGS,
                    link_filter_data[str(self.channel.id)],
                )

            link_filter_data[str(self.channel.id)][
                "linklist"
            ] = [f"{'https://' if not link.startswith(('http://', 'https://')) else ''}{link}" for link in self.link_list_input.value.replace(" ", "").split(",")]

        embed = discord.Embed()
        embed.description = f"> Channel: {self.channel.mention}\n> Enabled: ``{link_filter_data[str(self.channel.id)]['enabled']}``\n> Mode: ``{link_filter_data[str(self.channel.id)]['mode']}``\n\n**Link List**:\n```{', '.join(link for link in link_filter_data[str(self.channel.id)]['linklist'])}```"

        await self.root_interaction.edit_original_response(embed=embed)


@discord.app_commands.guild_only()
class ModerationCog(commands.GroupCog, name="mod"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()
        self.run_auto_prunes.start()
        self.run_auto_purges.start()
        self.run_role_traps.start()

        log.info("Loaded")

    def cog_unload(self):
        self.run_auto_prunes.cancel()
        self.run_auto_purges.cancel()
        self.run_role_traps.cancel()
        log.info("Unloaded")

    @tasks.loop(seconds=15)
    async def run_role_traps(self):
        for guild in self.bot.guilds:
            try:
                if not (role_traps_data := safe_read(COG, guild, "role_traps")):
                    continue

                for trapped_role_id in role_traps_data:
                    if not (trapped_role := guild.get_role(int(trapped_role_id))):
                        continue

                    for member in trapped_role.members:
                        try:
                            await member.ban(
                                reason=role_traps_data[trapped_role_id]["ban_reason"]
                            )
                        except Exception:
                            log.exception(traceback.format_exc())
            except Exception:
                log.exception(traceback.format_exc())

    @tasks.loop(minutes=1)
    async def run_auto_purges(self):
        for guild in self.bot.guilds:
            try:
                if not (auto_purge_data := safe_read(COG, guild, "auto_purge")):
                    continue

                for channel_id in auto_purge_data:
                    channel = guild.get_channel(int(channel_id))

                    if not channel:
                        continue

                    async for message in channel.history(limit=None):
                        try:
                            if message.created_at < (
                                datetime.datetime.now(tz=datetime.timezone.utc)
                                - datetime.timedelta(
                                    days=auto_purge_data[channel_id]["lifetime"]
                                )
                            ):
                                await message.delete()
                        except Exception:
                            log.error(traceback.format_exc())
            except Exception:
                log.error(traceback.format_exc())

    @tasks.loop(minutes=1)
    async def run_auto_prunes(self):
        for guild in self.bot.guilds:
            try:
                if not (auto_prune_data := safe_read(COG, guild, "auto_prune")):
                    continue

                if auto_prune_data["no_roles"]:
                    members_to_prune = [
                        member
                        for member in guild.members
                        if len(member.roles) <= 1
                        and (
                            datetime.datetime.now(datetime.timezone.utc)
                            - member.joined_at
                        ).total_seconds()
                        >= ONE_HOUR
                    ]

                    for member in members_to_prune:
                        try:
                            await member.kick(reason="Pruned by autoprune")
                        except Exception:
                            log.error(
                                f"Failed to prune {member} in {guild}:\n{traceback.format_exc()}"
                            )
            except Exception:
                log.error(traceback.format_exc())

    @commands.Cog.listener(name="on_message")
    async def handle_link_filters_on_message(self, message: discord.Message):
        if not (guild := message.guild):
            return
        if not (link_filter_data := safe_read(COG, guild, "link_filters")):
            return
        if not link_filter_data.get(str(message.channel.id)):
            return
        if not link_filter_data[str(message.channel.id)].get("enabled", DEFAULT_LINK_FILTER_CHANNEL_SETTINGS["enabled"]):
            return
        if not link_filter_data[str(message.channel.id)].get("linklist", DEFAULT_LINK_FILTER_CHANNEL_SETTINGS["linklist"]):
            return
        if not link_filter_data[str(message.channel.id)].get("mode", DEFAULT_LINK_FILTER_CHANNEL_SETTINGS["mode"]):
            return
        
        if link_filter_data[str(message.channel.id)]["mode"] == "whitelist":
            for link in get_links_from_string(message.content):
                if link.startswith(tuple(link_filter_data[str(message.channel.id)]["linklist"])):
                    continue

                try:
                    await message.delete()
                    return
                except Exception:
                    log.exception(traceback.format_exc())
        elif link_filter_data[str(message.channel.id)]["mode"] == "blacklist":
            for link in get_links_from_string(message.content):
                if link.startswith(tuple(link_filter_data[str(message.channel.id)]["linklist"])):
                    try:
                        await message.delete()
                        return
                    except Exception:
                        log.exception(traceback.format_exc())

    @commands.Cog.listener(name="on_member_update")
    async def run_role_traps_on_member_update(
        self, before: discord.Member, after: discord.Member
    ):
        if before.roles == after.roles:
            return
        if not (guild := after.guild):
            return
        if not (role_traps_data := safe_read(COG, guild, "role_traps")):
            return

        for role in after.roles:
            if str(role.id) in role_traps_data:
                try:
                    await after.ban(reason=role_traps_data[str(role.id)]["ban_reason"])
                except Exception:
                    log.exception(traceback.format_exc())

    mod_link_group = discord.app_commands.Group(
        name="link", description="Manage link filtering."
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @mod_link_group.command(
        name="filter", description="Edit the link filter for a channel"
    )
    async def mod_link_filter(
        self, interaction: discord.Interaction, channel: typing.Optional[discord.TextChannel]
    ):
        channel = interaction.channel if not channel else channel

        if not (link_filter_data := safe_read(COG, channel.guild, "link_filters")):
            update_dict_defaults(DEFAULT_LINK_FILTER_SETTINGS, link_filter_data)
        if not link_filter_data.get(str(channel.id)):
            link_filter_data[str(channel.id)] = {}
            update_dict_defaults(
                DEFAULT_LINK_FILTER_CHANNEL_SETTINGS, link_filter_data[str(channel.id)]
            )

        embed = discord.Embed()
        embed.description = f"> Channel: {channel.mention}\n> Enabled: ``{link_filter_data[str(channel.id)]['enabled']}``\n> Mode: ``{link_filter_data[str(channel.id)]['mode']}``\n\n**Link List**:\n```{', '.join(link for link in link_filter_data[str(channel.id)]['linklist'])}```"

        await interaction.response.send_message(
            embed=embed, view=EditLinkFilterView(interaction, channel), ephemeral=True
        )

    mod_trap_role_group = discord.app_commands.Group(
        name="traprole", description="Manage trapped roles."
    )

    @discord.app_commands.checks.has_permissions(ban_members=True)
    @discord.app_commands.checks.bot_has_permissions(ban_members=True)
    @mod_trap_role_group.command(name="add", description="Add a role to be trapped.")
    async def mod_trap_role_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        ban_reason: Optional[str],
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "role_traps") as role_traps_data:
            if not role_traps_data:
                update_dict_defaults(DEFAULT_TRAP_ROLE_SETTINGS, role_traps_data)
            if role.id in role_traps_data:
                await interaction.followup.send("Role is already trapped!")
                return

            role_traps_data[role.id] = {"ban_reason": ban_reason}

        await interaction.followup.send(f"{role.mention} is now trapped!")

    @discord.app_commands.checks.has_permissions(ban_members=True)
    @discord.app_commands.checks.bot_has_permissions(ban_members=True)
    @mod_trap_role_group.command(name="list", description="List trapped roles.")
    async def mod_trap_role_list(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not (role_traps_data := safe_read(COG, interaction.guild, "role_traps")):
            await interaction.followup.send("No roles are trapped!")
            return

        await interaction.followup.send(
            f"**Trapped Roles**\n {', '.join(interaction.guild.get_role(int(role_id)).mention for role_id in role_traps_data)}"
        )

    @discord.app_commands.checks.has_permissions(ban_members=True)
    @discord.app_commands.checks.bot_has_permissions(ban_members=True)
    @mod_trap_role_group.command(
        name="remove", description="Remove a role from being trapped."
    )
    async def mod_trap_role_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "role_traps") as role_traps_data:
            if not role_traps_data:
                update_dict_defaults(DEFAULT_TRAP_ROLE_SETTINGS, role_traps_data)
            if role.id not in role_traps_data:
                await interaction.followup.send("Role is not trapped!")
                return

            del role_traps_data[role.id]

        await interaction.followup.send(f"{role.mention} is no longer trapped!")

    mod_autopurge_group = discord.app_commands.Group(
        name="autopurge", description="Manage automatic message purging."
    )

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @mod_autopurge_group.command(
        name="enable", description="Enable automatic message purging in a channel."
    )
    @discord.app_commands.describe(
        channel="Channel to enable auto purge in.",
        lifetime="How many days messages will be kept before being deleted.",
    )
    async def mod_autopurge_enable(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        lifetime: int,
    ):
        if lifetime <= 0:
            await interaction.response.send_message("Lifetime must be greater than 0.")
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "auto_purge") as auto_purge_data:
            if not auto_purge_data:
                update_dict_defaults(DEFAULT_AUTO_PURGE_SETTINGS, auto_purge_data)
            if str(channel.id) in auto_purge_data:
                await interaction.followup.send(
                    f"Automatic message purging is already enabled in {channel.mention}!"
                )
                return

            auto_purge_data[str(channel.id)] = {"lifetime": lifetime}

        await interaction.followup.send(f"Auto purge enabled for {channel.mention}!")

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.checks.bot_has_permissions(manage_messages=True)
    @mod_autopurge_group.command(
        name="disable", description="Disable automatic message purging in a channel."
    )
    @discord.app_commands.describe(channel="Channel to disable auto purge in.")
    async def mod_autopurge_disable(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "auto_purge") as auto_purge_data:
            if not auto_purge_data:
                update_dict_defaults(DEFAULT_AUTO_PURGE_SETTINGS, auto_purge_data)
            if str(channel.id) not in auto_purge_data:
                await interaction.followup.send(
                    f"Automatic message purging is not enabled in {channel.mention}!"
                )
                return

            del auto_purge_data[str(channel.id)]

        await interaction.followup.send(f"Auto purge disabled for {channel.mention}!")

    mod_role_group = discord.app_commands.Group(
        name="role", description="Manage members roles."
    )

    @discord.app_commands.checks.has_permissions(manage_roles=True)
    @discord.app_commands.checks.bot_has_permissions(manage_roles=True)
    @mod_role_group.command(name="addall", description="Add a role to all members.")
    async def mod_role_addall(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        roles_given = 0
        embed = None

        for member in interaction.guild.members:
            try:
                await member.add_roles(role)
                roles_given += 1
            except Exception as e:
                if embed is None:
                    embed = discord.Embed(
                        title="Failed to update members", color=discord.Color.red()
                    )

                embed.add_field(name=str(member), value=f"Reason: ```{str(e)}```")

        await interaction.followup.send(
            content=f"Succesfully updated {roles_given}/{len(interaction.guild.members)} member{'' if len(interaction.guild.members) == 1 else 's'}",
            embed=embed,
        )

    mod_autoprune_group = discord.app_commands.Group(
        name="autoprune",
        description="Enable and disable auto pruning of members from the server.",
    )

    @discord.app_commands.checks.has_permissions(kick_members=True)
    @discord.app_commands.checks.bot_has_permissions(kick_members=True)
    @mod_autoprune_group.command(
        name="noroles",
        description="Enable or disable auto pruning of members without roles.",
    )
    async def mod_autoprune_noroles(
        self, interaction: discord.Interaction, state: bool
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "auto_prune") as auto_prune_data:
            if not auto_prune_data:
                update_dict_defaults(DEFAULT_AUTO_PURGE_SETTINGS, auto_prune_data)

            auto_prune_data["no_roles"] = state

        await interaction.followup.send(
            f"Auto pruning of members without roles has been set to {state}"
        )

    mod_prune_group = discord.app_commands.Group(
        name="prune", description="Prune members from the server."
    )

    @discord.app_commands.checks.has_permissions(kick_members=True)
    @discord.app_commands.checks.bot_has_permissions(kick_members=True)
    @mod_prune_group.command(
        name="noroles",
        description="Prune all members from the server that have no role.",
    )
    async def mod_prune_noroles(self, interaction: discord.Interaction):
        members_with_no_roles = [
            member for member in interaction.guild.members if len(member.roles) <= 1
        ]

        await interaction.response.send_message(
            content=f"{len(members_with_no_roles)} out of {len(interaction.guild.members)} member{'' if len(interaction.guild.members) == 1 else 's'} will be pruned.",
            ephemeral=True,
            view=PruneView(members_with_no_roles, interaction),
        )


async def setup(bot: Mammoth):
    await bot.add_cog(ModerationCog(bot))
