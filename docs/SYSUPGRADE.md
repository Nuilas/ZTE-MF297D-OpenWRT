# OpenWrt'yi arayüzden güncelleme

Bu yöntem **bu projenin NAND OpenWrt'si kurulu ve `fit-v1` açılış desteği etkinleştirilmiş MF297D** içindir. Stok Turkcell panelinin yükleme yöntemi değildir.

## Güncelleme: bilgisayardaki tarayıcı

1. Güncel Release'ten **`openwrt-mf297d-nss-sysupgrade.bin`** dosyasını indir. Kendi derlemende dosya `bin/mf297d/` içindedir.
2. Modemin LAN portuna bağlan ve **<http://192.168.1.1>** adresini aç.
3. **System → Backup / Flash Firmware → Flash new firmware image** bölümüne gir. Türkçe arayüzde **Sistem → Yedekleme / Yazılım Yükleme**.
4. `sysupgrade.bin` dosyasını seç. Ayarların kalmasını istiyorsan **Keep settings / Ayarları koru** seçeneğini açık bırak.
5. İmaj doğrulandıktan sonra **Continue / Devam** ile yükle. Ethernet'i ve güç kablosunu bağlı bırak. Yazma, geri okuma ve açılış birkaç dakika sürebilir; panel otomatik dönmezse aynı adresi yeniden aç.

Günlük güncellemede Telnet, ACS, TFTP, kexec veya RESET tuşuna basma adımı yoktur.

**Dosya seçimi:** `...-sysupgrade.bin` arayüz içindir. `...-nand.bin`, `kernel.bin`, `rootfs.bin` ve `...-initramfs.itb` bu ekrana yüklenmez. Eski NAND paketi ayrı bir elle kurulum biçimidir.

**Ayarları koru**, OpenWrt'nin normal ayar yedeğini geri yükler. Yeni firmware'e eklemek istediğin paketleri de yeni derlemende seçmelisin. Seçeneği kapatırsan yeni firmware varsayılan ayarlarla açılır; kurtarma ve kalibrasyon yine korunur.

## Neler korunur?

| Alan | Güncelleme davranışı |
| --- | --- |
| `owrt_kernel` — UBI 4 | Yeni kernel yazılır ve geri okunarak doğrulanır. |
| `owrt_rootfs` — UBI 5 | Yeni rootfs yazılır ve SHA256 doğrulanır. |
| `rootfs_data` — UBI 6 | Kalan alanla yeniden oluşturulur; seçildiyse ayar yedeği geri yüklenir. |
| `owrt_recovery` — UBI 7 | **Silinmez, yazılmaz; işlem öncesi/sonrası hash karşılaştırılır.** |
| `wifi_fw`, `bt_fw` — UBI 1/2 | **Korunur ve hash karşılaştırılır.** |
| Bootloader, ENV, ART, MAC ve diğer MTD 0–20 | **Normal sysupgrade yazmaz; hash'ler karşılaştırılır.** |

Kurtarma, mevcut **fişi çıkar → RESET'e basılı tutarak fişi tak → 7 saniye sonra RESET'i bırak** seçimiyle kalır. Güncellemede ilk değişiklik ana kernel hacmini geçersizleştirmektir; yeni kernel yalnız rootfs ve ayarlar hazırlandıktan sonra en son yazılır. Geçerli ana FIT bulunamazsa açılış komutu korunan kurtarmaya geçer. Kernel açılıp sonradan takılırsa RESET seçimi kullanılabilir.

## Ubuntu / VMware içinde kendi firmware'ini derleme

Mevcut `.config` ve seçtiğin paketler korunur:

```sh
cd ~/MF297D
git pull
cd ~/build-mf297d-nand
cp .config .config.backup
make menuconfig
JOBS=8 sh ~/MF297D/nss/build.sh nand "$PWD"
```

Arayüze yükleyeceğin dosya:

```text
~/build-mf297d-nand/bin/mf297d/openwrt-mf297d-nss-sysupgrade.bin
```

Kontrol:

```sh
cd ~/build-mf297d-nand/bin/mf297d
sha256sum -c SHA256SUMS
```

Paketleme ve yükseltme yardımcısının derlenmesi için son adımda **`nss/build.sh`** kullanılır. Yalnız `make` çalıştırmak bu ek paketleme adımının yerine geçmez. Temiz alanın ilk hazırlanması [NSS derleme belgesinde](NSS-GUNCELLEME.md#3-ubuntuda-paket-ekleyip-derleme) anlatılıyor.

## Eski kurulumlarda tek seferlik etkinleştirme

Eski açılış komutu kernelin sabit uzunluk/CRC değerini taşıdığı için yalnız dosya üretmek yeterli değildir. Açılış bir kez FIT doğrulamalı düzene geçirilir; sonraki sysupgrade işlemleri ENV'ye dokunmaz. [Bir defalık geçişin adımları](SYSUPGRADE-BOOTSTRAP.md).

Kontrol komutu:

```sh
ssh root@192.168.1.1 '/usr/libexec/mf297d-upgrade-guard --check-env /dev/mtd10ro'
```

`MF297D sysupgrade boot layout ready` sonucu hazır olduğunu gösterir. Bu geçişi yeniden çalıştırma.

## Test edilenler — 21 Kasım 2026

Gerçek cihazda `sysupgrade -T`, LuCI'nin `system.validate_firmware_image` doğrulayıcısı ve ayarları koruyan **gerçek `/sbin/sysupgrade` NAND yükseltmesi** geçti. Yeni kernel/rootfs hash'leri, ayar yedeği, SSH kimliği ve korunan bölüm hash'leri karşılaştırıldı. Yükseltme desteğinin yeni `/rom` içinde bulunduğu doğrulandı. İki CPU, NSS, iki Wi-Fi AP ve LuCI tekrar açıldı; kernel WARN/oops sayısı sıfırdı. SIM olmadığı için bu yükseltmede LTE internet testi yapılmadı.

18 imaj/ENV/RESET akış testi ve 7 flash hata senaryosu testi de geçti. Testler ve yardımcı kaynakları `nss/tests/`, `nss/src/upgrade_guard.c`, `nss/overlay/files/lib/upgrade/mf297d.sh` ve `tools/upgrade_boot.py` altındadır. FIT'in `bootm` ile hash doğrulaması [U-Boot belgesinde](https://docs.u-boot.org/en/latest/usage/fit/howto.html) açıklanır.
