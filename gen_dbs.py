"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

# use this to generate db if you need to
# for docker - docker compose run bot python gen_dbs.py
from tortoise import Tortoise, run_async

from db_settings import TORTOISE_ORM


async def init() -> None:
    await Tortoise.init(TORTOISE_ORM)
    await Tortoise.generate_schemas()


run_async(init())
