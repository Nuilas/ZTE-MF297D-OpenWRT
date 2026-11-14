# Kaynak kökeni ve lisanslar

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
