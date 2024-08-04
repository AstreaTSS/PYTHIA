-- CreateTable
CREATE TABLE "thiamessagelink" (
    "id" SERIAL NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "user_id" BIGINT NOT NULL,
    "channel_id" BIGINT NOT NULL,

    CONSTRAINT "thiamessagelink_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "thiamessageconfig" (
    "guild_id" BIGINT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "anon_enabled" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "thiamessageconfig_pkey" PRIMARY KEY ("guild_id")
);

-- CreateIndex
CREATE INDEX "thiamessagelink_guild_id_idx" ON "thiamessagelink"("guild_id");

-- CreateIndex
CREATE INDEX "thiamessagelink_guild_id_user_id_idx" ON "thiamessagelink"("guild_id", "user_id");

-- AddForeignKey
ALTER TABLE "thiamessagelink" ADD CONSTRAINT "thiamessagelink_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiamessageconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "thiamessageconfig" ADD CONSTRAINT "thiamessageconfig_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaguildconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;
