# SPDX-License-Identifier: GPL-2.0-only
# Existing single-OpenWrt layout only. Never formats MTD or rewrites ENV/recovery.

mf297d_error() { echo "MF297D sysupgrade: $*" >&2; return 1; }

mf297d_check_layout() {
	[ "$(board_name)" = zte,mf297d ] || return 1
	grep -q 'root=/dev/ubiblock0_5' /proc/cmdline || mf297d_error 'requires installed NAND OpenWrt' || return 1
	[ "$(cat /sys/class/mtd/mtd21/name)" = rootfs ] &&
	[ "$(cat /sys/class/mtd/mtd21/size)" = 221511680 ] &&
	[ "$(cat /sys/class/mtd/mtd21/erasesize)" = 131072 ] &&
	[ "$(cat /sys/class/mtd/mtd21/writesize)" = 2048 ] &&
	[ "$(cat /sys/class/mtd/mtd21/flags)" = 0x400 ] || { mf297d_error 'unsupported NAND geometry'; return 1; }
	local i name
	i=0
	while [ "$i" -le 20 ]; do
		[ "$(cat /sys/class/mtd/mtd$i/flags)" = 0x0 ] || { mf297d_error "MTD$i must be read-only"; return 1; }
		i=$((i+1))
	done
	[ "$(cat /sys/class/ubi/ubi0/mtd_num)" = 21 ] &&
	[ "$(cat /sys/class/ubi/ubi0/volumes_count)" = 6 ] &&
	[ "$(cat /sys/class/ubi/ubi0/eraseblock_size)" = 126976 ] &&
	[ ! -e /sys/class/ubi/ubi1/mtd_num ] || { mf297d_error 'unsupported UBI layout'; return 1; }
	for i in 1:wifi_fw 2:bt_fw 4:owrt_kernel 5:owrt_rootfs 6:rootfs_data 7:owrt_recovery; do
		name=${i#*:}; i=${i%%:*}
		[ "$(cat /sys/class/ubi/ubi0_$i/name)" = "$name" ] || { mf297d_error "unexpected volume $i"; return 1; }
	done
	for i in 1 2 4 5 7; do
		[ "$(cat /sys/class/ubi/ubi0_$i/type)" = static ] || return 1
	done
	[ "$(cat /sys/class/ubi/ubi0_6/type)" = dynamic ] || return 1
	/usr/libexec/mf297d-upgrade-guard --check-env /dev/mtd10ro || return 1
}

mf297d_cleanup() {
	case "$MF297D_WORK" in /tmp/mf297d-upgrade.*) rm -rf "$MF297D_WORK";; esac
	MF297D_WORK=
}

