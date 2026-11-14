#!/bin/sh
    set -eu
    : "${KEXEC_SOURCE:?Set path to prepared kexec-tools-2.0.32 source}"
    : "${CROSS_COMPILE:?Set absolute toolchain compiler prefix}"
    : "${STAGING_DIR:?Set target staging directory}"
    cd "$KEXEC_SOURCE"
    ./configure --host=aarch64-openwrt-linux-musl --target=aarch64-linux-musl --build="$(gcc -dumpmachine)" --without-zlib --without-lzma --without-zstd CC="${CROSS_COMPILE}gcc" LD="${CROSS_COMPILE}ld" AR="${CROSS_COMPILE}ar" TARGET_CC="${CROSS_COMPILE}gcc" TARGET_LD="${CROSS_COMPILE}ld" BUILD_CC=gcc LDFLAGS=-static
    make -j"${JOBS:-4}"
    printf 'Built build/sbin/kexec; no device operation performed.
'
