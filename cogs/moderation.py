from typing import Optional
from discord.ext import commands, tasks
from main import Mammoth
from utils.storage import safe_edit, safe_read, update_dict_defaults
import discord
import json
import asyncio
import traceback
import datetime
import logging


COG = __name__
ONE_HOUR = 3600
DEFAULT_TRAP_ROLE_SETTINGS = {}
DEFAULT_AUTO_PURGE_SETTINGS = {}
DEFAULT_AUTO_PRUNE_SETTINGS = {
    "no_roles": False
}

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


@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True, manage_roles=True)
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
                if not (role_traps := safe_read(COG, guild, "role_traps")):
                    continue

                for trapped_role_id in role_traps:
                    if not (trapped_role := guild.get_role(trapped_role_id)):
                        continue

                    for member in trapped_role.members:
                        try:
                            await member.ban(
                                reason=role_traps[trapped_role_id]["ban_reason"]
                            )
                        except Exception:
                            log.exception(traceback.format_exc())
            except Exception:
                log.exception(traceback.format_exc())

    @tasks.loop(minutes=1)
    async def run_auto_purges(self):
        for guild in self.bot.guilds:
            try:
                if not (auto_purge := safe_read(COG, guild, "auto_purge")):
                    continue

                for channel_id in auto_purge:
                    channel = guild.get_channel(int(channel_id))

                    if not channel:
                        continue

                    async for message in channel.history(limit=None):
                        try:
                            if message.created_at < (
                                datetime.datetime.now(tz=datetime.timezone.utc)
                                - datetime.timedelta(
                                    days=auto_purge[channel_id]["lifetime"]
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
                if not (auto_prune := safe_read(COG, guild, "auto_prune")):
                    continue

                if auto_prune["no_roles"]:
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

    @commands.Cog.listener(name="on_member_update")
    async def run_role_traps_on_member_update(
        self, before: discord.Member, after: discord.Member
    ):
        if before.roles == after.roles:
            return
        if not (guild := after.guild):
            return
        if not (role_traps := safe_read(COG, guild, "role_traps")):
            return

        for role in after.roles:
            if role.id in role_traps:
                try:
                    await after.ban(reason=role_traps[role.id]["ban_reason"])
                except Exception:
                    log.exception(traceback.format_exc())

    mod_trap_role_group = discord.app_commands.Group(
        name="traprole", description="Manage trapped roles."
    )

    @mod_trap_role_group.command(name="add", description="Add a role to be trapped.")
    async def mod_trap_role_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        ban_reason: Optional[str],
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "role_traps") as role_traps:
            if not role_traps:
                update_dict_defaults(DEFAULT_TRAP_ROLE_SETTINGS, role_traps)
            if role.id in role_traps:
                await interaction.followup.send("Role is already trapped!")
                return

            role_traps[role.id] = {"ban_reason": ban_reason}

        await interaction.followup.send(f"{role.mention} is now trapped!")

    @mod_trap_role_group.command(name="list", description="List trapped roles.")
    async def mod_trap_role_list(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not (role_traps := safe_read(COG, interaction.guild, "role_traps")):
            await interaction.followup.send("No roles are trapped!")
            return

        await interaction.followup.send(
            f"**Trapped Roles**\n {', '.join(interaction.guild.get_role(role_id).mention for role_id in role_traps)}"
        )

    @mod_trap_role_group.command(
        name="remove", description="Remove a role from being trapped."
    )
    async def mod_trap_role_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "role_traps") as role_traps:
            if not role_traps:
                update_dict_defaults(DEFAULT_TRAP_ROLE_SETTINGS, role_traps)
            if role.id not in role_traps:
                await interaction.followup.send("Role is not trapped!")
                return

            del role_traps[role.id]

        await interaction.followup.send(f"{role.mention} is no longer trapped!")

    mod_autopurge_group = discord.app_commands.Group(
        name="autopurge", description="Manage automatic message purging."
    )

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

        async with safe_edit(COG, interaction.guild, "auto_purge") as auto_purge:
            if not auto_purge:
                update_dict_defaults(DEFAULT_AUTO_PURGE_SETTINGS, auto_purge)
            if str(channel.id) in auto_purge:
                await interaction.followup.send(
                    f"Automatic message purging is already enabled in {channel.mention}!"
                )
                return

            auto_purge[str(channel.id)] = {"lifetime": lifetime}

        await interaction.followup.send(f"Auto purge enabled for {channel.mention}!")

    @mod_autopurge_group.command(
        name="disable", description="Disable automatic message purging in a channel."
    )
    @discord.app_commands.describe(channel="Channel to disable auto purge in.")
    async def mod_autopurge_disable(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, interaction.guild, "auto_purge") as auto_purge:
            if not auto_purge:
                update_dict_defaults(DEFAULT_AUTO_PURGE_SETTINGS, auto_purge)
            if str(channel.id) not in auto_purge:
                await interaction.followup.send(
                    f"Automatic message purging is not enabled in {channel.mention}!"
                )
                return

            del auto_purge[str(channel.id)]

        await interaction.followup.send(f"Auto purge disabled for {channel.mention}!")

    mod_role_group = discord.app_commands.Group(
        name="role", description="Manage members roles."
    )

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

    mod_prune_group = discord.app_commands.Group(
        name="prune", description="Prune members from the server."
    )

    mod_autoprune_group = discord.app_commands.Group(
        name="autoprune",
        description="Enable and disable auto pruning of members from the server.",
    )

    @mod_autoprune_group.command(
        name="noroles",
        description="Enable or disable auto pruning of members without roles.",
    )
    async def mod_autoprune_noroles(
        self, interaction: discord.Interaction, state: bool
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "auto_prune") as auto_prune:
            if not auto_prune:
                auto_prune = DEFAULT_AUTO_PRUNE_SETTINGS

            auto_prune["no_roles"] = state

        await interaction.followup.send(
            f"Auto pruning of members without roles has been set to {state}"
        )

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
