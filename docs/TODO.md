# Kalan işler

## Öncelik 1 — dağıtılabilir ve güncellenebilir sürüm

- [ ] Tam userspace/feeds/paket kaynaklarını sabitleyip sıfırdan temiz build;
  arkadaşın initramfs'inden gelen rootfs bağımlılığını kaldırma.
- [ ] Dekompile DTS'yi upstream IPQ5018 dtsi yapısına taşıma; kart profili,
  Wi-Fi/LTE paket seçimi, own-unit kalibrasyon/MAC üretimi.
- [ ] Factory/sysupgrade akışı; FIT CRC ve ENV koordinasyonu; imaj boyutu,
  recovery korunması, yanlış cihaz engeli ve güncelleme sonrası rollback.
- [ ] ENV/UBI geçişinde güç kesilmesi testi ve kurtarma tasarımı. UART'sız
  tüm hata türleri için garantili kurtarma şu anda yok.
- [ ] Fiziksel güç kes-aç, art arda reboot, overlay veri bütünlüğü, yeni build
  için recovery gerçek boot'u; birden fazla MF297D/revizyonda tekrar.

## Öncelik 2 — donanım ve bağlantı

- [ ] CPU1/SMP, PSCI ve warm-boot sorunu; maxcpus=1 sınırını kaldırma.
- [ ] Paketli SIM ile genel internet/HTTPS/DNS/hız; IPv6/IPv4v6, bant/CA,
  PIN, SIM çıkar-tak, şebeke kesintisi, otomatik tekrar bağlanma ve farklı operatör.
- [ ] LTE AT/QMI modem kontrolü için kalıcı, kişisel bilgiyi sızdırmayan tanı;
  uzun süre modem/USB autosuspend kararlılığı.
- [ ] Wi-Fi gerçek istemci aktarımı/menzil/çoklu istemci, 2.4/5GHz eşzamanlı,
  DFS/kanal genişlikleri ve uzun süre Q6 kararlılığı.
- [ ] Her LAN ve WAN portu için link hızı, VLAN/bridge ayrımı, DHCP/NAT,
  WAN failover ve donanım hızlandırma. PC tarafında görülen 100Mbps'i cihaz
  donanım sınırı diye kabul etmeyin; kablo/port/negotiation ayrıca ölçülmeli.
- [ ] RESET/WPS runtime işlevleri, LED isimleri ve güç kontrol GPIO ayrımı.
- [ ] Sıcaklık, watchdog, yük altında güç/kararlılık ve soak testleri.

## Öncelik 3 — bakım ve araçlar

- [ ] Varsayılan güvenli yönetim parolası oluşturma/ilk kurulum akışı,
  SSH/WAN erişimi ve firewall incelemesi; stok Telnet'ten arındırılmış kullanım.
- [ ] CI: temiz kernel/DTS/modül build, kaynak/lisans manifesti ve artefakt imzası.
- [ ] Upstream OpenWrt'ye kart desteği için incelenebilir patch serisi.
- [ ] Windows ACS/Telnet uygulamasının fabrika ayarlı stok cihazda paketlenmiş
  EXE ile uçtan uca testi, kurulum/kaldırma ve ağ geri alma testleri.

Yapıldı: tek OpenWrt NAND, büyük overlay, RAM recovery, kalıcı çift bant Wi-Fi,
SIM/LTE/QMI tanıma ve yeniden başlatma sonrası modem bağlantısı.
