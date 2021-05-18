# use this to generate db if you need to
from tortoise import run_async
from tortoise import Tortoise


async def init():
    await Tortoise.init(
        db_url="sqlite://db.sqlite3", modules={"models": ["common.models"]}
    )
    await Tortoise.generate_schemas()


run_async(init())
