"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thiabulletconfig" ADD "thread_behavior" SMALLINT NOT NULL DEFAULT 1;
        COMMENT ON COLUMN "thiabulletconfig"."thread_behavior" IS 'DISTINCT: 1\nPARENT: 2';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thiabulletconfig" DROP COLUMN "thread_behavior";"""


MODELS_STATE = (
    "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"
    "qm7cws2gpt4OjqZf1//ADDfQ=="
)
