from discord.ext import commands
from discord import app_commands
from main import Mammoth
import traceback
import logging
import discord
import json
import os


COG = __name__

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
