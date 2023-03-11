from discord.ext import commands, tasks
from main import Mammoth
from utils.storage import safe_read, safe_edit, update_dict_defaults
import discord
import json
import time
import traceback
import logging


COG = __name__
DEFAULT_TIMER_DATA = {}

log = logging.getLogger(COG)

with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)


class NewTimerModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Create New Timer")

        self.name_input = discord.ui.TextInput(
            label="Timer Name", style=discord.TextStyle.short, required=True
        )
        self.interval_input = discord.ui.TextInput(
            label="Timer Interval (minutes)",
            style=discord.TextStyle.short,
            required=True,
        )
        self.message_input = discord.ui.TextInput(
            label="Timer Message",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )

        self.add_item(self.name_input)
        self.add_item(self.interval_input)
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.interval_input.value.isdigit():
            await interaction.response.send_message(
                "Timer interval must be a number!", ephemeral=True
            )
            return
        if int(self.interval_input.value) < 5:
            await interaction.response.send_message(
                "Timer interval must be at least 5 minutes!", ephemeral=True
            )
            return

        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "timers") as timer_data:
            if not timer_data:
                update_dict_defaults(DEFAULT_TIMER_DATA, timer_data)
            if len(timer_data) >= 25:
                await interaction.followup.send(
                    "Timer limit of 25 reached! Please delete a timer before creating a new one.",
                    ephemeral=True,
                )
                return
            if self.name_input.value in timer_data:
                await interaction.followup.send(
                    f"``{self.name_input.value}`` already exists!", ephemeral=True
                )
                return

            timer_data[self.name_input.value] = {
                "interval": int(self.interval_input.value) * 60,
                "message": self.message_input.value,
                "last_run": 0,
                "enabled": True,
                "channel_id": interaction.channel_id,
                "last_message_id": None,
            }

        await interaction.followup.send(
            f"New timer created:\n\n**Name**: ``{self.name_input.value}``\n**Interval**: ``{self.interval_input.value} Minutes``\n**Message**: ``{self.message_input.value}``",
            ephemeral=True,
        )


class EditTimerModal(discord.ui.Modal):
    def __init__(self, guild: discord.Guild, name: str):
        super().__init__(title="Edit Timer")

        self.timer_data = safe_read(COG, guild, "timers")

        self.original_name = name

        self.name_input = discord.ui.TextInput(
            label="Timer Name",
            style=discord.TextStyle.short,
            required=True,
            default=name,
        )
        self.interval_input = discord.ui.TextInput(
            label="Timer Interval (minutes)",
            style=discord.TextStyle.short,
            required=True,
            default=str(int(self.timer_data[name]["interval"] / 60)),
        )
        self.message_input = discord.ui.TextInput(
            label="Timer Message",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
            default=self.timer_data[name]["message"],
        )

        self.add_item(self.name_input)
        self.add_item(self.interval_input)
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.interval_input.value.isdigit():
            await interaction.response.send_message(
                "Timer interval must be a number!", ephemeral=True
            )
            return
        if int(self.interval_input.value) < 5:
            await interaction.response.send_message(
                "Timer interval must be at least 5 minutes!", ephemeral=True
            )
            return

        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "timers") as timer_data:
            if not timer_data:
                update_dict_defaults(DEFAULT_TIMER_DATA, timer_data)

            timer_data[self.original_name]["interval"] = int(self.interval_input.value) * 60
            timer_data[self.original_name]["message"] = self.message_input.value
            timer_data[self.name_input.value] = timer_data.pop(self.original_name)

        await interaction.followup.send(
            f"Timer edited:\n\n**Name**: ``{self.name_input.value}``\n**Interval**: ``{self.interval_input.value} Minutes``\n**Message**: ``{self.message_input.value}``",
            ephemeral=True,
        )


@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_messages=True)
class TimersCog(commands.GroupCog, name="timer"):
    def __init__(self, bot: Mammoth):
        self.bot = bot

        super().__init__()

        self.run_timers.start()

        log.info("Loaded")

    def cog_unload(self):
        self.run_timers.cancel()
        log.info("Unloaded")

    @tasks.loop(seconds=15)
    async def run_timers(self):
        for guild in self.bot.guilds:
            async with safe_edit(COG, guild, "timers") as timer_data:
                if not timer_data:
                    continue

                for timer in timer_data:
                    if not (channel := guild.get_channel(timer_data[timer]["channel_id"])):
                        continue
                    if channel.last_message_id == timer_data[timer]["last_message_id"]:
                        continue
                    if not timer_data[timer]["enabled"]:
                        continue
                    if (time.time() - timer_data[timer]["last_run"]) < (
                        timer_data[timer]["interval"]
                    ):
                        continue

                    try:
                        new_last_message = await channel.send(timer_data[timer]["message"])
                        old_last_message_id = timer_data[timer]["last_message_id"]
                        timer_data[timer]["last_message_id"] = new_last_message.id
                        timer_data[timer]["last_run"] = time.time()

                        if not old_last_message_id:
                            continue
                        if not (
                            last_message := await channel.fetch_message(
                                old_last_message_id
                            )
                        ):
                            continue

                        await last_message.delete()
                    except Exception:
                        log.error(traceback.format_exc())
                        continue

    @discord.app_commands.command(
        name="new",
        description="Create a new message timer.",
    )
    async def timer_new(self, interaction: discord.Interaction):
        await interaction.response.send_modal(NewTimerModal())

    @discord.app_commands.command(
        name="edit", description="Edit an existing message timer."
    )
    @discord.app_commands.describe(name="Name of the timer to edit.")
    async def timer_edit(self, interaction: discord.Interaction, name: str):
        guild = interaction.guild
        if not (timer_data := safe_read(COG, guild, "timers")) or not timer_data.get(
            name
        ):
            await interaction.response.send_message(f"``{name}`` does not exist!")
            return

        await interaction.response.send_modal(EditTimerModal(guild, name))

    @timer_edit.autocomplete("name")
    async def timer_edit_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        guild = interaction.guild
        timer_data = safe_read(COG, guild, "timers")

        return [
            discord.app_commands.Choice(name=name, value=name)
            for name in timer_data.keys()
            if current.lower() in name.lower()
        ]

    @discord.app_commands.command(name="delete", description="Delete a message timer.")
    @discord.app_commands.describe(
        name="Name of the timer to delete.",
    )
    async def timer_delete(self, interaction: discord.Interaction, name: str):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        async with safe_edit(COG, guild, "timers") as timer_data:
            if not timer_data:
                await interaction.followup.send(f"Timer ``{name}`` doesn't exist!")
                return
            if name not in timer_data:
                await interaction.followup.send(f"Timer ``{name}`` doesn't exist!")
                return

            del timer_data[name]

        await interaction.followup.send(f"Timer ``{name}`` deleted!")

    @timer_delete.autocomplete("name")
    async def timer_delete_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        guild = interaction.guild
        timer_data = safe_read(COG, guild, "timers")

        return [
            discord.app_commands.Choice(name=name, value=name)
            for name in timer_data.keys()
            if current.lower() in name.lower()
        ]

    @discord.app_commands.command(name="list", description="List all message timers.")
    async def timer_list(self, interaction: discord.Interaction):
        guild = interaction.guild

        await interaction.response.defer(thinking=True, ephemeral=True)

        if not (timer_data := safe_read(COG, guild, "timers")):
            await interaction.followup.send("No timers exist!")
            return

        await interaction.followup.send(
            f"**Timers**\n\n```\n{', '.join(timer_data.keys())}\n```"
        )


async def setup(bot: Mammoth):
    await bot.add_cog(TimersCog(bot))
