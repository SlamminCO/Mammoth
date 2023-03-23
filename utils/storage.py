from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import logging
import asyncio
import os
import traceback
import discord
import json
import pickle


log = logging.getLogger(__name__)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)

CURRENT_STORAGE_VERSION = 1
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


def migrate_zero_to_one():
    log.info("Migrating storage from version 0 to 1")

    for scope in os.listdir(DATA_PATH):
        if scope in "global" or os.path.isfile(f"{DATA_PATH}/{scope}"):
            continue

        root_path = f"{DATA_PATH}/{scope}"

        for guild_id in os.listdir(root_path):
            base_path = f"{root_path}/{guild_id}"

            for file_name in os.listdir(base_path):
                if not file_name.endswith(".pickle"):
                    continue

                file_path = f"{base_path}/{file_name}"

                data = read_version_zero_data(base_path, file_path).get()

                new_file_path = file_path.replace(".pickle", ".json")

                try:
                    with open(new_file_path, "w") as w:
                        json.dump(data, w, indent=4)
                except Exception:
                    log.error(f"Failed to migrate [{file_path}] from version 0 to 1!")
                    log.exception(traceback.format_exc())

    with open(f"{DATA_PATH}/version.json", "w") as w:
        json.dump({"version": 1}, w, indent=4)

    log.info("Migrated storage from version 0 to 1")


def read_version_zero_data(base_path, file_path):
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
        except Exception as e:
            log.debug(f"Failed to load [{file_path}]\n\n{e}\n")

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


def migrate_storage():
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH, exist_ok=True)

    if not os.path.exists(f"{DATA_PATH}/version.json"):
        with open(f"{DATA_PATH}/version.json", "w") as w:
            json.dump({"version": 0}, w, indent=4)

    with open(f"{DATA_PATH}/version.json", "r") as r:
        storage_version_data = json.load(r)

    if storage_version_data["version"] == CURRENT_STORAGE_VERSION:
        return

    if storage_version_data["version"] == 0:
        migrate_zero_to_one()
        return migrate_storage()


def update_dict_defaults(defaults: dict, data_dict: dict):
    for key, value in defaults.items():
        if key not in data_dict:
            data_dict[key] = value


def safe_read(scope: str, identifier: discord.Guild | int, key: str) -> dict:
    guild_id = identifier.id if isinstance(identifier, discord.Guild) else identifier
    base_path = f"{DATA_PATH}/{scope}/{guild_id}"
    file_path = f"{base_path}/{key}.json"

    log.debug(f"Read-only request for [{file_path}]")
    log.debug(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        log.debug(f"File was not found [{file_path}]")

        data_dict: dict = {}
    else:
        try:
            with open(file_path, "r") as r:
                data_dict: dict = json.load(r)
        except Exception:
            log.exception(traceback.format_exc())

            data_dict: dict = {}

        log.debug(f"Loaded [{file_path}]")

    log.debug(f"Returning [{file_path}]")
    return data_dict


@asynccontextmanager
async def safe_edit(scope: str, identifier: discord.Guild | int, key: str) -> dict:
    guild_id = identifier.id if isinstance(identifier, discord.Guild) else identifier
    base_path = f"{DATA_PATH}/{scope}/{guild_id}"
    file_path = f"{base_path}/{key}.json"

    log.debug(f"Edit request opened for [{file_path}]")

    while os.path.exists(f"{file_path}.lock"):
        log.debug(f"File is locked [{file_path}], waiting...")

        await asyncio.sleep(1)

    log.debug(f"Loading [{file_path}]...")

    if not os.path.exists(file_path):
        os.makedirs(base_path, exist_ok=True)
        log.debug(f"File was not found [{file_path}]")

        data_dict: dict = {}
    else:
        try:
            with open(file_path, "r") as r:
                data_dict: dict = json.load(r)
        except Exception:
            log.exception(traceback.format_exc())

            data_dict: dict = {}

        log.debug(f"Loaded [{file_path}]")

    log.debug(f"Locking [{file_path}]...")

    try:
        Path(f"{file_path}.lock").touch()
        log.debug(f"Locked [{file_path}]")
    except Exception:
        log.exception(traceback.format_exc())

    try:
        log.debug(f"Yielding [{file_path}]")
        yield data_dict
    except Exception:
        log.exception(traceback.format_exc())
    finally:
        log.debug(f"Saving [{file_path}]...")

        try:
            with open(file_path, "w") as w:
                json.dump(data_dict, w, indent=4)
                log.debug(f"Saved [{file_path}]")
        except Exception:
            log.exception(traceback.format_exc())
        finally:
            log.debug(f"Unlocking [{file_path}]...")

            try:
                os.remove(f"{file_path}.lock")
                log.debug(f"Unlocked [{file_path}]")
            except Exception:
                log.exception(traceback.format_exc())
