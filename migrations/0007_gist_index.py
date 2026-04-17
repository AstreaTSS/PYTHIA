"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.migrations.operations import RunSQL


class Migration(migrations.Migration):
    dependencies = [("models", "0005_thread_behavior"), ("models", "0006_add_beta")]

    initial = False

    operations = [
        RunSQL(
            sql="""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            ALTER TABLE "thiatruthbullets" ALTER COLUMN "trigger" TYPE TEXT;

            DROP INDEX IF EXISTS thiagachaitems_name_idx;
            DROP INDEX IF EXISTS thiaitemssystemitems_name_idx;

            CREATE INDEX thiatruthbullets_trigger_idx ON "thiatruthbullets" USING GIST (trigger gist_trgm_ops);
            CREATE INDEX thiagachaitems_name_idx ON "thiagachaitems" USING GIST (name gist_trgm_ops);
            CREATE INDEX thiadicenetry_name_idx ON "thiadicenetry" USING GIST (name gist_trgm_ops);
            CREATE INDEX thiaitemssystemitems_name_idx ON "thiaitemssystemitems" USING GIST (name gist_trgm_ops);
            """.strip(),
            reverse_sql="""
            DROP INDEX IF EXISTS thiatruthbullets_trigger_idx;
            DROP INDEX IF EXISTS thiagachaitems_name_idx;
            DROP INDEX IF EXISTS thiadicenetry_name_idx;
            DROP INDEX IF EXISTS thiaitemssystemitems_name_idx;

            ALTER TABLE "thiatruthbullets" ALTER COLUMN "trigger" TYPE VARCHAR(100);
            DROP EXTENSION IF EXISTS pg_trgm;
            """.strip(),
        )
    ]
