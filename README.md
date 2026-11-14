# ZTE MF297D — OpenWrt

ZTE MF297D için geliştirilen OpenWrt portu. Çalışan NAND sisteminde Ethernet,
LuCI, iki Wi-Fi radyosu ve QMI/LTE bağlantısı var. Yeni NSS sürümü şu an
**RAM'de test ediliyor**; kablolu NSS hızlandırması doğrulandı.

## İndirilecek dosyalar

**[Firmware dosyalarını Release bölümünden indir](https://github.com/ozgunokan/ZTE-MF297D-OpenWRT/releases/tag/mf297d-2026.11.14-preview.1)**

| Dosya | Ne için? |
| --- | --- |
| `openwrt-mf297d-6.18.60-nss-ram-template.itb` | Tam RAM sistemi: yeni kernel, rootfs ve kablolu NSS. Aşağıdaki adımlarla geçici çalışır. |
| `mf297d-ram-tools.zip` | MAC hazırlama aracı, kexec ve RAM başlatma betiği. |
| `openwrt-mf297d-6.18.55-native-kernel-template.itb` | Çalışan NAND sürümünün kernel bileşeni. Tek başına tam kurulum değildir; mevcut eşleşen rootfs ve boot ayarı gerekir. |
| `mf297d-nss-source-integration.zip` | NSS derlemesinin DTS, patch, config ve sabit kaynak sürümleri. |
| `SHA256SUMS` | İndirilen dosyaları kontrol etmek için SHA256 listesi. |

Dosya adındaki `template`, Ethernet MAC adreslerinin örnek olduğu anlamına gelir.
Aşağıdaki araç kendi cihazınızın MAC adreslerini dosyaya işler. Başka cihaza ait
ART, kalibrasyon, şifre veya NAND yedeği indirmeye gerek yoktur.

## Stok Turkcell yazılımından ilk kurulum

**Stok panelden yüklenebilen factory imajı henüz yok.** Release'teki `.itb`
dosyalarını stok panelin güncelleme bölümüne yüklemeyin. Mevcut NAND geçişi bir
cihazda tamamlandı; başka stok cihaza uygulanacak genel manuel NAND yükleyicisi
henüz doğrulanmadı. Stoktan geçişin aşamaları [burada](docs/INSTALL.md).

Şu an aşağıdaki kısa yöntem, **bu projedeki OpenWrt 6.18.55 portu zaten kurulu
olan MF297D** içindir. Stok Telnet oturumunda çalışmaz.

## Manuel kurulum: NSS sürümünü RAM'de çalıştırma

Kalıcı sistemi değiştirmeden denemek için. İşlem sonunda normal yeniden
başlatma mevcut NAND sistemini açar. İlk NSS RAM sürümünde Wi-Fi kapalıdır.

### 1. Bağlan ve indir

Bilgisayarı modemin **LAN1/LAN2/LAN3** portlarından birine bağla. PC aynı ağda
olsun; örneğin `192.168.1.2 / 255.255.255.0`. Modem: `192.168.1.1`.

Release'ten NSS RAM `.itb` dosyasını, `mf297d-ram-tools.zip` ve `SHA256SUMS`
dosyasını indir. ZIP'i aç; NSS `.itb` dosyasını `mf297d-ram-tools` klasörüne koy.
Bilgisayarda Python 3 ve SSH/SCP bulunmalı; Windows Terminal kullanılabilir.

### 2. Kendi MAC adreslerini öğren

Terminalde:

```sh
ssh root@192.168.1.1 "cat /sys/class/net/eth0/address; cat /sys/class/net/wan/address"
```

İlk satır LAN, ikinci satır WAN adresidir. Aşağıdaki komuttaki `LAN_MAC` ve
`WAN_MAC` yerlerine bu iki değeri yaz. Önce `mf297d-ram-tools` klasörüne geç:

```sh
python personalise_release.py openwrt-mf297d-6.18.60-nss-ram-template.itb --lan-mac LAN_MAC --wan-mac WAN_MAC
```

Komut `ready` klasörünü oluşturur; henüz modeme bir şey yüklemez.
Windows'ta `python` bulunmazsa `py` kullan.

### 3. Dosyaları RAM'e gönder

```sh
ssh root@192.168.1.1 "mkdir -p /tmp/mf297d-ram"
scp -O ready/* kexec-aarch64 ram-boot-manual.sh root@192.168.1.1:/tmp/mf297d-ram/
ssh root@192.168.1.1 "sh /tmp/mf297d-ram/ram-boot-manual.sh"
```

SSH bağlantısı kesilir; yaklaşık bir dakika bekle. Betik cihaz/sürüm ve dosya
hash'lerini kontrol eder, radyoları durdurur, yeni sistemi RAM'den başlatır.
NAND veya boot ortamına firmware yazmaz. Bu komut için root SSH erişimi gerekir.

### 4. Giriş yap ve NSS'yi aç

Tekrar bağlanıp önce test süresini uzat:

```sh
ssh -o HostKeyAlias=mf297d-ram-test root@192.168.1.1
```

RAM sisteminin SSH anahtarı farklıdır; bu yüzden ayrı bir HostKeyAlias kullanılır.
İlk bağlantıda gösterilen anahtarı onayla. Modemin terminalinde:

```sh
echo 1200 > /tmp/mf297d-nss-guard-deadline
uname -r
uci set nss.general.enabled='1'
uci set nss.general.wifi_offload='0'
uci commit nss
/etc/init.d/nss start
```

`uname -r` sonucu **6.18.60** olmalı. Panel: **http://192.168.1.1/**.
Kontrol etmek için:

```sh
nss-status -j
cat /sys/kernel/debug/qca-dwmac-nss/status
```

`state: active` ve `phys_if 1: started` görülmeli. Gerçek yönlendirilmiş trafik
olmadan ECM bağlantı sayısı sıfır kalabilir; panelin açılması hızlandırma testi
değildir.

### 5. Mevcut sisteme dön

```sh
reboot
```

İlk açılışta süre uzatılmazsa RAM testi yaklaşık 3 dakika sonra kendisi döner.
Yukarıdaki `1200` değeri, açılıştan itibaren 20 dakika sonra otomatik dönüş
sağlar. Ayarlar RAM'de kalır; NAND'a kalıcı NSS kurulumu yapılmış olmaz.

## Neler çalışıyor?

| Bileşen | Durum |
| --- | --- |
| NAND OpenWrt 6.18.55 | Normal açılış, LuCI ve büyük overlay doğrulandı |
| Overlay | Yaklaşık 155 MiB toplam |
| Wi-Fi, NAND sürümü | IPQ5018 2.4 GHz + QCN6122 5 GHz çalışıyor |
| LTE, NAND sürümü | QMI/raw-IP bağlantısı ve otomatik bağlanma çalışıyor; paketli SIM ile genel internet testi bekliyor |
| Kablolu NSS, RAM 6.18.60 | 2400/2400 paket çift yönlü iletildi; firmware 2397 pakette hızlandırma hit'i saydı |
| Wi-Fi NSS | Entegrasyon/test sürüyor; henüz doğrulanmadı |
| LTE NSS/rmnet_rx | Bu modem RAM testinde rmnet_rx node 30’a bağlandı; LTE trafik hızlandırması henüz doğrulanmadı |
| CPU | CPU0 kullanılıyor; ikinci çekirdek sorunu açık |
| Genel factory/sysupgrade | Henüz yok |

Test tek fiziksel LAN bağlantısındaki iki sanal uçla yapıldı; gigabit hız,
WAN/NAT ve uzun süreli kararlılık sonucu değildir. RAM testinden sonra kurulu
kernel/rootfs/recovery ile korunan flash alanlarının hash'leri aynı bulundu.

## Kaynak ve teknik belgeler

- [Derleme](docs/BUILD.md) · [NAND geçişinin teknik sırası](docs/INSTALL.md)
- [Wi-Fi/LTE ayarları](docs/RADIOS.md) · [Kurtarma](docs/RECOVERY.md)
- [Donanım ve bölüm düzeni](docs/ARCHITECTURE.md)
- [Testler](docs/VALIDATION.md) · [Kalan işler](docs/TODO.md)
- [Kaynak kökeni ve lisanslar](NOTICE.md)

NAND sürümü 6.18.55 kaynakları bu depoda; NSS 6.18.60 entegrasyonu Release'teki
kaynak paketindedir. Kaynak DTS'leri anonim MAC kullanır. Her cihaz kendi
ART/kalibrasyonunu korumalıdır; kişisel yedekler, gerçek ENV ve özel ayarlar
Release'e eklenmez.
