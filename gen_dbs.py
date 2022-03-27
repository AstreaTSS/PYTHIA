# use this to generate db if you need to
import os

import asyncpg
import ujson
from dotenv import load_dotenv
from tortoise import run_async
from tortoise import Tortoise

load_dotenv()


async def init():
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )
    await Tortoise.generate_schemas()


async def migrate():
    # a basic migration from byte-based sets to something more proper
    conn: asyncpg.Connection = await asyncpg.connect(os.environ.get("DB_URL"))

    async with conn.transaction():
        await conn.execute("ALTER TABLE uiconfig RENAME prefixes TO old_prefixes")
        await conn.execute(
            "ALTER TABLE uiconfig RENAME bullet_custom_perm_roles TO"
            " old_bullet_custom_perm_roles"
        )
        await conn.execute(
            "ALTER TABLE uiconfig ADD prefixes VARCHAR(40)[] DEFAULT '{}'"
        )
        await conn.execute(
            "ALTER TABLE uiconfig ADD bullet_custom_perm_roles BIGINT[] DEFAULT '{}'"
        )

        config_data = await conn.fetch("SELECT * from uiconfig")

        for config in config_data:
            new_prefixes = ujson.loads(config["old_prefixes"])
            new_bullet_custom_perm_roles = ujson.loads(
                config["old_bullet_custom_perm_roles"]
            )
            await conn.execute(
                "UPDATE uiconfig SET prefixes = $1, bullet_custom_perm_roles = $2",
                new_prefixes,
                new_bullet_custom_perm_roles,
            )

        await conn.execute("ALTER TABLE uiconfig DROP COLUMN old_prefixes")
        await conn.execute(
            "ALTER TABLE uiconfig DROP COLUMN old_bullet_custom_perm_roles"
        )

    await conn.close()


run_async(init())
