from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from utils.debug import DebugPrinter
import asyncio
import os
import discord
import pickle
import json


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)

DATA_PATH = SETTINGS["dataPath"]


spam_debug_printer = DebugPrinter(__name__, SETTINGS["spammyDebugPrinting"])
sdprint = spam_debug_printer.dprint


class StorageObject:
    def __init__(self):
        self.value = None

        self.created = datetime.now()
        self.last_edit = None

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.last_edit = datetime.now()


def safe_read(cog: str, guild: discord.Guild, key: str):
    base_path = f"{DATA_PATH}/{cog}/{guild.id}"
    file_path = f"{base_path}/{key}.pickle"

    sdprint(f"Read-only request for [{file_path}]")

    """ Load the storage object """

    sdprint(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        sdprint(f"File was not found [{file_path}], creating empty StorageObject")

        storage_object = StorageObject()
    else:
        try:
            with open(file_path, "rb") as rb:
                loaded_object = pickle.load(rb)
        except Exception as e:
            sdprint(f"Failed to load [{file_path}]\n\n{e}\n")

            loaded_object = StorageObject()

        if not isinstance(loaded_object, StorageObject):
            sdprint(
                f"File is not StorageObject [{file_path}], creating empty StorageObject"
            )

            storage_object = StorageObject()

        sdprint(f"Loaded [{file_path}]")

        storage_object = loaded_object

    """ Return the storage object """

    sdprint(f"Returning [{file_path}]")
    return storage_object


@asynccontextmanager
async def safe_edit(cog: str, guild: discord.Guild, key: str):
    base_path = f"{DATA_PATH}/{cog}/{guild.id}"
    file_path = f"{base_path}/{key}.pickle"

    sdprint(f"Edit request opened for [{file_path}]")

    """ Wait until the file is not locked """

    while os.path.exists(f"{file_path}.lock"):
        sdprint(f"File is locked [{file_path}], waiting...")

        await asyncio.sleep(1)

    """ Load the storage object """

    sdprint(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        sdprint(f"File was not found [{file_path}], creating empty StorageObject")

        storage_object = StorageObject()
    else:
        try:
            with open(file_path, "rb") as rb:
                loaded_object = pickle.load(rb)
        except Exception as e:
            sdprint(f"Failed to load [{file_path}]\n\n{e}\n")

            loaded_object = StorageObject()

        if not isinstance(loaded_object, StorageObject):
            sdprint(
                f"File is not StorageObject [{file_path}], creating empty StorageObject"
            )

            storage_object = StorageObject()

        sdprint(f"Loaded [{file_path}]")

        storage_object = loaded_object

    """ Lock storage object """

    sdprint(f"Locking [{file_path}]...")

    try:
        Path(f"{file_path}.lock").touch()
        sdprint(f"Locked [{file_path}]")
    except Exception as e:
        sdprint(f"Failed to lock [{file_path}]\n\n{e}\n")

    """ Yield the storage object """

    try:
        sdprint(f"Yielding [{file_path}]")
        yield storage_object
    except Exception as e:
        sdprint(f"An error occurred while yielding [{file_path}]\n\n{e}\n")
    finally:

        """Save the storage object"""

        sdprint(f"Saving [{file_path}]...")

        try:
            with open(file_path, "wb") as wb:
                pickle.dump(storage_object, wb)

                sdprint(f"Saved [{file_path}]")
        except Exception as e:
            sdprint(f"Failed to save [{file_path}]\n\n{e}\n")
        finally:

            """Unlock the storage object"""

            sdprint(f"Unlocking [{file_path}]...")

            try:
                os.remove(f"{file_path}.lock")
                sdprint(f"Unlocked [{file_path}]")
            except Exception as e:
                sdprint(f"Failed to unlock [{file_path}]\n\n{e}\n")
