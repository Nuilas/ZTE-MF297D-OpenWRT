#!/bin/sh
set -eu
: "${OPENWRT_ROOT:?Set absolute path to pinned OpenWrt tree}"
: "${KERNEL_DIR:?Set absolute path to prepared, built Linux 6.18.55}"
: "${CROSS_COMPILE:?Set absolute toolchain prefix ending in aarch64-openwrt-linux-musl-}"
: "${STAGING_DIR:?Set OpenWrt target staging directory}"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=${1:?Usage: build.sh NEW_ABSOLUTE_OUTPUT_DIRECTORY}
case "$out" in /*) ;; *) echo 'Output must be absolute' >&2; exit 1;; esac
[ ! -e "$out" ] || { echo 'Output already exists' >&2; exit 1; }
mkdir -p "$out"
for source in usb-serial.c generic.c bus.c usb_wwan.c option.c usb-wwan.h; do
  cp "$KERNEL_DIR/drivers/usb/serial/$source" "$out/"
done
for source in usbnet.c cdc_ether.c rndis_host.c qmi_wwan.c; do
  cp "$KERNEL_DIR/drivers/net/usb/$source" "$out/"
done
cp "$KERNEL_DIR/drivers/net/wwan/wwan_core.c" "$out/"
cp "$KERNEL_DIR/drivers/usb/class/cdc-wdm.c" "$out/"
cp "$here/Makefile" "$out/"
python3 "$here/patch_option.py" "$out/option.c"
make -C "$KERNEL_DIR" M="$out" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" -j"${JOBS:-4}" modules
