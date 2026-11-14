#!/bin/sh
    # Operates on an already prepared pinned OpenWrt Linux tree. No device access.
    set -eu
    : "${OPENWRT_ROOT:?Set absolute path to pinned OpenWrt tree}"
    : "${KERNEL_DIR:?Set absolute path to prepared Linux 6.18.55}"
    : "${CROSS_COMPILE:?Set absolute toolchain compiler prefix}"
    : "${STAGING_DIR:?Set target staging directory}"
    here=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
    [ "$(git -C "$OPENWRT_ROOT" rev-parse HEAD)" = bb6df54d9d1cb486f7102e9863f0380cb9f3a1f3 ]
    grep -q '^VERSION = 6$' "$KERNEL_DIR/Makefile"
    grep -q '^PATCHLEVEL = 18$' "$KERNEL_DIR/Makefile"
    grep -q '^SUBLEVEL = 55$' "$KERNEL_DIR/Makefile"
    python3 "$here/tools/verify_export.py"
    python3 - "$here" "$KERNEL_DIR" <<'PY'
import pathlib, shutil, sys
source=pathlib.Path(sys.argv[1])/'src/kernel';target=pathlib.Path(sys.argv[2])
for p in source.rglob('*'):
    if p.is_file():
        dest=target/p.relative_to(source)
        if not dest.is_file(): raise SystemExit('Expected prepared source missing: '+str(dest))
        shutil.copyfile(p,dest)
PY
    cp "$here/config/kernel-native.config" "$KERNEL_DIR/.config"
    make -C "$KERNEL_DIR" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" KERNELRELEASE=6.18.55 olddefconfig
    grep -q '^CONFIG_KEXEC=y$' "$KERNEL_DIR/.config"
    grep -q '^CONFIG_PM_SLEEP_SMP=y$' "$KERNEL_DIR/.config"
    make -C "$KERNEL_DIR" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" KERNELRELEASE=6.18.55 KBUILD_BUILD_VERSION=0 KBUILD_BUILD_USER=mf297d KBUILD_BUILD_HOST=source-builder -j"${JOBS:-4}" Image modules
