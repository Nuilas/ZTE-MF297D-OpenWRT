#!/bin/sh
set -eu
cd /tmp/mf297d-install
test "$(uname -r)" = 6.18.55
grep -q mf297d.storage_expand=1 /proc/cmdline
test "$(cat /sys/class/mtd/mtd21/name)" = maintenance_storage
test "$(cat /sys/class/mtd/mtd21/flags)" = 0x400
test "$(cat /sys/class/mtd/mtd10/flags)" = 0x400
! grep -q ' ubifs ' /proc/mounts
sha256sum -c SHA256SUMS
hash() { sha256sum "$1" | cut -d' ' -f1; }
test "$(hash /dev/mtd10ro)" = '@ENV_BEFORE@'
test ! -e /sys/class/ubi/ubi0/mtd_num
sha256sum -c prefix.before.sha256
touch /tmp/mf297d-source-keep
./env-helper --selftest
./env-helper --check
ubiattach /dev/ubi_ctrl -m 21 -d 0
test "$(hash /dev/ubi0_4)" = '@OLD_KERNEL@'
test "$(hash /dev/ubi0_5)" = '@OLD_ROOT@'
test "$(hash /dev/ubi0_7)" = '@RECOVERY@'
test "$(hash /dev/ubi0_1)" = '@CONTROLLER1@'
test "$(hash /dev/ubi0_2)" = '@CONTROLLER2@'
test "$(cat /sys/class/ubi/ubi0/volumes_count)" = 6
test "$(cat /sys/class/ubi/ubi0/reserved_for_bad)" = 40
ubidetach /dev/ubi_ctrl -d 0
# New main CRC keeps the old main from booting during the transaction.
./env-helper --install
test "$(hash /dev/mtd10ro)" = '@ENV_AFTER@'
ubiattach /dev/ubi_ctrl -m 21 -d 0
ubirmvol /dev/ubi0 -n 6
ubirmvol /dev/ubi0 -n 5
ubirmvol /dev/ubi0 -n 4
ubimkvol /dev/ubi0 -n 4 -N owrt_kernel -t static -S @KLEBS@
ubimkvol /dev/ubi0 -n 5 -N owrt_rootfs -t static -S @RLEBS@
ubimkvol /dev/ubi0 -n 6 -N rootfs_data -t dynamic -S @OLEBS@
ubiupdatevol /dev/ubi0_5 rootfs.bin
test "$(hash /dev/ubi0_5)" = '@NEW_ROOT@'
ubiupdatevol /dev/ubi0_6 overlay.ubifs
mkdir -p /tmp/mf297d-overlay-check
mount -t ubifs -o ro /dev/ubi0_6 /tmp/mf297d-overlay-check
test "$(cat /tmp/mf297d-overlay-check/upper/etc/mf297d-nss-install-proof)" = '@PROOF@'
umount /tmp/mf297d-overlay-check
ubiupdatevol /dev/ubi0_4 kernel.bin
test "$(hash /dev/ubi0_4)" = '@NEW_KERNEL@'
test "$(hash /dev/ubi0_7)" = '@RECOVERY@'
test "$(hash /dev/ubi0_1)" = '@CONTROLLER1@'
test "$(hash /dev/ubi0_2)" = '@CONTROLLER2@'
test "$(hash /dev/mtd10ro)" = '@ENV_AFTER@'
grep -v '/dev/mtd10ro$' prefix.before.sha256 | sha256sum -c -
sync
ubidetach /dev/ubi_ctrl -d 0
printf 'Kernel/rootfs/overlay dogrulandi; yeniden baslatiliyor.\n'
reboot
