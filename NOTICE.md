# Kaynak kökeni ve lisanslar

## Telnet CFG yardımcısı

`tools/telnet_cfg.py` GPL-2.0-only lisanslı proje kodudur. Windows EXE'si
Python 3.14/Tcl-Tk ve PyInstaller 6.22.3 ile paketlenir; ilgili lisans ve
bootloader istisnası `mf297d-telnet-source.zip` içindedir. Araç yalnız yerel
CFG dosyasında LAN Telnet değerini değiştirir. Test cihazının kişisel CFG'si
dağıtılmaz. ACS yönetici EXE'sinin kaynakları `tools/windows-manager/` altındadır.

- Temel ağaç: https://git.openwrt.org/openwrt/openwrt.git,
  commit `bb6df54d9d1cb486f7102e9863f0380cb9f3a1f3`.
- Linux 6.18.55; hazırlanan OpenWrt kernel ağacından seçilen sürücüler
  `src/kernel/` içindedir. Her dosyanın SPDX/telif bildirimi korunur; Linux
  GPL-2.0 metni `LICENSES/GPL-2.0.txt` içindedir. İlk port patch'i tarihsel
  referanstır; son hazırlanmış kaynak overlay'i derlemede önceliklidir.
- Wi-Fi backports 7.2: OpenWrt package/kernel/mac80211 Makefile kaynağı ve
  sabit SHA256; sürücü/binary lisansları upstream'de korunur.
- kexec-tools 2.0.32: https://git.kernel.org/pub/scm/utils/kernel/kexec/kexec-tools.git/;
  kendi upstream lisans koşulları geçerlidir.
- `reference/rootfs/` seçilmiş OpenWrt shell kaynaklarını ve package world
  listesini içerir; tam rootfs veya tüm corresponding-source arşivi değildir.
- `tools/windows-manager/` proje MIT lisansını ve üçüncü taraf bildirimlerini
  içerir; Npcap ayrı kurulur ve kendi lisansı geçerlidir. Orijinal TR069ACS_4/5
  EXE dosyaları bu uygulamanın kaynakları değildir ve burada dağıtılmaz.
- DTS'ler test edilen decompile ağacından, cihaz MAC'leri anonimleştirilerek
  üretilmiştir. Bütün initial userspace'in temiz kaynak rebuild'i tamamlanmadı.
- Kapalı kaynak Qualcomm/ZTE modem/radyo firmware, ART/caldata, bootloader,
  gerçek cihaz ENV'si ve kullanıcı rootfs yedekleri dağıtılmaz. Her cihaz kendi
  orijinal yedeğinden bunları sağlamalıdır; yeniden dağıtım hakkı varsayılmaz.

Bu depoyu tam binary firmware yayınının bütün corresponding-source yükümlülüğünü
karşılayan eksiksiz bir sürüm olarak değerlendirmeyin: source-lock ve TODO
eksik userspace/paket yeniden üretimini açıkça kaydeder. Yeni binary sürüm
yayımlanmadan önce kaynak/provenance/lisans kapsamı tamamlanmalıdır.

## 14 Kasım 2026 binary ön sürümü

Release, mevcut cihazda test edilmiş kernel payload'larını içerir. FIT DTB'leri
MAC şablonuna dönüştürülmüştür; kişiselleştirme aracı payload'ı değiştirmez.
NSS RAM rootfs'i sabit commit/feed/config ile kaynaklardan yeni üretilmiştir;
eski kullanıcı overlay'i veya cihaz yedeği değildir. Native dosya yalnız
kernel bileşenidir; ilk sağlanan userspace/rootfs binary'si dağıtılmaz.
NSS kaynak entegrasyonu ayrıca Release asset'i olarak verilir; taban kaynak
ve feed commitleri pakette kayıtlıdır. kexec binary'sinin kaynağı kexec-tools
2.0.32 ve bu depodaki build_kexec.sh reçetesidir.

## 20 Kasım 2026 NSS kaynak ve binary ön sürümü

Güncel kaynak tabanı kuncy7/openwrt-nss-edma,
593ffa8e281c0a4ab17fd52365aecb546bfaf442; Linux 6.18.60'tır.
nss/SOURCE.json ve feeds-lock.json tam kaynak sürümlerini kaydeder.
nss/openwrt.patch, overlay ve feed-overlay proje değişiklikleridir.
Eski src/config belgeleri tarihsel 6.18.55 portuna aittir.

mf297d-unsquashfs, squashfs-tools 4.7.5 (GPL-2.0-or-later) ve XZ 5.8.4
liblzma kullanır. Kaynak indirme adresleri/hashleri ve derleme komutları
nss/tools/build-radio-reader.py ile nss/src/reader-build.json içindedir.
Squashfs-tools: https://github.com/plougher/squashfs-tools ;
XZ: https://tukaani.org/xz/ (liblzma ağırlıklı olarak 0BSD/public domain;
dosya bazında upstream SPDX/lisans bildirimleri geçerlidir).
Kendi factory_data.c yardımcısının lisansı dosya başlığındadır.
Kexec için tools/build_kexec.sh ve kexec-tools 2.0.32 kaynakları geçerlidir.

Genel imajlar çalışan derleme çıktılarının temizlenmiş türevleridir.
Kapalı radyo firmware veya kişisel kalibrasyon dağıtılmaz; kendi cihazının
korunmuş wifi_fw ve ART verileri çalışma anında okunur. Genel profil ve
genelleştirilmiş NAND kurucu tam canlı kurulum testinden geçmemiştir.
Temiz reçete kontrolü tam bit-eşdeğer yeniden üretim iddiası değildir.
