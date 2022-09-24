from discord.ui import Button
from storage import safe_edit
import helper
import discord


class HashBlacklistObject:
    def __init__(self):
        self.hash_blacklist = []

    def blacklisted(self, hash: str):
        return hash in self.hash_blacklist

    def add(self, hash: str):
        self.hash_blacklist.append(hash)

    def remove(self, hash: str):
        self.hash_blacklist.remove(hash)


class HashBlacklistButton(Button):
    def __init__(self, message: discord.Message, hash: str):
        super().__init__(style=discord.ButtonStyle.gray)

        self.message = message
        self.hash = hash

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

        async with safe_edit(
            "global", guild, "hash_blacklist"
        ) as hash_blacklist_storage_object:
            if not (hash_blacklist := hash_blacklist_storage_object.get()):
                hash_blacklist = HashBlacklistObject()
            if not isinstance(hash_blacklist, HashBlacklistObject):
                hash_blacklist = HashBlacklistObject()
            if hash_blacklist.blacklisted(self.hash):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return

            hash_blacklist.add(self.hash)
            hash_blacklist_storage_object.set(hash_blacklist)

        self.update_mode()

        await interaction.response.edit_message(view=self.view)

    async def unblacklist_mode(self, interaction: discord.Interaction):
        guild = interaction.guild

        async with safe_edit(
            "global", guild, "hash_blacklist"
        ) as hash_blacklist_storage_object:
            if not (hash_blacklist := hash_blacklist_storage_object.get()):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return
            if not isinstance(hash_blacklist, HashBlacklistObject):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return
            if not hash_blacklist.blacklisted(self.hash):
                self.update_mode()

                await interaction.response.edit_message(view=self.view)

                return

            hash_blacklist.remove(self.hash)
            hash_blacklist_storage_object.set(hash_blacklist)

        self.update_mode()

        await interaction.response.edit_message(view=self.view)

    def update_mode(self):
        self.label = (
            "Unblacklist"
            if helper.is_blacklisted(self.message.guild, self.hash)
            else "Blacklist"
        )
