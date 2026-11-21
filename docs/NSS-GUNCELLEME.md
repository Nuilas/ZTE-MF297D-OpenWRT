# ZTE MF297D — OpenWrt + NSS

**Günlük güncelleme için yeni yöntem:** [LuCI'den sysupgrade](SYSUPGRADE.md).
Arayüze yüklenen dosya **`openwrt-mf297d-nss-sysupgrade.bin`**. Aşağıdaki
`...-nand.bin` ve RAM bakım adımları eski/elle kurulum yoludur; normal
arayüz güncellemesinde çalıştırılmaz. Önceki kurulumlarda bir kez
[FIT açılış desteği](SYSUPGRADE-BOOTSTRAP.md) etkinleştirilir.

MF297D üzerinde NAND'dan çalışan OpenWrt 6.18.60 portu. Ethernet, 2,4/5 GHz
Wi-Fi NSS ve QMI/LTE `rmnet_rx` hızlandırması doğrulandı. İki normal NAND
yeniden başlatması ve gerçek LTE trafiği test edildi. İki CPU, başlangıç servisiyle etkin;
IPv4/IPv6 NSS yolu sanal eşlerle test edildi; WAN hızı, uzun süreli kararlılık ve SQM testleri tamamlanmadı.

## İndir

**[Güncel firmware ve araçlar — Release](https://github.com/ozgunokan/ZTE-MF297D-OpenWRT/releases/tag/mf297d-2026.11.20-install-kit.3)**

| Dosya | Kullanım |
| --- | --- |
| `openwrt-mf297d-6.18.60-nss-initramfs.itb` | Geçici RAM sistemi; yeniden başlatınca NAND'a dönülür. |
| `openwrt-mf297d-6.18.60-nss-nand.bin` | Özel proje NAND düzeni için kernel + hizalı rootfs paketi. |
| `mf297d-tools.zip` | Kexec, kişiselleştirme ve kontrollü NAND hazırlama araçları. |
| `mf297d-nss-source.zip` | DTS, yamalar, sabit kaynak/feed sürümleri ve derleme profilleri. |
| `SHA256SUMS` | İndirilen dosyaların SHA256 değerleri. |

**NAND `.bin`, tar biçiminde bir bileşen paketidir; stok web paneline veya
standart `sysupgrade` komutuna doğrudan verilmez.** Stok Turkcell sisteminden
ilk NAND geçişini yapan genel factory imajı yok. Aşağıdaki NAND yöntemi yalnız
bu projenin OpenWrt portu zaten kurulmuş cihazlar içindir.

Yayın imajlarında kişisel Wi-Fi şifresi, SSH anahtarı veya başka cihaza ait
ART/caldata bulunmaz. Cihaz kendi korunmuş `wifi_fw` birimini ve ART'ını okur;
desteklenen radyo dosyaları hash kontrolünden geçer. Wi-Fi ve LTE bağlantısı
genel imajda kullanıcı yapılandırmasına bırakılır. Çalışan kernel/modüller
korundu; yeni genel profil bütünüyle canlı flash edilmedi. Ayrıntılar:
[test kapsamı](NSS-RELEASE.md).

## 1. RAM'de deneme

Gerekenler: bu portta çalışan 64 bit OpenWrt, root SSH ve kexec desteği.
PC'yi **LAN1/LAN2/LAN3** portlarından birine bağla. Modem `192.168.1.1`,
PC örneğin `192.168.1.2/24` olsun. Ubuntu terminalini kullan.

Release'ten initramfs dosyasını ve araç ZIP'ini indir. ZIP'i aç; imajı
`mf297d-tools` klasörüne koy:

```sh
cd ~/mf297d-tools
ssh root@192.168.1.1 'cat /sys/class/net/eth0/address; cat /sys/class/net/wan/address'
```

Çıkan ilk adresi `LAN_MAC`, ikinciyi `WAN_MAC` yerine yaz:

```sh
python3 tools/personalise_release.py openwrt-mf297d-6.18.60-nss-initramfs.itb --lan-mac LAN_MAC --wan-mac WAN_MAC
```

RAM geçişinden önce **CPU1, NSS ve Wi-Fi'nin hiç başlatılmadığı tek bir açılış**
gerekir. Yalnız NSS'yi kapatmak yeterli değildir: sıcak geçişte CPU1 açılamayabilir
ve Wi-Fi işlemcisi zaman aşımına düşebilir. Araç mevcut başlangıç dosyalarını ve
NSS ayarlarını PC'deki özel klasöre yedekler; bir kez atlama işareti tüketilir.
Firmware/ENV yazılmaz. Önce:

```sh
sudo apt install python3-paramiko
python3 tools/prepare_ram_boot.py stage --out ~/mf297d-ram-startup-private
ssh root@192.168.1.1 reboot
```

Yaklaşık **2 dakika** bekle. Mevcut başlangıç dosyalarını geri koy; bu komuttan
sonra servisleri yeniden başlatma, aşağıdaki RAM adımına geç:

```sh
python3 tools/prepare_ram_boot.py restore --out ~/mf297d-ram-startup-private
```

Vazgeçersen `restore` sonrasında `ssh root@192.168.1.1 reboot` ile normal
NAND'a dön. Yedek klasörü özeldir; GitHub'a yükleme. Root parolası varsa araç
terminalde sorar; parola dosyaya yazılmaz.

Şimdi dosyaları gönderip RAM'den başlat:

```sh
ssh root@192.168.1.1 'mkdir -p /tmp/mf297d-ram'
scp -O ready/* kexec-aarch64 tools/ram-boot-manual.sh root@192.168.1.1:/tmp/mf297d-ram/
ssh root@192.168.1.1 'sh /tmp/mf297d-ram/ram-boot-manual.sh'
```

SSH kesilir. Yaklaşık 90 saniye sonra:

```sh
ssh -o HostKeyAlias=mf297d-ram root@192.168.1.1
uname -r
nss-status -j
```

LuCI: `http://192.168.1.1`. İlk girişte root şifreni ve Wi-Fi ayarlarını yap.
RAM profilinde bütün fiziksel NAND bölümleri salt okunurdur. `reboot` mevcut
NAND sistemini açar; RAM'de yapılan ayarlar kalıcı değildir.

## 2. Mevcut proje NAND düzenine yükleme

**Deneysel, eşleşen düzenle sınırlı yöntem.** Temel yazma/geri okuma yolu
cihazda kullanıldı; genelleştirilmiş hazırlama betiğinin tamamı yeni bir
canlı flash ile tekrar denenmedi. Betik stok veya tanımadığı bölümleri kabul etmez.
Gereken düzen: UBI `1=wifi_fw`, `2=bt_fw`, `4=owrt_kernel`, `5=owrt_rootfs`,
`6=rootfs_data`, `7=owrt_recovery`; bu projenin CRC kontrollü açılış ortamı.

Ubuntu 24.04/Python 3.12 terminalinde araçlar:

```sh
sudo apt update
sudo apt install git gh python3 gcc-aarch64-linux-gnu libc6-dev-arm64-cross mtd-utils squashfs-tools
gh repo clone ozgunokan/ZTE-MF297D-OpenWRT ~/MF297D
cd ~/MF297D
```

Repo private ise önce kendi hesabınla `gh auth login` yap. Release'teki NAND
dosyasını ev klasörüne, araç ZIP'ini `~/mf297d-tools` içine aç.

Önce yedekle ve yalnız bu cihazın ENV'sine bağlı dosyaları hazırla:

```sh
python3 nss/tools/prepare-nand.py --router 192.168.1.1 --firmware ~/openwrt-mf297d-6.18.60-nss-nand.bin --kexec ~/mf297d-tools/kexec-aarch64 --out ~/MF297D-ready
```

Bu adım flash yazmaz; tutarlı overlay yedeği için kısa süre salt okunur
bağlama yapar. `~/MF297D-ready/backups` eski sistemi ve ayarları içerir;
bu klasörü ve üretilen `owner` dosyalarını paylaşma.

RAM bakım ortamına geç:

```sh
sh ~/MF297D-ready/boot-maintenance.sh
```

Yaklaşık 90 saniye sonra yeni RAM oturumuna bağlan, dosyaları **yeniden** gönder:

```sh
ssh -o HostKeyAlias=mf297d-maintenance root@192.168.1.1 'touch /tmp/mf297d-source-keep; mkdir -p /tmp/mf297d-install'
cd ~/MF297D-ready
scp -O -o HostKeyAlias=mf297d-maintenance Image maintenance.dtb bootargs.txt kernel.bin rootfs.bin overlay.ubifs env-helper kexec SHA256SUMS install-from-ram.sh prefix.before.sha256 root@192.168.1.1:/tmp/mf297d-install/
ssh -o HostKeyAlias=mf297d-maintenance root@192.168.1.1 'chmod 500 /tmp/mf297d-install/env-helper; sh /tmp/mf297d-install/install-from-ram.sh'
```

Son komut kurulumu yapar ve yeniden başlatır. Betik mevcut ENV/firmware
hashlerini kontrol eder, kurtarmayı korur, yeni rootfs/ayarları doğrular ve
kerneli en son yazar. İlk bağlantıdaki SSH anahtarını doğrula; RAM ve NAND
oturumlarının anahtarları farklı olabilir.

Yaklaşık 90 saniye sonra kontrol:

```sh
ssh root@192.168.1.1 'uname -r; nss-status -j; ifstatus lte; df -h /overlay'
```

## 3. Ubuntu'da paket ekleyip derleme

### Hazır bilgisayardaki alan

Mevcut çalışma alanı duruyor. Windows Terminal'den:

```powershell
wsl -d MF297D-Ubuntu -u build
```

Ubuntu içinde:

```sh
cd /home/build/openwrt-mf297d-nss-ipq50
cp .config .config.backup
make menuconfig
make defconfig
JOBS=8 sh ~/MF297D/nss/build.sh nand "$PWD"
```

`menuconfig` içinde istediğin paketleri seçip kaydet. Hata ayrıntısı için
`make -j1 V=s` kullan. Derleme tek başına cihaza yazmaz. Bu hazır alan
cihazına özel dosyalar içerebilir; paylaşılabilir imaj için temiz reçeteyi kullan.

### Başka bir Ubuntu'da temiz alan

Gerçek NSS tabanı `kuncy7/openwrt-nss-edma` ve sabit commit'tir. İlk istenen
`JuliusBairaktaris/openwrt-ppe-nss` ağacının IPQ5018/IPQ50xx desteği yeterli
olmadığı için çalışan entegrasyon bu uyumlu tabanda tutuluyor. Kaynak ve feed
sürümleri [nss/SOURCE.json](../nss/SOURCE.json) ve [feed kilidinde](../nss/feeds-lock.json).

```sh
sudo apt install build-essential clang flex bison g++ gawk gcc-multilib gettext git libncurses-dev libssl-dev libelf-dev python3 python3-setuptools rsync unzip zlib1g-dev file wget curl swig libpython3-dev device-tree-compiler squashfs-tools mtd-utils
cd ~/MF297D
sh nss/configure.sh nand ~/build-mf297d-nand
cd ~/build-mf297d-nand
make menuconfig
JOBS=8 sh ~/MF297D/nss/build.sh nand "$PWD"
```

Çıktılar `~/build-mf297d-nand/bin/mf297d/` içindedir. NAND paketleme aracı
rootfs'i otomatik olarak 4 KiB sınırına hizalar.

Initramfs için ayrı alan:

```sh
cd ~/MF297D
sh nss/configure.sh initramfs ~/build-mf297d-ram
cd ~/build-mf297d-ram
make menuconfig
JOBS=8 sh ~/MF297D/nss/build.sh initramfs "$PWD"
```

Çıktı `~/build-mf297d-ram/bin/mf297d/openwrt-mf297d-nss-initramfs.itb`.
Kendi dosyalarını `files/` altına ekleyebilirsin; örneğin `files/etc/config/`.
Yeniden derlediğin kernel ve modülleri aynı derlemeden kullan.

## Durum ve kaynaklar

- [NSS yayın/test kapsamı](NSS-RELEASE.md)
- [NAND kurtarma ve bölüm düzeni](RECOVERY.md)
- [Tarihsel ilk port](BUILD-LEGACY.md)
- [Lisans/kaynak notları](../NOTICE.md)

CPU1 düzeltmesi `mf297d-cpu` servisindedir: erken açılışta `maxcpus=1`
korunur, S18 aşamasında CPU1 açılır ve S19 NSS bundan sonra başlar.
Bootloader/ENV değiştirilmez. Çalışan cihazda otomatik yeniden açılış ve
iki çekirdeğe sabitlenen işler NSS/iki Wi-Fi radyosuyla birlikte doğrulandı.
Kontrol: `cat /sys/devices/system/cpu/online` çıktısı `0-1` olmalıdır.
Bu, erken SMP açılış sorununun çekirdek düzeyinde çözülmesi iddiası değildir;
çalışan iki çekirdek sağlayan başlangıç düzenidir.


## NAND build stops at profiles.json

If the build reports `JSON info file script could not find any JSON files for target`,
the custom NAND profile has no standard `IMAGES` entries to describe. Kernel and
rootfs may already have been generated; this error is the final overview metadata
step. Update the integration repository with `git -C ~/MF297D pull --ff-only`.
The current NAND build wrapper disables that overview target and then runs the
custom packaging step. Existing build trees can also be corrected explicitly:

```sh
cd ~/build-mf297d-nand
cp .config .config.before-json-fix
sed -i 's/^CONFIG_JSON_OVERVIEW_IMAGE_INFO=y$/# CONFIG_JSON_OVERVIEW_IMAGE_INFO is not set/' .config
make defconfig
JOBS=8 sh ~/MF297D/nss/build.sh nand "$PWD"
```

Completed custom outputs are under `bin/mf297d/`. This does not create a normal
factory/sysupgrade image; use the documented installation workflow.
