"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import logging
import os
import platform
import re
import traceback
from pathlib import Path

import aiohttp
import discord
import sentry_sdk
import typing_extensions as typing
from discord.ext import commands

from common.core import *

OS_TRUE_VALUES = frozenset({"true", "True", "TRUE", "t", "T", "1"})
SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore
VOTING_ENABLED = bool(os.environ.get("TOP_GG_TOKEN") or os.environ.get("DBL_TOKEN"))
DOCKER_ENABLED = os.environ.get("DOCKER_MODE") in OS_TRUE_VALUES
BOT_COLOR = discord.Color(int(os.environ["BOT_COLOR"]))
MAX_DICE_ENTRIES: typing.Final[int] = 50
PYTHON_VERSION = platform.python_version_tuple()
PYTHON_IMPLEMENTATION = platform.python_implementation()

logger = logging.getLogger("discord")

CogT = typing.TypeVar("CogT", bound=discord.Cog)

SINGLE_QUOTE_REGEX = re.compile(r"‘|’")  # noqa: RUF001
DOUBLE_QUOTE_REGEX = re.compile(r"“|”|„|‟|⹂|〝|〞|＂")  # noqa: RUF001


def toggle_friendly_str(bool_to_convert: bool) -> typing.Literal["on", "off"]:
    return "on" if bool_to_convert else "off"


def yesno_friendly_str(bool_to_convert: bool) -> typing.Literal["yes", "no"]:
    return "yes" if bool_to_convert else "no"


def replace_smart_punc(text: str) -> str:
    text = SINGLE_QUOTE_REGEX.sub("'", text)
    return DOUBLE_QUOTE_REGEX.sub('"', text)


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


def quick_model(
    *items: discord.ui.ModalItem,
    title: str,
    custom_id: str,
) -> discord.ui.DesignerModal:
    class CustomModal(discord.ui.DesignerModal):
        pass

    return CustomModal(*items, title=title, custom_id=custom_id, store=False)


def make_container(
    description: str, *, title: str | None = None
) -> discord.ui.Container:
    return discord.ui.Container(
        discord.ui.TextDisplay(
            description if not title else f"# {title}\n{description}"
        ),
        color=BOT_COLOR,
    )


def make_view(description: str, *, title: str | None = None) -> discord.ui.DesignerView:
    return quick_designer_view(
        make_container(description, title=title),
    )


def error_view(error_msg: str) -> discord.ui.DesignerView:
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
            view=error_view(
                "An internal error has occured. The bot owner has been notified and"
                " will likely fix the issue soon."
            )
        )


def modal_handler(
    custom_id: str | None = None,
    custom_id_prefix: str | None = None,
) -> typing.Callable[
    [
        typing.Callable[
            [CogT, Interaction, dict[str, typing.Any]], typing.Awaitable[None]
        ]
    ],
    typing.Callable[[CogT, Interaction], typing.Awaitable[None]],
]:
    if not custom_id and not custom_id_prefix:
        raise ValueError("Either custom_id or custom_id_prefix must be provided.")
    if custom_id and custom_id_prefix:
        raise ValueError("custom_id and custom_id_prefix cannot both be provided.")

    def inner(
        func: typing.Callable[
            [CogT, Interaction, dict[str, typing.Any]], typing.Awaitable[None]
        ],
    ) -> typing.Callable[[CogT, Interaction], typing.Awaitable[None]]:
        async def wrapper(self: CogT, inter: Interaction) -> None:
            if inter.type != discord.InteractionType.modal_submit or not inter.data:
                return

            if custom_id and inter.data["custom_id"] != custom_id:
                return
            if custom_id_prefix and not inter.data["custom_id"].startswith(
                custom_id_prefix
            ):
                return

            responses: dict[str, typing.Any] = {}

            for component in inter.data["components"]:
                if component["type"] == discord.ComponentType.action_row:
                    # old style modals
                    responses[component["components"][0]["custom_id"]] = component[
                        "components"
                    ][0]["value"]
                    continue

                # we can assume it's a label component
                held_component = component["component"]

                if held_component["type"] in (
                    discord.ComponentType.string_select,
                    discord.ComponentType.user_select,
                    discord.ComponentType.role_select,
                    discord.ComponentType.channel_select,
                    discord.ComponentType.mentionable_select,
                ):
                    # ...let's just let pycord handle this
                    fake_select = discord.ui.Select(held_component["type"])
                    fake_select.refresh_from_modal(inter, held_component)
                    responses[held_component["custom_id"]] = fake_select.values
                elif held_component["type"] == discord.ComponentType.file_upload:
                    # ...and this
                    fake_file = discord.ui.FileUpload()
                    fake_file.refresh_from_modal(inter, held_component)
                    responses[held_component["custom_id"]] = fake_file.values
                elif held_component.get("values") is not None:
                    responses[held_component["custom_id"]] = held_component["values"]
                else:
                    responses[held_component["custom_id"]] = held_component.get("value")

            try:
                await func(
                    self,
                    inter,
                    responses,
                )
            except Exception as error:
                inter.client.dispatch("modal_error", error, inter)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return discord.Cog.listener("on_interaction")(wrapper)

    return inner


class ReplaceSmartPuncConverter(commands.Converter):
    async def convert(self, _: THIABridgeContext, argument: str) -> str:
        return replace_smart_punc(argument)


class CustomCheckFailure(discord.CheckFailure):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass
