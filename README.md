# ZTE MF297D — OpenWrt geliştirme kaynakları

Bu depo, bir ZTE MF297D üzerinde yapılan stok yazılımdan **tek OpenWrt NAND**
sistemine geçişin kaynaklarını, cihaz ağacını ve doğrulama sonuçlarını içerir.
Son durum: 14 Kasım 2026. Bu bir upstream OpenWrt sürümü veya her MF297D için
denenmiş otomatik kurucu değildir. Genel factory/sysupgrade desteği henüz yoktur.

| Bileşen | Doğrulanan durum |
| --- | --- |
| Sistem | Linux 6.18.55, AArch64, OpenWrt SNAPSHOT r36880-bb6df54d9d |
| NAND | 256 MiB; son 211.25 MiB UBI; stok işletim sistemi kaldırıldı |
| Overlay | 1399 LEB, `df` ile yaklaşık 155 MiB toplam, kurulum sonrası yaklaşık 144 MiB boş |
| Açılış | Normal NAND açılışı ve RESET ile OpenWrt RAM kurtarma; stok ile dual boot yok |
| Ethernet / LuCI | LAN yönetimi ve kimlik doğrulanmış LuCI çalışıyor |
| Wi-Fi | IPQ5018 + QCN6122; iki WPA2/WPA3 erişim noktası gerçek taramada görüldü |
| LTE | SIM READY, LTE kayıt, QMI bağlantısı ve yeniden başlatma sonrası otomatik bağlantı |
| LTE internet | Operatör sitesi erişimi var; SIM'de paket yok, genel internet/hız testi bekliyor |
| CPU | Yalnız CPU0; SMP/PSCI sorunu açık |

## Belgeler

- [Derleme ve kaynakların sabitlenmesi](docs/BUILD.md)
- [Stoktan geçiş ve kurulum sırası](docs/INSTALL.md)
- [NAND, UBI ve açılış mimarisi](docs/ARCHITECTURE.md)
- [Kurtarma ve güncelleme sınırları](docs/RECOVERY.md)
- [Wi-Fi ve LTE kurulumu](docs/RADIOS.md)
- [Yapılan testler ve kanıt sınırları](docs/VALIDATION.md)
- [Kalan işler](docs/TODO.md)
- [Dosyalar, lisans ve kaynak kökeni](NOTICE.md)

`src/kernel/` testte kullanılan hazırlanmış Linux ağacından seçilen gerçek
sürücü kaynaklarını içerir; yalnız ilk deneme patch'inden oluşmaz.
`dts/` çalışan cihaz ağacının MAC adresleri anonimleştirilmiş şablonlarıdır.
`files/` kalıcı Wi-Fi başlangıç servisini ve LTE modül listesini içerir.
`tools/windows-manager/` stok yazılım için bağımsız ACS/Telnet/yedekleme
uygulamasının kaynaklarıdır; uygulama hâlâ prototiptir, NAND kurucusu değildir.

**Cihaza özgü ART, MAC, modem kimlikleri, yedekler, şifreler, özel rootfs ve
kapalı kaynak radyo firmware dosyaları burada dağıtılmaz.** Her cihaz kendi
kalibrasyonunu kullanmalıdır. Bu depodan alınan kodla üretilen yeni FIT'in boyut
ve CRC'si değişir; mevcut cihazın CRC kilitli bootcmd'sine doğrudan uymaz.
