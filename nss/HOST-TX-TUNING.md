# MF297D: IPv4 host TX checksum, TSO and WAN GRO/GSO tuning

On the tested MF297D NSS image (Linux 6.18.60, NSS firmware 12.5-210-MP.R),
`qca-dwmac-nss` clears eth0 TX checksum features during takeover. Software
forwarding and userspace proxy traffic still traverse the host stack; NSS NAT
throughput does not measure that path. The processor's AES/PMULL support was
present and Go's accelerated AES routines were observed in a live CPU profile.

This board-specific service restores IPv4 TX checksum on eth0, enables the
kernel-bound `mf297d_host_tso` companion for eth0/LAN1, and repairs a WAN
software-GRO/GSO actual-off/wanted-on inconsistency. It respects an explicit
user request to keep WAN GRO/GSO off. IPv6, CPU clocks and Xray itself are
unchanged. The service checks state every 30 seconds without bouncing links
or restarting NSS.

The companion bypasses Synopsys's hardware-TSO rejection only while the existing
NSS data-plane owner is active. VLAN safety checks remain in place. The routed
bridge and lower devices use a matching 32 KiB IPv4 GSO ceiling. No DMA/ring
configuration or firmware messages are changed. RTNL, netdevice-unregister
notification and `synchronize_net()` protect attachment/removal; no long-lived
netdevice reference prevents bridge deletion. The tested live configuration
accelerates LAN1. Other ports keep their previous behavior.

The loader requires a SHA256 match of `/sys/kernel/notes` with the identity
installed beside the module. The OpenWrt package generates this identity from
the matching vmlinux `.notes` section. A wrong identity was tested and refused.
Do not carry an old `.ko` into a new kernel; rebuild the package with the image.

## Validation on 2026-11-21

Identical local TLS/VLESS Vision topology, four parallel downloads, unmodified
Xray 26.11.9 on the router:

| Condition | Download | Average router CPU |
| --- | ---: | ---: |
| IPv4 checksum off | 334.75 Mbps | 97.7% |
| IPv4 checksum on | 432.90 Mbps | 97.1% |
| IPv4 checksum off again | 336.79 Mbps | 97.3% |

These first three results isolate the checksum change, before the TSO companion.
The CPU remains busy at maximum throughput, but it transfers about 29% more data.
The local topology exercises the same 1 Gbps PC Ethernet link in both directions.
These numbers are not internet speed claims.

The existing internet VPN profile, same OVH HTTPS file, two parallel downloads:

| Condition | Download | Average router CPU |
| --- | ---: | ---: |
| IPv4 checksum off | 191.41 Mbps | 92.9% |
| IPv4 checksum on | 223.38 Mbps | 88.7% |

Both internet transfers downloaded all 200 MiB with HTTP 200 and no curl errors.
Xray's proxy downlink counter subsequently reported 420,559,444 bytes, consistent
with the combined 400 MiB transfers. A local UDP echo test also verified all
32 payloads with the feature both off and on. An independent public-DNS probe
was refused with either setting, so it was not used as proof of this change.

### Subsequent TSO and WAN fixes

The Synopsys `ndo_features_check` rejected GSO even when NSS owned transmission.
Merely advertising TSO had no repeatable benefit. With the NSS-owner-aware
check and matching bridge/lower GSO sizes, the patterned TCP test changed from
664.52 to 807.02 Mbps and returned to 648.47 Mbps after automatic rollback.
NSS host-TX skb count fell from 463,354 to 32,213 during the comparable test;
TCP retransmission deltas were 2 versus 1. Payload bytes were verified.

With unmodified Xray, the local TLS/VLESS Vision test measured 406.04 Mbps off,
574.25 Mbps on, and 440.16 Mbps off again. The on test downloaded all four
256 MiB files without curl errors. These local numbers are not internet speeds.

The WAN software GSO, GRO and GRO-list features were actual-off/wanted-on.
Toggling them to make actual state match the requested state restored them.
With TSO and this WAN fix, the existing internet VPN profile downloaded two
100 MiB OVH files at 332.91 Mbps, HTTP 200, no curl errors.

A separate 15-second rate-limited internet VPN run delivered 201.67 Mbps at
51.8% average CPU (CPU0 55.1%, CPU1 48.6%). The test intentionally stopped
the larger files at 15 seconds; curl timeout 28 in that run is expected.
No 600–700 Mbps internet result is claimed.

Service restart and automatic restoration after a simulated feature reset were
verified without rebooting. A disposable empty bridge removal also detached
the companion and restored features without a held-reference wait. The live
companion was installed only after bounded 10/30-second rollback tests and
independent recovery guards. The tested image's backup list includes the config,
helper, init script and enable/stop symlinks. A new firmware image was not flashed.
The ordinary Xray path was restored after temporary core comparisons; no custom
Xray binary is installed. RPS and CPU-pinning experiments were not installed.

## Configuration and rollback

The integration build installs the files and preserves an existing tuning config.
The service is specific to `zte,mf297d` with a started NSS eth0 data plane.

```sh
ethtool -k eth0 | grep tx-checksum-ipv4
ethtool -k lan1 | grep tx-tcp-segmentation
cat /sys/module/mf297d_host_tso/parameters/gso_packets
/etc/init.d/mf297d-host-tx running
```

Disable and restore the old checksum behavior:

```sh
uci set mf297d_tuning.general.host_ipv4_checksum='0'
uci set mf297d_tuning.general.host_ipv4_tso='0'
uci commit mf297d_tuning
/etc/init.d/mf297d-host-tx stop
/etc/init.d/mf297d-host-tx disable
```

To enable again, set both options to `1`, then enable and start the service.
No boot environment, partition layout, recovery image or NAND firmware changes
are needed. High CPU at unrestricted maximum speed is still possible; the
verified fixed-rate result is the evidence for reduced CPU cost at 200 Mbps.
Boot persistence is configured; a full-device reboot was not performed in this
validation. The `.ko` and ABI identity are deliberately not sysupgrade backup
items: the new image must contain the rebuilt kmod package.

The final CPU-affinity A/B/A internet comparison was inconclusive: the return
run received HTTP 429 from the download endpoint. Default affinity (both CPUs)
was restored; the isolated higher result is not a validated improvement.
