#!/bin/sh
set -eu
profile=${1:-nand}
case "$profile" in nand|initramfs) ;; *) echo 'Kullanim: sh nss/configure.sh nand|initramfs /yol/openwrt' >&2; exit 2;; esac
integration=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tree=${2:-"$PWD/openwrt-mf297d"}
base=593ffa8e281c0a4ab17fd52365aecb546bfaf442
if [ ! -e "$tree" ]; then
 git clone https://github.com/kuncy7/openwrt-nss-edma.git "$tree"
fi
cd "$tree"
test "$(git rev-parse HEAD)" = "$base" || git checkout --detach "$base"
test ! -e mf297d/public-source-configured || { echo 'Bu alan zaten hazir. Paket eklemek icin make menuconfig kullan.' >&2; exit 1; }
git apply --check "$integration/openwrt.patch"
git apply "$integration/openwrt.patch"
cp -a "$integration/overlay/." .
cp "$integration/feeds.conf" feeds.conf
./scripts/feeds update -a
./scripts/feeds install -a
if [ -s "$integration/nss-feed.patch" ]; then
 git -C feeds/nss apply --check "$integration/nss-feed.patch"
 git -C feeds/nss apply "$integration/nss-feed.patch"
fi
cp -a "$integration/feed-overlay/." feeds/nss/
cp "$integration/config/$profile.config" .config
python3 "$integration/tools/prune-unused-feeds.py" "$PWD"
python3 "$integration/tools/select-profile.py" "$PWD" "$profile"
chmod 755 files/etc/board.d/*mf297d* files/etc/uci-defaults/*mf297d* files/etc/init.d/mf297d-radio files/etc/init.d/mf297d-cpu files/etc/init.d/mf297d-wifi-led files/usr/sbin/mf297d-wifi-led files/usr/sbin/mf297d-radio-prepare files/etc/init.d/mf297d-host-tx files/usr/sbin/mf297d-host-tx
chmod 600 files/etc/shadow
make defconfig
mkdir -p mf297d
printf '%s\n' "$integration" > mf297d/public-source-configured
printf 'Hazir: %s\nPaket secimi: make menuconfig\nDerleme: sh %s/build.sh %s %s\n' "$PWD" "$integration" "$profile" "$PWD"
