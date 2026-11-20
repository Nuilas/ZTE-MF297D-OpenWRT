#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
cd "$(dirname "$0")"
grep -q 'root=/dev/ram0' /proc/cmdline
grep -q 'mf297d.install_stock=2' /proc/cmdline
grep -q 'mf297d.owner_token=@TOKEN@' /proc/cmdline
[ "$(uname -r)" = 6.18.60 ]
[ "$(cat /tmp/sysinfo/board_name)" = zte,mf297d ]
[ "$(cat RESET-PERMIT)" = @TOKEN@ ]
[ "$(cat /sys/class/mtd/mtd21/name)" = maintenance_storage ]
[ "$(cat /sys/class/mtd/mtd21/size)" = 221511680 ]
[ "$(cat /sys/class/mtd/mtd10/flags)" = 0x0 ]
! grep -q ' ubifs ' /proc/mounts
[ ! -e /sys/class/ubi/ubi0/mtd_num ]
sha256sum -c SHA256SUMS
sha256sum -c prefix.after.sha256
[ "$(sha256sum /dev/mtd10ro | cut -d' ' -f1)" = @ENV_AFTER@ ]
lower=$(dd if=/dev/mtd21ro bs=131072 count=464 2>/dev/null | sha256sum | cut -d' ' -f1)
[ "$lower" = "$(cat LOWER-SHA256)" ]
./erase-tail --check
./erase-tail --erase-tail
# Reject any controller address alias: original 58MiB UBI and prefix must match.
[ "$(dd if=/dev/mtd21ro bs=131072 count=464 2>/dev/null | sha256sum | cut -d' ' -f1)" = "$lower" ]
sha256sum -c prefix.after.sha256
ubiattach /dev/ubi_ctrl -m 21 -d 0
[ "$(cat /sys/class/ubi/ubi0/volumes_count)" = 5 ]
[ "$(sha256sum /dev/ubi0_7 | cut -d' ' -f1)" = @RECOVERY_SHA@ ]
[ "$(sha256sum /dev/ubi0_0 | cut -d' ' -f1)" = @OLD0_SHA@ ]
[ "$(sha256sum /dev/ubi0_3 | cut -d' ' -f1)" = @OLD3_SHA@ ]
[ "$(sha256sum /dev/ubi0_1 | cut -d' ' -f1)" = @FW1_SHA@ ]
[ "$(sha256sum /dev/ubi0_2 | cut -d' ' -f1)" = @FW2_SHA@ ]
[ ! -e /sys/class/ubi/ubi0_4/name ]
[ ! -e /sys/class/ubi/ubi0_5/name ]
[ ! -e /sys/class/ubi/ubi0_6/name ]
echo 'Physical RESET recovery was verified. Removing ONLY old OS volumes 0 and 3.'
ubirmvol /dev/ubi0 -n 0
ubirmvol /dev/ubi0 -n 3
# Reserve kernel space now; its bytes are deliberately written LAST.
ubimkvol /dev/ubi0 -n 4 -N owrt_kernel -s $((@KERNEL_LEBS@*126976)) -t static
ubimkvol /dev/ubi0 -n 5 -N owrt_rootfs -s $((@ROOT_LEBS@*126976)) -t static
ubiupdatevol /dev/ubi0_5 rootfs.bin
[ "$(sha256sum /dev/ubi0_5 | cut -d' ' -f1)" = @ROOT_SHA@ ]
ubimkvol /dev/ubi0 -n 6 -N rootfs_data -m -t dynamic
ubiupdatevol /dev/ubi0_6 overlay.ubifs
mkdir -p /tmp/mf297d-overlay-verify
mount -t ubifs -o ro ubi0:rootfs_data /tmp/mf297d-overlay-verify
[ -d /tmp/mf297d-overlay-verify/upper ]
[ -d /tmp/mf297d-overlay-verify/work ]
[ "$(readlink /tmp/mf297d-overlay-verify/.fs_state)" = 2 ]
umount /tmp/mf297d-overlay-verify
[ "$(sha256sum /dev/ubi0_7 | cut -d' ' -f1)" = @RECOVERY_SHA@ ]
[ "$(sha256sum /dev/ubi0_1 | cut -d' ' -f1)" = @FW1_SHA@ ]
[ "$(sha256sum /dev/ubi0_2 | cut -d' ' -f1)" = @FW2_SHA@ ]
sha256sum -c prefix.after.sha256
ubiupdatevol /dev/ubi0_4 kernel.bin
[ "$(sha256sum /dev/ubi0_4 | cut -d' ' -f1)" = @KERNEL_SHA@ ]
sync
echo 'Native image verified. Recovery preserved; stock OS removed; rebooting single OpenWrt.'
reboot
