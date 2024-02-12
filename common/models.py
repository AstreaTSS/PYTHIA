"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import os
import typing

import interactions as ipy
from tortoise import fields
from tortoise.connection import connections
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model


# yes, this is a copy from common.utils
# but circular imports are a thing
def yesno_friendly_str(bool_to_convert: bool) -> str:
    return "yes" if bool_to_convert else "no"


class SetField(ArrayField, set):
    """A somewhat exploity way of using an array field to store a set."""

    def to_python_value(self, value: typing.Any) -> typing.Optional[set]:
        value = None if value is None else set(value)
        self.validate(value)
        return value

    def to_db_value(
        self, value: typing.Optional[set], _: typing.Any
    ) -> typing.Optional[list]:
        self.validate(value)
        return None if value is None else list(value)


class TruthBullet(Model):
    class Meta:
        table = "uinewtruthbullets"
        indexes = (
            "name",
            "channel_id",
            "guild_id",
            "found",
        )

    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=100)
    aliases: set[str] = SetField("VARCHAR(40)")
    description: str = fields.TextField()
    channel_id: int = fields.BigIntField()
    guild_id: int = fields.BigIntField()
    found: bool = fields.BooleanField()  # type: ignore
    finder: typing.Optional[int] = fields.BigIntField(null=True)

    @property
    def chan_mention(self) -> str:
        return f"<#{self.channel_id}>"

    def bullet_info(self) -> str:
        str_list = [
            f"`{self.name}` - in {self.chan_mention}",
            f"Aliases: {', '.join(f'`{a}`' for a in self.aliases)}",
            f"Found: {yesno_friendly_str(self.found)}",
        ]

        str_list.extend((
            f"Finder: {f'<@{self.finder}>' if self.finder else 'N/A'}",
            "",
            f"Description: {self.description}",
        ))

        return "\n".join(str_list)

    def found_embed(self, username: str) -> ipy.Embed:
        embed = ipy.Embed(
            title="Truth Bullet Discovered",
            timestamp=ipy.Timestamp.utcnow(),
            color=int(os.environ["BOT_COLOR"]),
        )
        embed.description = (
            f"`{self.name}` - from {self.chan_mention}\n\n{self.description}"
        )

        footer = f"Found by {username}" if self.finder else "To be found as of"
        embed.set_footer(text=footer)

        return embed


class Config(Model):
    class Meta:
        table = "uinewconfig"

    guild_id: int = fields.BigIntField(pk=True)
    bullet_chan_id: typing.Optional[int] = fields.BigIntField(null=True)
    ult_detective_role: typing.Optional[int] = fields.BigIntField(null=True)
    player_role: typing.Optional[int] = fields.BigIntField(null=True)
    bullets_enabled: bool = fields.BooleanField(default=False)  # type: ignore


async def find_truth_bullet(
    channel_id: ipy.Snowflake_Type, content: str
) -> typing.Optional[TruthBullet]:
    conn = connections.get("default")

    result = await conn.execute_query(
        f"SELECT {', '.join(TruthBullet._meta.fields)} FROM"  # noqa: S608
        f" {TruthBullet.Meta.table} WHERE channel_id=$1 AND ((position(LOWER(name) in"
        " LOWER($2)))>0 OR 0 < ANY(SELECT position(LOWER(UNNEST(aliases)) in"
        " LOWER($2))));",
        [int(channel_id), content],
    )

    try:
        return None if result[0] <= 0 else TruthBullet(**dict(result[1][0]))
    except (KeyError, IndexError, ValueError):
        return None
