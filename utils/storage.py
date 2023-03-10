from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import logging
import asyncio
import os
import traceback
import discord
import json


log = logging.getLogger(__name__)


with open("./settings.json", "r") as r:
    SETTINGS = json.load(r)

DATA_PATH = SETTINGS["dataPath"]


def update_dict_defaults(defaults: dict, data_dict: dict):
    for key, value in defaults.items():
        if key not in data_dict:
            data_dict[key] = value


def safe_read(scope: str, guild: discord.Guild, key: str) -> dict:
    base_path = f"{DATA_PATH}/{scope}/{guild.id}"
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
async def safe_edit(scope: str, guild: discord.Guild, key: str) -> dict:
    base_path = f"{DATA_PATH}/{scope}/{guild.id}"
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
