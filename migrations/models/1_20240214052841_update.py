"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "uinewconfig" RENAME COLUMN "ult_detective_role" TO "best_bullet_finder_role";
        ALTER TABLE "uinewtruthbullets" RENAME COLUMN "name" TO "trigger";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "uinewconfig" RENAME COLUMN "best_bullet_finder_role" TO "ult_detective_role";
        ALTER TABLE "uinewtruthbullets" RENAME COLUMN "trigger" TO "name";"""
