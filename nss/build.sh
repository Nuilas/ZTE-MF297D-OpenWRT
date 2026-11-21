#!/bin/sh
set -eu
profile=${1:-nand}
case "$profile" in nand|initramfs) ;; *) exit 2;; esac
integration=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tree=${2:-"$PWD"}
cd "$tree"
tree=$PWD
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
jobs=${JOBS:-8}
make -j"$jobs" tools/install
make -j"$jobs" toolchain/install
python3 "$integration/tools/enable-sysupgrade.py" "$tree"
python3 "$integration/tools/enable-host-tx.py" "$tree"
python3 "$integration/tools/build-radio-reader.py" --tree "$tree" --out "$tree/mf297d/public-helper-bin"
cc="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-gcc"
export STAGING_DIR="$tree/staging_dir/target-aarch64_cortex-a53_musl"
mkdir -p files/usr/sbin
"$cc" -static -Os -s -Wall -Wextra -Werror -Wno-misleading-indentation "$integration/src/factory_data.c" -o files/usr/sbin/mf297d-factory-data
cp mf297d/public-helper-bin/unsquashfs-aarch64 files/usr/sbin/mf297d-unsquashfs
chmod 755 files/usr/sbin/mf297d-factory-data files/usr/sbin/mf297d-unsquashfs
mkdir -p files/usr/libexec
"$cc" -static -Os -s -Wall -Wextra -Werror -Wno-misleading-indentation "$integration/src/upgrade_guard.c" -o files/usr/libexec/mf297d-upgrade-guard
chmod 755 files/usr/libexec/mf297d-upgrade-guard
if [ "$profile" = nand ]; then
 # The custom NAND bundle is packaged below, outside OpenWrt's IMAGES list.
 # An empty image list has no JSON records for profiles.json to aggregate.
 make -j"$jobs" CONFIG_JSON_OVERVIEW_IMAGE_INFO=
else
 make -j"$jobs"
fi
python3 "$integration/tools/package-build.py" --tree "$tree" --profile "$profile" --out "$tree/bin/mf297d"
