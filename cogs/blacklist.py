from discord.ext import commands
from main import Mammoth
from shared_classes import HashBlacklistObject
from utils.storage import safe_read, safe_edit
from utils.hash import get_media_sorted_link_hashes_from_message
from utils.debug import DebugPrinter
import discord
import json


COG = __name__

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


debug_printer = DebugPrinter(COG, SETTINGS["debugPrinting"])
dprint = debug_printer.dprint


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

        media_sorted_link_hashes = await get_media_sorted_link_hashes_from_message(
            message
        )
        all_media_sorted_link_hashes = (
            media_sorted_link_hashes.image_link_hashes
            + media_sorted_link_hashes.video_link_hashes
            + media_sorted_link_hashes.audio_link_hashes
        )

        storage_object = safe_read("global", guild, "hash_blacklist")

        if not (hash_blacklist := storage_object.get()):
            return
        if not isinstance(hash_blacklist, HashBlacklistObject):
            return

        for link_hash in all_media_sorted_link_hashes:
            if hash_blacklist.link_hash_blacklisted(link_hash):
                try:
                    await message.delete()

                    notice_message = await channel.send(
                        f"{message.author.mention} Your message has been removed for containing blacklisted media."
                    )

                    await notice_message.delete(delay=30)
                except discord.Forbidden:
                    return
                except discord.NotFound:
                    return
                except discord.HTTPException:
                    return

    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.command(name="list", description="List blacklisted hashes.")
    async def blacklist_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        storage_object = safe_read("global", guild, "hash_blacklist")

        if not (hash_blacklist := storage_object.get()):
            hash_blacklist = HashBlacklistObject()
        if not isinstance(hash_blacklist, HashBlacklistObject):
            hash_blacklist = HashBlacklistObject()

        hash_blacklist = ", ".join([f"``{hash}``" for hash in hash_blacklist.all()])

        await interaction.response.send_message(
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

        async with safe_edit("global", guild, "hash_blacklist") as storage_object:
            if not (hash_blacklist := storage_object.get()):
                hash_blacklist = HashBlacklistObject()
            if not isinstance(hash_blacklist, HashBlacklistObject):
                hash_blacklist = HashBlacklistObject()
            if hash_blacklist.string_blacklisted(hash):
                await interaction.followup.send(f"``{hash}`` is already blacklisted!")
                return

            hash_blacklist.add(hash)
            storage_object.set(hash_blacklist)

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
            if not hash_blacklist.string_blacklisted(hash):
                await interaction.followup.send(f"``{hash}`` is not blacklisted!")
                return

            hash_blacklist.remove(hash)
            hash_blacklist_storage_object.set(hash_blacklist)

        await interaction.followup.send(f"``{hash}`` unblacklisted!")


async def setup(bot: Mammoth):
    await bot.add_cog(BlacklistCog(bot))