mf297d_validate_payload() {
	local image="$1" listing expected meta manifest kbytes rbytes ksha rsha value
	MF297D_WORK=$(mktemp -d /tmp/mf297d-upgrade.XXXXXX) || return 1
	[ -f "$image" ] && [ "$(wc -c < "$image")" -le 157286400 ] || { mf297d_error 'invalid image size'; return 1; }
	listing=$(tar tf "$image" 2>/dev/null) || return 1
	expected=$(printf '%s\n' sysupgrade-zte_mf297d/ sysupgrade-zte_mf297d/CONTROL sysupgrade-zte_mf297d/kernel sysupgrade-zte_mf297d/root sysupgrade-zte_mf297d/manifest.json)
	[ "$listing" = "$expected" ] || { mf297d_error 'not an MF297D sysupgrade archive'; return 1; }
	[ "$(tar xOf "$image" sysupgrade-zte_mf297d/CONTROL)" = 'BOARD=zte,mf297d' ] || return 1
	meta=$MF297D_WORK/metadata.json
	fwtool -q -i "$meta" "$image" || { mf297d_error 'missing or corrupt OpenWrt metadata'; return 1; }
	[ "$(jsonfilter -i "$meta" -e '@.supported_devices[*]')" = zte,mf297d ] &&
	[ "$(jsonfilter -i "$meta" -e '@.mf297d_layout')" = ubi-fixed-4-5-6-recovery-7-v1 ] || { mf297d_error 'wrong board or layout metadata'; return 1; }
	[ "$(tar xOf "$image" sysupgrade-zte_mf297d/manifest.json | wc -c)" -le 4096 ] || return 1
	manifest=$MF297D_WORK/manifest.json
	tar xOf "$image" sysupgrade-zte_mf297d/manifest.json > "$manifest" || return 1
	[ "$(jsonfilter -i "$manifest" -e '@.kind')" = MF297D-SYSUPGRADE-1 ] &&
	[ "$(jsonfilter -i "$manifest" -e '@.model')" = zte,mf297d ] || return 1
	kbytes=$(jsonfilter -i "$manifest" -e '@.kernel_bytes')
	rbytes=$(jsonfilter -i "$manifest" -e '@.root_bytes')
	ksha=$(jsonfilter -i "$manifest" -e '@.kernel_sha256')
	rsha=$(jsonfilter -i "$manifest" -e '@.root_sha256')
	for value in "$kbytes" "$rbytes"; do case "$value" in ''|*[!0-9]*) return 1;; esac; [ ${#value} -le 9 ] || return 1; done
	[ "$kbytes" -ge 4096 ] && [ "$kbytes" -le 16777216 ] &&
	[ "$rbytes" -ge 4096 ] && [ "$rbytes" -le 134217728 ] || return 1
	for value in "$ksha" "$rsha"; do case "$value" in *[!0-9a-f]*) return 1;; esac; [ ${#value} -eq 64 ] || return 1; done
	value=$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)
	[ "$((value*1024))" -ge "$((kbytes*3+8388608))" ] || { mf297d_error 'not enough free RAM to validate this kernel'; return 1; }
	[ "$(tar xOf "$image" sysupgrade-zte_mf297d/root | wc -c)" = "$rbytes" ] || return 1
	[ "$(tar xOf "$image" sysupgrade-zte_mf297d/root | sha256sum | cut -d' ' -f1)" = "$rsha" ] || { mf297d_error 'rootfs SHA256 mismatch'; return 1; }
	tar xOf "$image" sysupgrade-zte_mf297d/kernel > "$MF297D_WORK/kernel.generic" || return 1
	[ "$(wc -c < "$MF297D_WORK/kernel.generic")" = "$kbytes" ] &&
	[ "$(sha256sum "$MF297D_WORK/kernel.generic" | cut -d' ' -f1)" = "$ksha" ] || { mf297d_error 'kernel SHA256 mismatch'; return 1; }
	/usr/libexec/mf297d-upgrade-guard --check-fit "$MF297D_WORK/kernel.generic" || return 1
	tar xOf "$image" sysupgrade-zte_mf297d/root | dd bs=4096 count=1 of="$MF297D_WORK/root.header" 2>/dev/null
	/usr/libexec/mf297d-upgrade-guard --check-root "$MF297D_WORK/root.header" "$rbytes" || return 1
	MF297D_KERNEL_BYTES=$kbytes; MF297D_ROOT_BYTES=$rbytes; MF297D_ROOT_SHA=$rsha
	local budget klebs rlebs i
	budget=$(cat /sys/class/ubi/ubi0/avail_eraseblocks) || return 1
	for i in 4 5 6; do budget=$((budget + $(cat /sys/class/ubi/ubi0_$i/reserved_ebs))); done
	klebs=$(((kbytes+126975)/126976+1)); rlebs=$(((rbytes+126975)/126976+1))
	MF297D_KERNEL_LEBS=$klebs; MF297D_ROOT_LEBS=$rlebs; MF297D_OVERLAY_LEBS=$((budget-klebs-rlebs))
	[ "$MF297D_OVERLAY_LEBS" -ge 128 ] || { mf297d_error 'not enough space while preserving recovery'; return 1; }
	echo 'MF297D sysupgrade payload validated; recovery and calibration will be preserved.'
}

mf297d_check_image() {
	local result=0
	mf297d_check_layout || return 1
	mf297d_validate_payload "$1" || result=1
	mf297d_cleanup
	return "$result"
}

mf297d_preserved_hashes() {
	local i
	for i in $(seq 0 20); do sha256sum /dev/mtd${i}ro || return 1; done
	for i in 1 2 7; do sha256sum /dev/ubi0_$i || return 1; done
}

mf297d_flash() {
	local image="$1" kernel_sha
	# Recheck even if the operator used sysupgrade --force.
	mf297d_check_layout && mf297d_validate_payload "$image" || return 1
	/usr/libexec/mf297d-upgrade-guard --personalise "$MF297D_WORK/kernel.generic" "$MF297D_WORK/kernel.owned" || return 1
	kernel_sha=$(sha256sum "$MF297D_WORK/kernel.owned" | cut -d' ' -f1)
	mf297d_preserved_hashes > "$MF297D_WORK/preserved.sha256" || return 1
	# Refuse a busy root; never detach/format the whole UBI container.
	nand_remove_ubiblock ubi0_5 || return 1
	grep -q ' ubifs ' /proc/mounts && { mf297d_error 'UBIFS still mounted after RAM pivot'; return 1; }
	# Invalidate main FIRST: a power interruption must not boot an old kernel
	# after its rootfs has gone. U-Boot then selects the preserved recovery.
	ubirmvol /dev/ubi0 -n 4 && ubirmvol /dev/ubi0 -n 5 && ubirmvol /dev/ubi0 -n 6 || return 1
	ubimkvol /dev/ubi0 -n 4 -N owrt_kernel -t static -S "$MF297D_KERNEL_LEBS" &&
	ubimkvol /dev/ubi0 -n 5 -N owrt_rootfs -t static -S "$MF297D_ROOT_LEBS" &&
	ubimkvol /dev/ubi0 -n 6 -N rootfs_data -t dynamic -S "$MF297D_OVERLAY_LEBS" || return 1
	tar xOf "$image" sysupgrade-zte_mf297d/root | ubiupdatevol /dev/ubi0_5 -s "$MF297D_ROOT_BYTES" - || return 1
	[ "$(sha256sum /dev/ubi0_5 | cut -d' ' -f1)" = "$MF297D_ROOT_SHA" ] || return 1
	CI_UBIPART=rootfs; CI_KERNPART=owrt_kernel; CI_ROOTPART=owrt_rootfs
	CI_DATA_UBIPART=rootfs; CI_KERN_UBIPART=rootfs; CI_ROOT_UBIPART=rootfs
	# Standard OpenWrt settings archive, including the LuCI 'Keep settings' choice.
	nand_do_restore_config || return 1
	# An empty/invalid kernel volume falls through to the untouched recovery.
	ubiupdatevol /dev/ubi0_4 "$MF297D_WORK/kernel.owned" || return 1
	[ "$(sha256sum /dev/ubi0_4 | cut -d' ' -f1)" = "$kernel_sha" ] || return 1
	sha256sum -c "$MF297D_WORK/preserved.sha256" || return 1
	sync
	echo 'MF297D kernel/rootfs verified; ENV, recovery and calibration unchanged.'
}

mf297d_do_upgrade() {
	if mf297d_flash "$1"; then
		mf297d_cleanup
		nand_do_upgrade_success
	fi
	mf297d_cleanup
	nand_do_upgrade_failed
}
