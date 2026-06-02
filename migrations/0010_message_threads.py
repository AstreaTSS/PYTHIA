"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import migrations
from tortoise.migrations.operations import RunSQL


class Migration(migrations.Migration):
    dependencies = [("models", "0009_aliases_split")]

    initial = False

    operations = [
        RunSQL(
            sql="""
            ALTER TABLE "thiamessageconfig" ADD "mode" SMALLINT NOT NULL DEFAULT 1;
            ALTER TABLE "thiamessageconfig" ALTER COLUMN "mode" SET DEFAULT 2;
            CREATE TABLE IF NOT EXISTS "thiamessagethread" (
                "id" SERIAL PRIMARY KEY,
                "message_link_id" INTEGER NOT NULL REFERENCES "thiamessagelink" ("id") ON DELETE CASCADE,
                "user_id" BIGINT NOT NULL,
                "thread_id" BIGINT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS "thiamessagethread_message_link_id_idx" ON "thiamessagethread" ("message_link_id");
            CREATE INDEX IF NOT EXISTS "thiamessagethread_user_id_idx" ON "thiamessagethread" ("user_id");
            """.strip(),
            reverse_sql="""
            ALTER TABLE "thiamessageconfig" DROP COLUMN "mode";
            DROP TABLE IF EXISTS "thiamessagethread";
            """.strip(),
        )
    ]
