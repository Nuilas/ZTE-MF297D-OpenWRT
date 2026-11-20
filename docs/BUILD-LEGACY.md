# Kaynaklardan derleme

## Tekrarlanabilirlik sınırı

Test kernel/modüllerinin gerçek kaynak overlay'i ve config'leri var. Tam
userspace ilk sağlanan initramfs'ten geldi; bu depodaki package world listesi
kaynak feed commit kilitlerinin yerini tutmaz. Baştan tek komutla bit-eşdeğer
factory imaj üretimi **henüz doğrulanmadı**. Bu belge çalışan bileşenlerin
derleme reçetesidir; denenmiş evrensel imaj fabrikası değildir.

## Temel kaynak ve araçlar

Ubuntu/WSL Linux x86_64: git, Python3, GNU make, gcc/g++, bc, bison, flex,
libssl-dev, libelf-dev, device-tree-compiler, u-boot-tools, xz, zstd,
squashfs-tools, mtd-utils ve OpenWrt'nin resmi build prerequisites paketleri.

```sh
git clone https://git.openwrt.org/openwrt/openwrt.git openwrt
cd openwrt
git checkout bb6df54d9d1cb486f7102e9863f0380cb9f3a1f3
```

`config/openwrt-build.config` çalışma ağacının config snapshot'ıdır; kernel
kaynak seçimini/paketleri incelemek içindir. Özel MF297D image profile'ı bu
repo tarafından upstream'e eklenmiş değildir. Henüz olmayan profili seçip
`make world` çalıştırmak kurulum imajı üretmez. `reference/etc/apk/world` ve
`openwrt_release` eski userspace envanterini gösterir. Feeds'i güncel HEAD'e
çekmek testteki paketleri yeniden üretmez; tam feed lock TODO'dur.

Linux tarball: linux-6.18.55.tar.xz SHA256
`f410638061a165c12f42ab871d2f3fcd525515359b5faeee80969cff84524df9`.
Backports7.2 SHA256
`6ec76a4cb0988b5382b2fc5053610a56ada90b8ef6a5a4f2807cd433badb9454`.
Test toolchain: aarch64_cortex-a53, GCC14.4.0, musl. Hash kilidi
`config/source-lock.json` içinde; upstream indirmeyi hash kontrolü olmadan açmayın.

OpenWrt toolchain ve target kernel prepare işlemlerini seçilmiş ipq50xx hedefinde
tamamlayın. Çalışma ağacında kullanılan yol örneği:
`build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55`.
Bu dizin düz vanilla Linux değildir; OpenWrt target patch'leri uygulanmıştır.
`src/kernel` sürücülerini vanilla kernel üzerine kopyalamak yeterli değildir.

## Native kernel

```sh
export OPENWRT_ROOT=/absolute/path/openwrt
export KERNEL_DIR="$OPENWRT_ROOT/build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55"
export STAGING_DIR="$OPENWRT_ROOT/staging_dir/target-aarch64_cortex-a53_musl"
export CROSS_COMPILE="$OPENWRT_ROOT/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-"
sh tools/build_kernel.sh
```

Script base commit/version ve source manifest'i kontrol eder; hazırlanmış
ağaca son sürücü kaynaklarını ve native config'i koyar. `olddefconfig`, KEXEC/
PM_SLEEP_SMP kontrolleri, ardından Image/modules build yapar. İlk tarihsel
`patches/0999-mf297d-board-port.patch` inceleme içindir; son overlay üstüne
tekrar apply etmeyin. Foresee ID, QPIC seri bank/ayar, MDIO clock/reset ve
UNIPHY değişikliklerini son `.c` dosyaları üzerinden inceleyin.

## Recovery kernel

Native build'in ayrı kopyası/O= build dizini kullanılmalı. `kernel-recovery.config`
içindeki INITRAMFS_SOURCE `initramfs.cpio` yer tutucusudur. Kendi oluşturduğunuz
CPIO'yu aynı ağaca bu adla koyun; içine SSH/LAN ayarları, `/init`, gerekli
dinamik kitaplıklar ve modül/kernel uyumu dahil edilmelidir. Kişisel host key,
shadow ve radyo firmware arşivlerini depoya eklemeyin. Recovery config ile
`olddefconfig` ve `Image modules` derleyin; build çıktısını native ile karıştırmayın.
Native/recovery için module ABI/Module.symvers karşılaştırması gerekir.

## DTS ve FIT

