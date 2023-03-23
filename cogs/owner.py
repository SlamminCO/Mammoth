from discord.ext import commands
from discord import app_commands
from main import Mammoth
from utils.storage import safe_read, safe_edit, update_dict_defaults
import traceback
import logging
import discord
import json
import os


COG = __name__
DEFAULT_WHITELIST_DATA = {"enabled": False, "whitelist": []}

log = logging.getLogger(COG)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


def is_owner(interaction: discord.Interaction):
    return interaction.user.id in SETTINGS["ownerIDs"]


@app_commands.check(is_owner)
class OwnerCog(commands.GroupCog, name="owner"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        log.info("Loaded")

    @commands.Cog.listener(name="on_guild_join")
    async def handle_whitelist_on_guild_join(self, guild: discord.Guild):
        if not (whitelist_data := safe_read(COG, 0, "whitelist")):
            return
        if not whitelist_data["enabled"]:
            return

        if guild.id not in whitelist_data["whitelist"]:
            try:
                await guild.leave()
                log.info(
                    f"Left guild [{guild}] | [{guild.id}] because it is not whitelisted!"
                )
            except Exception:
                log.error(
                    f"Failed to leave non-whitelisted guild [{guild}] | [{guild.id}]"
                )
                log.exception(traceback.format_exc())

    owner_whitelist_group = discord.app_commands.Group(
        name="whitelist",
        description="Manage the bot's guild whitelist.",
    )

    @owner_whitelist_group.command(
        name="enable", description="Enable guild whitelisting."
    )
    async def owner_whitelist_enable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        async with safe_edit(COG, 0, "whitelist") as whitelist_data:
            if not whitelist_data:
                update_dict_defaults(DEFAULT_WHITELIST_DATA, whitelist_data)
            if whitelist_data["enabled"]:
                await interaction.followup.send(
                    "Guild whitelisting is already enabled!"
                )
                return

            whitelist_data["enabled"] = True

        await interaction.followup.send("Guild whitelisting enabled!")

    @owner_whitelist_group.command(
        name="disabled", description="Disable guild whitelisting."
    )
    async def owner_whitelist_disable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        async with safe_edit(COG, 0, "whitelist") as whitelist_data:
            if not whitelist_data:
                update_dict_defaults(DEFAULT_WHITELIST_DATA, whitelist_data)
            if not whitelist_data["enabled"]:
                await interaction.followup.send("Guild whitelisting is not enabled!")
                return

            whitelist_data["enabled"] = False

        await interaction.followup.send("Guild whitelisting disabled!")

    @owner_whitelist_group.command(
        name="add", description="Add a guild to the whitelist."
    )
    @app_commands.describe(guild_id="ID of the guild to whitelist.")
    async def owner_whitelist_add(
        self, interaction: discord.Interaction, guild_id: str
    ):
        if not guild_id.isdigit():
            await interaction.response.send_message("Guild ID must be a number!")
            return

        guild_id = int(guild_id)

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with safe_edit(COG, 0, "whitelist") as whitelist_data:
            if not whitelist_data:
                update_dict_defaults(DEFAULT_WHITELIST_DATA, whitelist_data)
            if not whitelist_data["enabled"]:
                await interaction.followup.send("Guild whitelist is not enabled!")
                return
            if guild_id in whitelist_data["whitelist"]:
                await interaction.followup.send(
                    f"Guild ``{guild_id}`` is already whitelisted!"
                )
                return

            whitelist_data["whitelist"].append(guild_id)

        await interaction.followup.send(f"Guild ``{guild_id}`` whitelisted!")

    @owner_whitelist_group.command(
        name="remove", description="Remove a guild from the whitelist."
    )
    @app_commands.describe(guild_id="ID of the guild to remove from the whitelist.")
    async def owner_whitelist_remove(
        self, interaction: discord.Interaction, guild_id: str
    ):
        if not guild_id.isdigit():
            await interaction.response.send_message("Guild ID must be a number!")
            return

        guild_id = int(guild_id)

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with safe_edit(COG, 0, "whitelist") as whitelist_data:
            if not whitelist_data:
                update_dict_defaults(DEFAULT_WHITELIST_DATA, whitelist_data)
            if not whitelist_data["enabled"]:
                await interaction.followup.send("Guild whitelist is not enabled!")
                return
            if guild_id in whitelist_data["whitelist"]:
                await interaction.followup.send(
                    f"Guild ``{guild_id}`` is already whitelisted!"
                )
                return

            whitelist_data["whitelist"].remove(guild_id)

        await interaction.followup.send(
            f"Guild ``{guild_id}`` removed from the whitelist!"
        )

    @owner_whitelist_remove.autocomplete("guild_id")
    async def owner_whitelist_remove_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        if not (whitelist_data := safe_read(COG, 0, "whitelist")):
            return []
        if not whitelist_data.get("enabled", DEFAULT_WHITELIST_DATA["enabled"]):
            return []
        if not whitelist_data.get("whitelist", DEFAULT_WHITELIST_DATA["whitelist"]):
            return []

        return [
            app_commands.Choice(name=str(guild_id), value=str(guild_id))
            for guild_id in whitelist_data["whitelist"]
            if current.lower() in str(guild_id).lower()
        ]

    @app_commands.command(name="load", description="Load a cog.")
    @app_commands.describe(cog="Cog to load")
    async def owner_load(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.load_extension(f"cogs.{cog}")

            await interaction.response.send_message(
                f"``{cog}`` loaded successfully!", ephemeral=True
            )
        except commands.ExtensionNotFound:
            await interaction.response.send_message(
                f"``{cog}`` not found in the cogs directory!", ephemeral=True
            )
        except commands.ExtensionAlreadyLoaded:
            await interaction.response.send_message(
                f"``{cog}`` already loaded!", ephemeral=True
            )
        except commands.NoEntryPointError:
            await interaction.response.send_message(
                f"``{cog}`` missing setup function!", ephemeral=True
            )
        except commands.ExtensionFailed as e:
            await interaction.response.send_message(
                f"``{cog}`` failed to load!\n\n```{e}```", ephemeral=True
            )
            log.exception(traceback.format_exc())

    @owner_load.autocomplete("cog")
    async def owner_load_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        cogs = [
            cog.replace(".py", "")
            for cog in os.listdir("./cogs")
            if cog.endswith(".py")
        ]
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="unload", description="Unload a cog.")
    @app_commands.describe(cog="Cog to unload")
    async def owner_unload(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.unload_extension(f"cogs.{cog}")

            await interaction.response.send_message(
                f"``{cog}`` unloaded successfully!", ephemeral=True
            )
        except commands.ExtensionNotFound:
            await interaction.response.send_message(
                f"``{cog}`` not found in the cogs directory!", ephemeral=True
            )
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(
                f"``{cog}`` not loaded!", ephemeral=True
            )

    @owner_unload.autocomplete("cog")
    async def owner_unload_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        cogs = [
            cog.replace(".py", "")
            for cog in os.listdir("./cogs")
            if cog.endswith(".py")
        ]
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="reload", description="Reload a cog.")
    @app_commands.describe(cog="Cog to reload")
    async def owner_reload(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")

            await interaction.response.send_message(
                f"``{cog}`` successfully reloaded!", ephemeral=True
            )
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(
                f"``{cog}`` not loaded!", ephemeral=True
            )
        except commands.ExtensionNotFound:
            await interaction.response.send_message(
                f"``{cog}`` not found in the cogs directory!", ephemeral=True
            )
        except commands.NoEntryPointError:
            await interaction.response.send_message(
                f"``{cog}`` missing setup function!", ephemeral=True
            )
        except commands.ExtensionFailed as e:
            await interaction.response.send_message(
                f"``{cog}`` failed to load!\n\n```{e}```", ephemeral=True
            )
            log.exception(traceback.format_exc())

    @owner_reload.autocomplete("cog")
    async def owner_reload_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        cogs = [
            cog.replace(".py", "")
            for cog in os.listdir("./cogs")
            if cog.endswith(".py")
        ]
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @app_commands.command(name="reloadall", description="Reloads all cogs.")
    async def owner_reloadall(self, interaction: discord.Interaction):
        messages = []

        for cog in [
            f'{x[:x.find(".py")]}' for x in os.listdir("./cogs") if x.endswith(".py")
        ]:
            try:
                await self.bot.reload_extension(f"cogs.{cog}")

                messages.append(f"``{cog}`` successfully reloaded!\n\n")
            except commands.ExtensionNotLoaded:
                messages.append(f"``{cog}`` not loaded!\n\n")
            except commands.ExtensionNotFound:
                messages.append(f"``{cog}`` not found in the cogs directory!\n\n")
            except commands.NoEntryPointError:
                messages.append(f"``{cog}`` missing setup function!\n\n")
            except commands.ExtensionFailed as e:
                messages.append(f"``{cog}`` failed to load!\n\n```{e}```\n\n")
                log.exception(traceback.format_exc())

        await interaction.response.send_message(
            f'Reload:\n\n{"".join(messages)}', ephemeral=True
        )

    @app_commands.command(name="servers", description="List all servers the bot is in.")
    async def owner_servers(self, interaction: discord.Interaction):
        if not self.bot.guilds:
            await interaction.response.send_message(
                "I am not in any servers!", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f'Servers: {", ".join([f"``{guild}``" for guild in self.bot.guilds])}',
            ephemeral=True,
        )

    # These do not check against the settings specified owner list!

    @commands.is_owner()
    @commands.command(name="sync")
    async def owner_sync(self, ctx: commands.Context, scope: str = "local" or "global"):
        guild = ctx.guild

        if scope == "global":
            await self.bot.tree.sync()
            await ctx.reply(f"Synced app commands globally!")
            return

        self.bot.tree.copy_global_to(guild=guild)
        await self.bot.tree.sync(guild=guild)

        await ctx.reply(f"Synced app commands for {guild}!")

    @commands.is_owner()
    @commands.command(name="unsync")
    async def owner_unsync(self, ctx: commands.Context):
        guild = ctx.guild

        self.bot.tree.clear_commands(guild=guild)
        await self.bot.tree.sync(guild=guild)
        await ctx.reply(f"Cleared app commands for {guild}")


async def setup(bot: Mammoth):
    await bot.add_cog(OwnerCog(bot))
