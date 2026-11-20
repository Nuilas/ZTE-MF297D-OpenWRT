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
  DTS derlemesi ve shell sözdizimi kontrol edildi. Tam temiz derleme henüz yapılmadı; yeni genel RAM imajının canlı testi aşağıdadır.

## Sınırlar

CPU1 artık S18 başlangıç servisiyle açılır; erken açılışta maxcpus=1 korunur. İki
CPU ve NSS/iki Wi-Fi radyosu yeniden açılışta birlikte doğrulandı. Her CPU’ya
sabitlenen 64 MiB SHA256 işleri geçti; bootloader/ENV değişmedi. SQM, uzun
süreli yük, bütün Ethernet portları arasında hız ve bağlantı kopma/toparlanma
testleri tamamlanmadı. SIM/APN ve Wi-Fi kullanıcı tarafından ayarlanmalıdır.

NAND `.bin` standart factory/sysupgrade imajı değildir: kernel.bin,
rootfs.bin ve manifest içeren tar paketidir. Genel kurulum araçları yalnız
mevcut proje bölüm/ENV düzenini kabul eder. Yeni stoktan ilk kurulum kiti
`stock/` altında ayrıdır ve henüz canlı stok cihazda doğrulanmadı.
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


## Yeni kurulum kiti — 20 Kasım

- CPU ve modemin ADB üzerinden yönetilen Wi-Fi LED servisi yeni genel imajlara eklendi.
- Yeni genel rootfs gerçek 6.18.60 üzerinde yalnız /tmp'ye salt okunur loop bağlandı:
  BusyBox chroot, ADB1.0.32 ve servis shell sözdizimi geçti. ENV değişmedi, reboot yapılmadı.
- IPv6 iki sanal eş fiziksel LAN üzerinden 2400/2400 UDP; NSS hash hit +2397,
  ECM IPv6 hızlandırılmış akış1, WARN/oops0. Operatör IPv6 WAN testi değildir.
- Stok modüllerin gerçek ARM32/ARM64 kod emülasyonu, bozuk CRC reddi ve istisna
  dönüşü geçti. U-Boot hush 14 senaryo geçti; donanım etkileri modellenmiştir.
- Gerçek ilk hazırlama CLI'si kendi stok yedeklerini kullanan çevrimdışı aygıt
  adaptöründe çalıştı: 25 fiziksel/4 UBI yedeği, ENV derlemesi, RAM profilleri ve
  UBIFS üretimi geçti. Bu, canlı flash veya elektrik kesintisi testi değildir.
- İkinci stok cihaz yok; kullanıcı mevcut OpenWrt'nin korunmasını istedi.
  Yeni stok yükleyicisi ve ilk NAND canlı testi yapılmadı. Bu yüzden kit ön sürüm olarak kalır.
- Uzun süreli yük, fiziksel WAN hız testi ve SQM doğrulaması tamamlanmadı.
  Bu özellikler için test yapılmış/kararlılık garantisi verilmiş değildir.

## Genel RAM imajının canlı testi — 20 Kasım

İlk denemede NSS kapalı olsa da kaynak çekirdekte CPU1/Wi-Fi daha önce çalışmıştı:
RAM açıldı, fakat CPU1 açılamadı ve Q6 zaman aşımı/WARN görüldü. Bu başarısız deneme
gizlenmedi. Kaynak NAND'a dönüldü; firmware/ENV/ART/MAC/kurtarma hashleri ve kullanıcı
ayarları birebir doğrulandı. Çözüm: kexec öncesindeki tek açılışta CPU1, NSS ve radyo
başlangıcını atlamak; orijinal başlangıç dosyalarını RAM geçişinden önce geri koymak.
`tools/prepare_ram_boot.py` ve güncel RAM yönergesi bu sırayı kullanır.

İkinci denemede yayımlanan genel RAM imajı açıldı: Linux6.18.60, CPU0-1, etkin NSS,
22 fiziksel MTD salt okunur, UBIFS kök yok, WARN/oops0. Kendi wifi_fw/ART verilerinden
radyo hazırlığı tamamlandı. Wi-Fi varsayılan olarak kapalı kaldı; yalnız RAM'de kendi
Wi-Fi ayarları uygulanınca iki AP ve iki NSS radyo kaydı açıldı, her radyoda gönderim
sayacı arttı. LED servisi çalıştı, iç modemde brightness4 geri okundu. Fiziksel ışığın
görülmesi ve yeni RAM profilinde telefonla çift yönlü Wi-Fi testi ayrıca doğrulanmalıdır.
IPv4 ve IPv6 ayrı ayrı fiziksel LAN'daki sanal eşler arasında 2400/2400 UDP iletildi;
IPv6 NSS hash hit +2397, ECM1. Bunlar WAN/operatör IPv6 veya hız testleri değildir.
NAND firmware veya ENV bu RAM testlerinde yazılmadı.
