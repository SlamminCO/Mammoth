from time import time
from helper import DPrinter
from discord.ext import commands
from main import Mammoth
from shared_classes import HashBlacklistObject
from storage import safe_edit
import discord
import helper
import json


COG = __name__

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


dprint = DPrinter(COG).dprint


@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
class BlacklistCog(commands.GroupCog, name="blacklist"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        dprint(f"Loaded {COG}")

    @commands.Cog.listener(name="on_message")
    async def handle_blacklisted_content(self, message: discord.Message):
        channel = message.channel

        if not (guild := message.guild):
            return

        results, _ = await helper.get_media_hashes_from_message(message)

        for result in results:
            if helper.is_blacklisted(guild, results[result]):
                try:
                    await message.delete()

                    notice_message = await channel.send(
                        f"{message.author.mention} Your message has been removed for containing blacklisted media."
                    )

                    await notice_message.delete(delay=30)
                except discord.Forbidden:
                    # return False, "⚠ **Blacklisted media could not be deleted!** ⚠"
                    return
                except discord.NotFound:
                    # return True, None
                    return
                except discord.HTTPException:
                    # return False, "⚠ **Blacklisted media could not be deleted!** ⚠"
                    return

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.command(name="list", description="List blacklisted hashes.")
    async def blacklist_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(
            "global", guild, "hash_blacklist"
        ) as hash_blacklist_storage_object:
            if not (hash_blacklist := hash_blacklist_storage_object.get()):
                hash_blacklist = HashBlacklistObject()
            if not isinstance(hash_blacklist, HashBlacklistObject):
                hash_blacklist = HashBlacklistObject()

            hash_blacklist = ", ".join([f"``{hash}``" for hash in hash_blacklist.all()])

            await interaction.followup.send(
                f"Hashes Blacklisted: {hash_blacklist}",
                ephemeral=True,
            )

    @discord.app_commands.command(
        name="add", description="Add a hash to the blacklist."
    )
    @discord.app_commands.describe(hash="Hash to add to the blacklist.")
    async def blacklist_blacklist_add(
        self, interaction: discord.Interaction, hash: str
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(
            "global", guild, "hash_blacklist"
        ) as hash_blacklist_storage_object:
            if not (hash_blacklist := hash_blacklist_storage_object.get()):
                hash_blacklist = HashBlacklistObject()
            if not isinstance(hash_blacklist, HashBlacklistObject):
                hash_blacklist = HashBlacklistObject()
            if hash_blacklist.blacklisted(hash):
                await interaction.followup.send(f"``{hash}`` is already blacklisted!")
                return

            hash_blacklist.add(hash)
            hash_blacklist_storage_object.set(hash_blacklist)

        await interaction.followup.send(f"``{hash}`` blacklisted!")

    @discord.app_commands.command(
        name="remove", description="Remove a hash from the blacklist."
    )
    @discord.app_commands.describe(hash="Hash to remove from the blacklist.")
    async def blacklist_blacklist_remove(
        self, interaction: discord.Interaction, hash: str
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True)

        async with safe_edit(
            "global", guild, "hash_blacklist"
        ) as hash_blacklist_storage_object:
            if not (hash_blacklist := hash_blacklist_storage_object.get()):
                hash_blacklist = HashBlacklistObject()
            if not isinstance(hash_blacklist, HashBlacklistObject):
                hash_blacklist = HashBlacklistObject()
            if not hash_blacklist.blacklisted(hash):
                await interaction.followup.send(f"``{hash}`` is not blacklisted!")
                return

            hash_blacklist.remove(hash)
            hash_blacklist_storage_object.set(hash_blacklist)

        await interaction.followup.send(f"``{hash}`` unblacklisted!")


async def setup(bot: Mammoth):
    await bot.add_cog(BlacklistCog(bot))
