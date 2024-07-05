-- DropForeignKey
ALTER TABLE "thiaguildconfig" DROP CONSTRAINT "thiaguildconfig_guild_id_bullets_fkey";

-- AddForeignKey
ALTER TABLE "thianames" ADD CONSTRAINT "thianames_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaguildconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "thiabulletconfig" ADD CONSTRAINT "thiabulletconfig_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaguildconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;
