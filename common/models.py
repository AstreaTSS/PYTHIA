import os
import typing

import naff
from tortoise import fields
from tortoise.connection import connections
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model


# yes, this is a copy from common.utils
# but circular imports are a thing
def yesno_friendly_str(bool_to_convert):
    return "yes" if bool_to_convert == True else "no"


class SetField(ArrayField, set):
    """A somewhat exploity way of using an array field to store a set."""

    def to_python_value(self, value):
        value = None if value is None else set(value)
        self.validate(value)
        return value

    def to_db_value(self, value, _):
        self.validate(value)
        value = None if value is None else list(value)
        return value


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
    def chan_mention(self):
        return f"<#{self.channel_id}>"

    def __str__(self):  # sourcery skip: merge-list-append
        str_list = [
            f"`{self.name}` - in {self.chan_mention}",
            f"Aliases: {', '.join(f'`{a}`' for a in self.aliases)}",
        ]

        str_list.append(f"Found: {yesno_friendly_str(self.found)}")
        str_list.extend(
            (
                f"Finder: {f'<@{self.finder}>' if self.finder else 'N/A'}",
                "",
                f"Description: {self.description}",
            )
        )

        return "\n".join(str_list)

    def found_embed(self, username: str):
        embed = naff.Embed(
            title="Truth Bullet Discovered",
            timestamp=naff.Timestamp.utcnow(),
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


BULLET_QUERY_BY_NAME = f"""
SELECT *
FROM {TruthBullet.Meta.table}
WHERE channel_id = $1
AND (lower(name) = $2
OR (EXISTS (SELECT 1 FROM unnest(aliases) a WHERE lower(a) = $2)))
""".strip()

BULLET_EXISTS_BY_NAME = f"""
SELECT EXISTS(
    SELECT 1
    FROM {TruthBullet.Meta.table}
    WHERE channel_id=$1
    AND (lower(name)=$2
    OR (EXISTS (SELECT 1 FROM unnest(aliases) a WHERE lower(a)=$2)))
)
"""


async def get_bullet_from_name(channel_id: int, name: str):
    possible_bullet = await connections.get("default").execute_query(
        BULLET_QUERY_BY_NAME, [channel_id, name.lower()]
    )

    if possible_bullet[0] == 0:
        return None

    return TruthBullet(**possible_bullet[1][0])


async def bullet_exists_by_name(channel_id: int, name: str):
    result = await connections.get("default").execute_query(
        BULLET_EXISTS_BY_NAME, [channel_id, name.lower()]
    )

    return bool(result[0])
