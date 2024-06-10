/*
  Warnings:

  - A unique constraint covering the columns `[names_id]` on the table `uinewconfig` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "uinewconfig" ADD COLUMN     "names_id" INTEGER;

-- CreateTable
CREATE TABLE "PrismaNames" (
    "id" SERIAL NOT NULL,
    "singular_bullet" TEXT NOT NULL DEFAULT 'Truth Bullet',
    "plural_bullet" TEXT NOT NULL DEFAULT 'Truth Bullets',
    "singular_truth_bullet_finder" TEXT NOT NULL DEFAULT '{{bullet_name}} Finder',
    "plural_truth_bullet_finder" TEXT NOT NULL DEFAULT '{{bullet_name}} Finders',
    "best_bullet_finder" TEXT NOT NULL DEFAULT 'Best {{bullet_finder}}',

    CONSTRAINT "PrismaNames_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "uinewconfig_names_id_key" ON "uinewconfig"("names_id");

-- AddForeignKey
ALTER TABLE "uinewconfig" ADD CONSTRAINT "uinewconfig_names_id_fkey" FOREIGN KEY ("names_id") REFERENCES "PrismaNames"("id") ON DELETE CASCADE ON UPDATE CASCADE;
