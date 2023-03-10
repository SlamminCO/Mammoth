from discord.ext import commands
from main import Mammoth
from utils.storage import safe_read, safe_edit, update_dict_defaults
from utils.hash import get_media_sorted_link_hashes_from_message
import discord
import json
import logging


COG = __name__
DEFAULT_HASH_BLACKLIST = {"blacklist": []}

log = logging.getLogger(COG)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
class BlacklistCog(commands.GroupCog, name="blacklist"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        log.info("Loaded")

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

        if not (hash_blacklist_data := safe_read("global", guild, "hash_blacklist")):
            return
        if not hash_blacklist_data.get(
            "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
        ):
            return

        for link_hash in all_media_sorted_link_hashes:
            if (
                link_hash.md5 in hash_blacklist_data["blacklist"]
                or link_hash.image_hash in hash_blacklist_data["blacklist"]
            ):
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

    @discord.app_commands.command(name="list", description="List blacklisted hashes.")
    async def blacklist_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        if not (hash_blacklist_data := safe_read("global", guild, "hash_blacklist")):
            hash_blacklist_data = DEFAULT_HASH_BLACKLIST.copy()
        if not hash_blacklist_data.get(
            "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
        ):
            hash_blacklist_data = DEFAULT_HASH_BLACKLIST.copy()

        hash_blacklist = ", ".join(
            [f"``{hash}``" for hash in hash_blacklist["blacklist"]]
        )

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

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit("global", guild, "hash_blacklist") as hash_blacklist_data:
            if not hash_blacklist_data:
                update_dict_defaults(hash_blacklist_data, DEFAULT_HASH_BLACKLIST)
            if not hash_blacklist_data.get(
                "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
            ):
                update_dict_defaults(hash_blacklist_data, DEFAULT_HASH_BLACKLIST)
            if hash in hash_blacklist_data["blacklist"]:
                await interaction.followup.send(
                    f"``{hash}`` is already blacklisted!", ephemeral=True
                )
                return

            hash_blacklist_data["blacklist"].append(hash)

        await interaction.followup.send(f"``{hash}`` blacklisted!", ephemeral=True)

    @discord.app_commands.command(
        name="remove", description="Remove a hash from the blacklist."
    )
    @discord.app_commands.describe(hash="Hash to remove from the blacklist.")
    async def blacklist_blacklist_remove(
        self, interaction: discord.Interaction, hash: str
    ):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit("global", guild, "hash_blacklist") as hash_blacklist_data:
            if not hash_blacklist_data:
                update_dict_defaults(hash_blacklist_data, DEFAULT_HASH_BLACKLIST)
            if not hash_blacklist_data.get(
                "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
            ):
                update_dict_defaults(hash_blacklist_data, DEFAULT_HASH_BLACKLIST)
            if hash not in hash_blacklist_data["blacklist"]:
                await interaction.followup.send(
                    f"``{hash}`` is not blacklisted!", ephemeral=True
                )
                return

            hash_blacklist_data["blacklist"].remove(hash)

        await interaction.followup.send(f"``{hash}`` unblacklisted!", ephemeral=True)


async def setup(bot: Mammoth):
    await bot.add_cog(BlacklistCog(bot))
