# NSS sürümü — 20 Kasım 2026

Kurulum komutları ana [README](../README.md) içindedir.

## Doğrulananlar

- Cihaza özel çalışan NAND sisteminde Linux 6.18.60, NSS 12.5-210-MP.R,
  Ethernet ve iki Wi-Fi radyosu açıldı; iki normal NAND açılışı geçti.
- RAM testlerinde 5 GHz ve 2,4 GHz istemci trafiği ayrı ayrı NSS sayaçlarıyla
  doğrulandı. NAND sisteminde LTE DNS testi 48/48 geçti ve hızlandırılmış
  IPv4 trafiği sayacı arttı. Bu testler hız veya uzun süreli kararlılık ölçümü değildir.
- Yayın için kişisel ayarlar, SSH anahtarları, MAC adresleri, ART ve radyo
  dosyaları çıkarıldı. Genel profil kendi cihazının korunmuş wifi_fw/ART
  verisini kullanır. Radyo hazırlama aracı çalışan cihazda yalnız /tmp'ye
  yazarak test edildi: 33 firmware ve iki kalibrasyon dosyası birebir eşleşti.
- FIT hashleri, 4 KiB rootfs hizası, initramfs konsol aygıtı ve kişisel veri
  taraması geçti. RAM çekirdeğinin CPIO dışındaki kod/verileri değiştirilmedi.
- Sabit kaynak/feed sürümleri temiz Ubuntu ağacında uygulanıp defconfig,
  DTS derlemesi ve shell sözdizimi kontrol edildi. Tam temiz derleme ve
  yayımlanan genel profilin bütün olarak canlı açılışı henüz yapılmadı.

## Sınırlar

CPU1 artık S18 başlangıç servisiyle açılır; erken açılışta maxcpus=1 korunur. İki
CPU ve NSS/iki Wi-Fi radyosu yeniden açılışta birlikte doğrulandı. Her CPU’ya
sabitlenen 64 MiB SHA256 işleri geçti; bootloader/ENV değişmedi. IPv6 NSS, SQM, uzun
süreli yük, bütün Ethernet portları arasında hız ve bağlantı kopma/toparlanma
testleri tamamlanmadı. SIM/APN ve Wi-Fi kullanıcı tarafından ayarlanmalıdır.

NAND `.bin` standart factory/sysupgrade imajı değildir: kernel.bin,
rootfs.bin ve manifest içeren tar paketidir. Genel kurulum araçları yalnız
mevcut proje bölüm/ENV düzenini kabul eder; stoktan ilk kurulum desteklenmez.
Araçların çevrimdışı kontrolleri geçti, fakat genelleştirilmiş yeni kurucu
canlı flash testinden geçmedi. Kurtarma birimi korunur; UART olmadan
bootloader/ENV değişikliklerinin geri dönüşü güç olabilir.

## Kaynak

Güncel NSS reçetesi [nss/](../nss/) içindedir. Önceki `src/`, `config/` ve
BUILD-LEGACY belgeleri ilk portun tarihsel kaydıdır. Release imajları
çalışan derleme çıktılarından temizlenerek paketlenmiştir; temiz reçeteyle
bit düzeyinde yeniden üretilebilirlik iddiası yoktur.

CPU1 için Linux CPU hotplug arayüzü kullanılır: [kernel belgesi](https://docs.kernel.org/core-api/cpu_hotplug.html). Servis kaynağı: [mf297d-cpu](../nss/overlay/files/etc/init.d/mf297d-cpu).

İki CPU açıkken fiziksel LAN üzerinden iki sanal eş arasında 2400/2400 UDP paket
iletildi; NSS IPv4 hash hit artışı 2397 ve ECM hızlandırılmış akış sayısı 1 oldu.
Bu, fiziksel WAN hız testi değildir. CPU servisiyle iki normal NAND açılışı geçti.
