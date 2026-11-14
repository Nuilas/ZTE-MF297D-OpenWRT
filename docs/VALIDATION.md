# Doğrulama kaydı — 14 Kasım 2026

Kayıtlar tek MF297D üzerindeki çalışmadan alınan sonuçların özetidir. Ham
günlükler MAC, hat kimliği, komşu SSID, IP ve özel dosya yolları içerdiğinden
dağıtılmaz. Hash'ler imaj referansıdır; bu repodaki MAC şablonlarıyla yeni
derlenen imajın aynı hash'i vermesi beklenmez. Test arşivleri özel saklanır.

| Kontrol | Sonuç ve sınır |
| --- | --- |
| Native NAND | İki normal yazılımsal reboot, kalıcı overlay ve ayarlar geçti |
| Recovery | Yeni geniş-geometri RAM recovery gerçek cihazda boot edildi |
| RESET | Açılışta recovery seçimi test edildi; Linux runtime factory reset ayrı iş |
| NAND sınırı | Yüksek adres okuma/yazma alias kontrolü, tail kontrolü ve ön alan hash doğrulaması geçti |
| Overlay | 48 üst kayıt, 21 whiteout, 10 xattr taşındı; READY işareti korundu |
| LuCI | Kimlik doğrulanmış giriş/overview HTTP200; anonim kök403 olabilir |
| Wi-Fi | İki gerçek şifreli beacon, doğru kendi MAC'leri, iki reboot sonrası radyo başlangıcı |
| Wi-Fi hız | İstemci hız/menzil/çoklu istemci/DFS testi henüz yok |
| LTE | SIM/şebeke kaydı, QMI, kalıcı modüller ve otomatik bağlanma reboot testi geçti |
| LTE genel internet | Paket olmadığı için uçtan uca test tamamlanmadı; operatör sitesi erişildi |
| Güç döngüsü | Son iki reboot, fiziksel elektrik kes-aç testi değildir |
| Sysupgrade | Doğrulanmadı; genel kullanım için desteklenmiyor |
| Tam yeniden derleme | Kernel/module kaynak reçeteleri var; tüm userspace'in sıfırdan bit-eşdeğer üretimi yok |

## Bu kaynak paketi hazırlanırken yapılan kontroller

- Altı kernel kaynak dosyası SHA256 manifest kontrolü ve özel veri/desen taraması.
- Dört DT varyantının derlenmesi, 22 MTD ve yazılabilir bölüm sınırlarının testi.
- FDT encode/decode roundtrip, FIT hash yenileme/kernel değişmezliği ve bozuk
  template reddi; kalibrasyon checksum/MAC üretimi ve bozuk girdi reddi: 3 test.
- Windows ACS/Telnet uygulaması 15 sentetik test; TFTP yedek alıcısı 4 test geçti.
- Yeni taşınabilir LTE betiğiyle dokuz `.ko` gerçekten yeniden derlendi.
  MODULE_DESCRIPTION eksikliği uyarıları vardı; derleme hatası olmadı.
- Yeni FIT builder gerçek native Image ile offline üretildi; açılan Image aynı,
  CRC/SHA doğrulandı. Yeni FIT donanımda boot/flash edilmedi.
- Shell sözdizimi ve Python compile kontrolleri geçti. Tam kernel/userspace
  sıfırdan build veya çalışan cihaza yeniden kurulum bu yayımlama adımında yapılmadı.

## Son çalışan özel artefakt kimlikleri

| Artefakt | SHA256 |
| --- | --- |
| Native Image | d65bb3b1cbe206ad257feb98c782d4c46fd9c934b79e8ba7d98baee1e3ae5001 |
| Native Wi-Fi FIT | bc347d673be7006d7ae88ab609fb1369c223a80539d7fb100f15f5a1ee6bd882 |
| Geniş recovery FIT | 0c7daa3133dd70fc163a6900e985bdb3357c760c1e350742cc97fe908c20806e |
| Rootfs SquashFS | ec9c852ee0eeb8737591f8cfe405cbe1e799688d295d7ff19f20eee45adeccce |

Native FIT 4584620 bayt; CRC32 decimal861071048. Recovery FIT11377916 bayt.
Bu CRC'leri yeni imaj için kopyalamayın. ENV özel veriler içerir ve dağıtılmaz.
