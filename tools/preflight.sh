#!/bin/sh
    # Read-only inventory. Does not change network, UBI, ENV or flash.
    set -eu
    uname -a
    cat /etc/openwrt_release
    cat /proc/cmdline
    cat /proc/mtd
    for p in /sys/class/mtd/mtd[0-9]*; do
      [ -r "$p/name" ] || continue
      for field in name offset size erasesize writesize oobsize flags; do
        [ ! -r "$p/$field" ] || { printf '%s %s=' "${p##*/}" "$field"; cat "$p/$field"; }
      done
    done
    mount
    df -h /overlay /
    command -v ubinfo >/dev/null 2>&1 && ubinfo -a
    printf 'No writes performed. Review locally; inventory may contain identifiers.
'
