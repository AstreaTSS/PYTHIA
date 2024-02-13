"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

# use this to generate db if you need to
import os

from dotenv import load_dotenv
from tortoise import Tortoise, run_async

load_dotenv()


async def init() -> None:
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )
    await Tortoise.generate_schemas()


run_async(init())
