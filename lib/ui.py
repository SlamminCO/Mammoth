from discord.ui import Button
from utils.storage import safe_read, safe_edit, update_dict_defaults
from utils.hash import LinkHash
from cogs.blacklist import DEFAULT_HASH_BLACKLIST
import discord


class HashBlacklistButton(Button):
    def __init__(self, message: discord.Message, link_hash: LinkHash):
        super().__init__(style=discord.ButtonStyle.gray)

        self.message = message
        self.link_hash = link_hash

        self.update_mode()

    async def callback(self, interaction: discord.Interaction):
        if not self.message.channel.permissions_for(interaction.user).manage_messages:
            return await interaction.response.send_message(
                f"You do not have permission to manage messages in {self.message.channel.mention}!"
            )

        if self.label == "Blacklist":
            await self.blacklist_mode(interaction)
            return

        await self.unblacklist_mode(interaction)

    async def blacklist_mode(self, interaction: discord.Interaction):
        guild = interaction.guild

        async with safe_edit("global", guild, "hash_blacklist") as hash_blacklist_data:
            if not hash_blacklist_data or not hash_blacklist_data.get(
                "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
            ):
                update_dict_defaults(hash_blacklist_data, DEFAULT_HASH_BLACKLIST)
            if (
                self.link_hash.md5 in hash_blacklist_data["blacklist"]
                or self.link_hash.image_hash in hash_blacklist_data["blacklist"]
            ):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return

            if self.link_hash.md5:
                hash_blacklist_data["blacklist"].append(self.link_hash.md5)
            if self.link_hash.image_hash:
                hash_blacklist_data["blacklist"].append(self.link_hash.image_hash)

        self.update_mode()

        await interaction.response.edit_message(view=self.view)

    async def unblacklist_mode(self, interaction: discord.Interaction):
        guild = interaction.guild

        async with safe_edit("global", guild, "hash_blacklist") as hash_blacklist_data:
            if not hash_blacklist_data or not hash_blacklist_data.get(
                "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
            ):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return
            if not (
                self.link_hash.md5 in hash_blacklist_data["blacklist"]
                or self.link_hash.image_hash in hash_blacklist_data["blacklist"]
            ):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return

            if self.link_hash.md5:
                hash_blacklist_data["blacklist"].remove(self.link_hash.md5)
            if self.link_hash.image_hash:
                hash_blacklist_data["blacklist"].remove(self.link_hash.image_hash)

        self.update_mode()

        await interaction.response.edit_message(view=self.view)

    def update_mode(self):
        if not (
            hash_blacklist_data := safe_read(
                "global", self.message.guild, "hash_blacklist"
            )
        ):
            hash_blacklist_data = DEFAULT_HASH_BLACKLIST.copy()
        if not hash_blacklist_data.get(
            "blacklist", DEFAULT_HASH_BLACKLIST["blacklist"]
        ):
            hash_blacklist_data = DEFAULT_HASH_BLACKLIST.copy()

        self.label = (
            "Unblacklist"
            if self.link_hash.md5 in hash_blacklist_data["blacklist"]
            or self.link_hash.image_hash in hash_blacklist_data["blacklist"]
            else "Blacklist"
        )
