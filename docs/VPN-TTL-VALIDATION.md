# MF297D NSS: persistent VPN performance and TTL64 profile

This source profile preserves the tested host IPv4 TX checksum/TSO and WAN
GRO/GSO fixes. TTL rewriting is **disabled by default**, in both the MF297D
image overlay and the standalone `luci-app-ttl` package. The optional preset is
IPv4 TTL64 on `wan` and `lte`; enable it from Network -> TTL Control when needed.
Existing build-overlay settings are preserved by the update helper. IPv6 Hop
Limit remains disabled.

## Rebuild with your existing package choices

```sh
cd ~/MF297D
git pull --ff-only
sh nss/build.sh nand ~/build-mf297d-nand
```

The build helper installs the companion kernel package and `luci-app-ttl`, runs
`make defconfig`, and preserves unrelated package selections. The kernel module
must be built against that image's own kernel. No VPN credentials or active
profile are part of this source profile; configure your VPN separately.

Enable the host TX fixes on an already configured device containing these packages:

```sh
uci set mf297d_tuning.general.host_ipv4_checksum='1'
uci set mf297d_tuning.general.host_ipv4_tso='1'
uci commit mf297d_tuning
/etc/init.d/mf297d-host-tx enable
/etc/init.d/mf297d-host-tx start
```

Optional TTL64 activation (this is not the image default):

```sh
uci set mf297d-ttl.main.enabled='1'
uci set mf297d-ttl.main.ttl='64'
uci commit mf297d-ttl
/etc/init.d/mf297d-ttl enable
/etc/init.d/mf297d-ttl reload
```

To keep TTL rewriting disabled across reboots:

```sh
uci set mf297d-ttl.main.enabled='0'
uci commit mf297d-ttl
/etc/init.d/mf297d-ttl reload
```

TTL enforcement pauses IPv4 ECM flow acceleration so established accelerated
flows cannot bypass the nftables rewrite. Wi-Fi NSS and host TX segmentation
remain active. Firewall software/hardware flowtables must also be disabled;
the application rejects activation if they would bypass the rule.

## Actual internet VPN results, 2026-11-21

Unmodified Xray 26.11.9, VLESS/TLS Vision, wired WAN/LAN1, IPv4 TTL64 enabled:

| Condition | Sustained download | Average CPU |
| --- | ---: | ---: |
| Normal CPU placement, two streams | 438.22 Mbps | 94.7% |
| Temporary CPU1 placement, two streams, later repeat | 472.73 Mbps | 97.1% |
| After final reboot, normal placement, TTL disabled | 337.82 Mbps | 95.1% |
| After final reboot, normal placement, TTL64 enabled | 345.35 Mbps | 93.8% |

Post-boot downloads were also confirmed by Xray's proxy downlink counter:
635,317,589 bytes with TTL off and 649,480,761 with TTL64. The lower post-boot
results mean 438 Mbps must not be presented as a guaranteed persistent speed.
The configured offloads and segmentation counters survived the reboots; the
remaining throughput variation has not been isolated to a single cause.

These are 15-second aggregate internet VPN downloads, not the separate local
574.25 Mbps Vision result. HTTP200 was checked. Curl timeout28 was intentional
at the 15-second limit. Internet variation prevents claiming a repeatable
benefit from CPU placement, GOMAXPROCS=1 or avoiding redundant TTL writes.
Those experiments were reverted. The final profile uses both CPUs and the
original TTL rules, with a 32768-byte IPv4 GSO ceiling. A 64000-byte comparison
did not improve throughput and was reverted. Sustained 500 Mbps is not verified.

WAN capture observed TTL64 on 400 outgoing TCP packets. A separate probe sent
three UDP packets with TTL123; all three left WAN with TTL64. This checks an
actual rewrite, rather than merely observing the router's default TTL.

## Boot validation

See [the machine-readable boot report](../nss/validation/vpn-ttl-boot.json).
Three software-initiated reboots passed: the first two with optional TTL64
enabled, and the final one with TTL rewriting disabled and committed. The final
configuration keeps TTL disabled. The final boot reached full readiness in
87.3 seconds without manual service startup or manual VPN reconnection.
The tests verify changed boot IDs, automatic VPN connection, the original Xray,
TTL64 rules and guard, the matching kernel-module identity, host TX offloads,
WAN GRO/GSO, both CPUs, both Wi-Fi radios, and LuCI's login page. HTTP403 with
`x-luci-login-required: yes` is the normal unauthenticated login response.

After startup, TTL64 activation also needs its ECM guard to report `1`; merely
finding an nftables rule is insufficient. The guard was rechecked after startup
in the enabled tests. With the final disabled setting both ECM stop flags are `0`.

These checks validate the existing NAND installation with the persistent
runtime additions. They do not validate a newly rebuilt/flashed firmware image
or a physical cold power cycle. No bootloader, ENV or recovery image was written.
Previously published firmware Release binaries do not contain these additions;
rebuild from the updated source to include them in a new image.

For diagnosis and rollback see [HOST-TX-TUNING.md](../nss/HOST-TX-TUNING.md).
