from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import logging
import asyncio
import os
import traceback
import discord
import pickle
import json


log = logging.getLogger(__name__)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)

DATA_PATH = SETTINGS["dataPath"]


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


def safe_read(scope: str, guild: discord.Guild, key: str):
    base_path = f"{DATA_PATH}/{scope}/{guild.id}"
    file_path = f"{base_path}/{key}.pickle"

    log.debug(f"Read-only request for [{file_path}]")

    """ Load the storage object """

    log.debug(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        log.debug(f"File was not found [{file_path}], creating empty StorageObject")

        storage_object = StorageObject()
    else:
        try:
            with open(file_path, "rb") as rb:
                loaded_object = pickle.load(rb)
        except Exception:
            log.exception(traceback.format_exc())

            loaded_object = StorageObject()

        if not isinstance(loaded_object, StorageObject):
            log.debug(
                f"File is not StorageObject [{file_path}], creating empty StorageObject"
            )

            storage_object = StorageObject()

        log.debug(f"Loaded [{file_path}]")

        storage_object = loaded_object

    """ Return the storage object """

    log.debug(f"Returning [{file_path}]")
    return storage_object


@asynccontextmanager
async def safe_edit(scope: str, guild: discord.Guild, key: str):
    base_path = f"{DATA_PATH}/{scope}/{guild.id}"
    file_path = f"{base_path}/{key}.pickle"

    log.debug(f"Edit request opened for [{file_path}]")

    """ Wait until the file is not locked """

    while os.path.exists(f"{file_path}.lock"):
        log.debug(f"File is locked [{file_path}], waiting...")

        await asyncio.sleep(1)

    """ Load the storage object """

    log.debug(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        log.debug(f"File was not found [{file_path}], creating empty StorageObject")

        storage_object = StorageObject()
    else:
        try:
            with open(file_path, "rb") as rb:
                loaded_object = pickle.load(rb)
        except Exception:
            log.exception(traceback.format_exc())

            loaded_object = StorageObject()

        if not isinstance(loaded_object, StorageObject):
            log.debug(
                f"File is not StorageObject [{file_path}], creating empty StorageObject"
            )

            storage_object = StorageObject()

        log.debug(f"Loaded [{file_path}]")

        storage_object = loaded_object

    """ Lock storage object """

    log.debug(f"Locking [{file_path}]...")

    try:
        Path(f"{file_path}.lock").touch()
        log.debug(f"Locked [{file_path}]")
    except Exception:
        log.exception(traceback.format_exc())

    """ Yield the storage object """

    try:
        log.debug(f"Yielding [{file_path}]")
        yield storage_object
    except Exception:
        log.exception(traceback.format_exc())
    finally:
        """Save the storage object"""

        log.debug(f"Saving [{file_path}]...")

        try:
            with open(file_path, "wb") as wb:
                pickle.dump(storage_object, wb)

                log.debug(f"Saved [{file_path}]")
        except Exception:
            log.exception(traceback.format_exc())
        finally:
            """Unlock the storage object"""

            log.debug(f"Unlocking [{file_path}]...")

            try:
                os.remove(f"{file_path}.lock")
                log.debug(f"Unlocked [{file_path}]")
            except Exception:
                log.exception(traceback.format_exc())
