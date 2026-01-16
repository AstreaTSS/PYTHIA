"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import re
import textwrap

import typing_extensions as typing
from tortoise import Model

__all__ = (
    "code_template",
    "generate_regexp",
    "guild_id_model",
    "short_desc",
    "yesno_friendly_str",
)


# yes, this is a copy from common.utils
# but circular imports are a thing
def yesno_friendly_str(bool_to_convert: bool) -> str:
    return "yes" if bool_to_convert else "no"


def generate_regexp(attribute: str) -> str:
    return rf"regexp_replace({attribute}, '([\%_])', '\\\1', 'g')"


TEMPLATE_MARKDOWN = re.compile(r"({{(.*)}})")


def code_template(value: str) -> str:
    return TEMPLATE_MARKDOWN.sub(r"`\1`", value)


def short_desc(description: str, length: int = 25) -> str:
    new_description = textwrap.shorten(description, length, placeholder="...")
    if new_description == "...":  # word is too long, lets manually cut it
        return f"{description[:length-3].strip()}..."
    return new_description


def new_init(old_init: typing.Callable) -> typing.Callable:
    def wrapper(self: Model, *args: typing.Any, **kwargs: typing.Any) -> None:
        guild_id = kwargs.pop("guild_id", None)
        old_init(self, *args, **kwargs)
        if guild_id is not None:
            self.guild_id = guild_id

    return wrapper


MODEL_T = typing.TypeVar("MODEL_T", bound=Model)


def guild_id_model(cls: type[MODEL_T]) -> type[MODEL_T]:
    cls._meta.fields_db_projection["guild_id"] = "guild_id"
    cls.__init__ = new_init(cls.__init__)
    return cls
