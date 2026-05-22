"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import logging
import os
import traceback
from pathlib import Path

import aiohttp
import discord
import sentry_sdk
import typing_extensions as typing

from common.core import *

OS_TRUE_VALUES = frozenset({"true", "True", "TRUE", "t", "T", "1"})
SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore
VOTING_ENABLED = bool(os.environ.get("TOP_GG_TOKEN") or os.environ.get("DBL_TOKEN"))
DOCKER_ENABLED = os.environ.get("DOCKER_MODE") in OS_TRUE_VALUES
BOT_COLOR = discord.Color(int(os.environ["BOT_COLOR"]))
MAX_DICE_ENTRIES: typing.Final[int] = 50

logger = logging.getLogger("discord")


def parse_hex_number(hex_number: str) -> discord.Color:
    if hex_number.startswith("#"):
        hex_number = hex_number[1:]

    arg = "".join(i * 2 for i in hex_number) if len(hex_number) == 3 else hex_number
    value = int(arg, base=16)
    return discord.Color(value=value)


def file_to_ext(str_path: str, base_path: str) -> str:
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path: str, folder: str = "exts") -> list[str]:
    # gets all extensions in a folder
    ext_files: list[str] = []
    location_split = str_path.split(folder)
    base_path = location_split[0]

    if base_path == str_path:
        base_path = base_path.replace("main.py", "")
    base_path = base_path.replace("\\", "/")

    if base_path[-1] != "/":
        base_path += "/"

    pathlist = Path(f"{base_path}/{folder}").glob("**/*.py")
    for path in pathlist:
        str_path = str(path.as_posix())
        str_path = file_to_ext(str_path, base_path)
        ext_files.append(str_path)

    return ext_files


def quick_view(
    *items: discord.ui.ViewItem,
) -> discord.ui.View:
    class CustomView(discord.ui.View):
        pass

    return CustomView(*items, store=False)


def quick_designer_view(
    *items: discord.ui.ViewItem,
) -> discord.ui.DesignerView:
    class CustomDesignerView(discord.ui.DesignerView):
        pass

    return CustomDesignerView(*items, store=False)


def error_view_generate(error_msg: str) -> discord.ui.DesignerView:
    return quick_designer_view(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# Error\n{error_msg}"),
            color=parse_hex_number("#FF9800"),
        )
    )


async def error_handle(
    error: Exception, *, ctx: THIABridgeContext | discord.Interaction | None = None
) -> None:
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        if SENTRY_ENABLED:
            scope = sentry_sdk.Scope.get_current_scope()
            if ctx:
                scope.set_context(
                    type(ctx).__name__,
                    {
                        "args": ctx.args,  # type: ignore
                        "kwargs": ctx.kwargs,  # type: ignore
                        "message": ctx.message,
                    },
                )
            sentry_sdk.capture_exception(error)
        else:
            traceback.print_exception(error)
            logger.error("An error occured.", exc_info=error)
    if ctx and isinstance(
        ctx,
        (THIABridgeApplicationContext, THIABridgeExtContext, discord.Interaction),
    ):
        await ctx.respond(
            view=error_view_generate(
                "An internal error has occured. The bot owner has been notified and"
                " will likely fix the issue soon."
            )
        )


class CustomCheckFailure(discord.CheckFailure):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass
