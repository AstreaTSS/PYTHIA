"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise.migrations.operations import RunSQL
from tortoise.migrations.migration import Migration


class Migration(Migration):
    dependencies = [("models", "0004_rarity_index")]

    operations = [
        RunSQL(
            sql="""ALTER TABLE "thiabulletconfig" ADD "thread_behavior" SMALLINT NOT NULL DEFAULT 1;
                    COMMENT ON COLUMN "thiabulletconfig"."thread_behavior" IS 'DISTINCT: 1\nPARENT: 2';""",
            reverse_sql="""ALTER TABLE "thiabulletconfig" DROP COLUMN "thread_behavior";""",
        )
    ]