```sh
python3 tools/build_dtb.py --variant native --lan-mac OWN_LAN_MAC --wan-mac OWN_WAN_MAC --out build/native.dtb
python3 tools/build_fit.py --image "$KERNEL_DIR/arch/arm64/boot/Image" --dtb build/native.dtb --out build/native-built.itb
python3 tools/inspect_fit.py private/verified-native.itb
python3 tools/replace_fit_dtb.py private/verified-native.itb build/native.dtb build/native-new.itb
```

`OWN_*` değerleri örnek metindir; kendi cihazınızın doğrulanmış Ethernet MAC'lerini
girin. DTS'ler decompile olduğu için dtc'den unit-address vb. uyarılar gelebilir;
fatal hata göz ardı edilmez. `replace_fit_dtb.py` sadece inline fdt-1 + hash
düğümleri olan unsigned FIT şablonunu değiştirir; kernel payload'ını korur,
eski/yeni hash'leri doğrular, boyut/CRC/SHA raporlar ve **flash yazmaz**.
Yeni Image için `build_fit.py`, testteki inline FIT şemasını sıfırdan üretir:
ARM64 + LZMA, load/entry 0x41000000, config@mp03.3, CRC32/SHA1. Image başlık
magic, text_offset=0, image_size/RAM sınırı ve DT modelini kontrol eder; ELF
veya sıkıştırılmış Image kabul etmez. Helper gerçek native Image ile offline
üretim/açma/hash testinden geçti; **bu helper'ın yeni çıktısı donanımda boot
edilmedi**. Yeni FIT'i yazmadan RAM test ve ayrılan UBI hacmine sığma kontrolü
gerekir (native37 LEB, recovery90 LEB). Rootfs ve ilk initramfs bu depoda yok;
otomatik tam imaj üretiminin açık kalan bölümü userspace/kurulumdur. Yeni CRC
için RECOVERY.md'yi okuyun. Recovery üretiminde recovery Image ve recovery DT
birlikte kullanılmalı; native Image içine initramfs sonradan kendiliğinden eklenmez.

## Wi-Fi modülleri

Aynı OpenWrt build ağacında backports hazırlanıp son kernel config/headers ile:

```sh
make package/kernel/mac80211/compile -j4 V=s CONFIG_PACKAGE_kmod-cfg80211=m CONFIG_PACKAGE_kmod-mac80211=m CONFIG_PACKAGE_kmod-ath=m CONFIG_PACKAGE_kmod-ath11k=m CONFIG_PACKAGE_kmod-ath11k-ahb=m CONFIG_ATH11K_THERMAL=y
```

Yedi modül ve firmware/caldata eşleşmesi RADIOS.md'de. Modül vermagic ve
sürüm/hash kontrolünden sonra hedefe alınır. Wi-Fi init/start dosyaları root:root
executable/LF olarak yerleştirilir; eski CRLF autoload dosyası kullanılmaz.

## LTE modülleri

```sh
sh src/lte-modules/build.sh "$PWD/build/lte-modules"
```

Native kernel build hazır olmalı. Script boş/yeni output ister; Linux'tan
USB/serial/WWAN/WDM/QMI kaynaklarını kopyalar, sadece option ff:ff:40 girdisini
ekler, aynı toolchain/config ile derler. Dokuz `.ko` oluşur. Core kernel config'i
yeniden değiştirmeden module-feature macro'ları Kbuild'de verilir; farklı
config ile rastgele modül derlemek struct ABI'sini bozabilir. `usb-wwan.h`
private header'ının tireli adı korunmalıdır. Runtime liste `files/etc/modules.d/`.

## kexec-tools

OpenWrt'nin sabitlenmiş package tarifiyle kexec-tools2.0.32 kaynağını hazırlayın.
`KEXEC_SOURCE=/absolute/path/kexec-tools-2.0.32 sh tools/build_kexec.sh`.
Script statik AArch64 binary üretir; firmware yüklemez veya reboot etmez.
Stok 32-bit kernel bu binary ile otomatik kexec destekli hale gelmez.

## Offline kontroller

```sh
python3 tools/verify_export.py
python3 tools/test_offline.py
python3 -m compileall -q tools src/lte-modules
for script in tools/build_kernel.sh tools/build_kexec.sh tools/preflight.sh src/lte-modules/build.sh; do sh -n "$script" || exit; done
```

Bunlar kaynak/FDT/FIT/caldata yardımcılarının kontrolüdür; temiz tam kernel
build'in veya yeni firmware donanım boot testinin yerine geçmez. Public paket
hazırlanırken çalışan modem üzerinde yeniden flash işlemi yapılmadı.
