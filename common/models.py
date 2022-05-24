import naff
from tortoise import fields
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
        table = "uitruthbullets"

    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=100)
    aliases: set[str] = SetField("VARCHAR(40)")
    description: str = fields.TextField()
    channel_id: int = fields.BigIntField()
    guild_id: int = fields.BigIntField()
    found: bool = fields.BooleanField()
    finder: int = fields.BigIntField()

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
                f"Finder: {f'<@{self.finder}>' if self.finder > 0 else 'N/A'}",
                "",
                f"Description: {self.description}",
            )
        )

        return "\n".join(str_list)

    def found_embed(self, username):
        embed = naff.Embed(
            title="Truth Bullet Discovered",
            timestamp=naff.Timestamp.utcnow(),
            color=14232643,
        )
        embed.description = (
            f"`{self.name}` - from {self.chan_mention}\n\n{self.description}"
        )

        footer = "To be found as of" if self.finder is None else f"Found by {username}"
        embed.set_footer(text=footer)

        return embed


class Config(Model):
    class Meta:
        table = "uiconfig"

    id: int = fields.IntField(pk=True)
    guild_id: int = fields.BigIntField()
    bullet_chan_id: int = fields.BigIntField()
    ult_detective_role: int = fields.BigIntField()
    player_role: int = fields.BigIntField()
    bullets_enabled: bool = fields.BooleanField(default=False)
    prefixes: set[str] = SetField("VARCHAR(40)")
    bullet_default_perms_check: bool = fields.BooleanField(default=True)
    bullet_custom_perm_roles: set[int] = SetField("BIGINT")
