# ZTE MF297D — adım adım OpenWrt kurulumu

Sıra: **1. Telnet aç → 2. kexec/yükleyici ekle → 3. RAM'de dene →
4. RESET kurtarmasını doğrula → 5. NAND'a yaz.**

**Şu anki eksik:** Release, stok Turkcell yazılımından sonuna kadar çalışan
bir ilk kurulum paketi değildir. Telnet aracı var. OpenWrt kurulu cihazın RAM
denemesi ve eşleşen NAND düzenini güncelleme araçları var. **Stoktan ilk RAM
geçişinin dağıtıma hazır yükleyicisi ve ilk NAND/kurtarma kurucusu henüz yok.**
Stok cihazla başlayan kişi **2A'da durmalıdır**. Önceki README bu başlangıcı
atlayıp zaten OpenWrt kurulu cihazdan devam ediyordu.

Test cihazında Linux 6.18.60, iki CPU, NSS ve iki Wi-Fi radyosu çalışıyor.
Bu, genel ilk kurulum paketinin tamamlandığı anlamına gelmez.

## Ön hazırlık: komutları nereye yazacaksın?

| Etiket | Neresi? |
| --- | --- |
| **PC / Windows** | Bilgisayardaki tarayıcı, EXE veya PowerShell. |
| **PC / Ubuntu** | Bilgisayardaki Ubuntu/WSL terminali. Modemin terminali değil. |
| **MODEM / Telnet** | PuTTY ile modeme Telnet bağlandıktan sonraki ekran. |
| **MODEM / SSH** | SSH ile OpenWrt'ye bağlandıktan sonraki ekran. |

Kurulum/SSH için Ethernet kablosu **PC ↔ modem LAN1/LAN2/LAN3** arasında olur.
**WAN** soketi yalnız 1B'deki ACS işlemi sırasında kullanılacak.

**PC / Windows:** Ayarlar → Ağ ve İnternet → Ethernet → IP ataması → Düzenle
→ El ile → IPv4. Adres **192.168.1.2**, maske **255.255.255.0** gir.
Ethernet ağ geçidi/DNS alanını boş bırak. Modemin LAN adresi **192.168.1.1**.
PC'nin internet için kullandığı Wi-Fi ayarını değiştirme.

## Dosyalar

[Release sayfasından indir](https://github.com/ozgunokan/ZTE-MF297D-OpenWRT/releases/tag/mf297d-2026.11.20-nss.2):

| Dosya | Kullanımı |
| --- | --- |
| `MF297D-Telnet-CFG.exe` | Kendi CFG yedeğinden Telnet açık dosya üretir; Python gerekmez. |
| `MF297D-Yerel-Yonetici.exe` | ACS üzerinden sUser/LAN Telnet yardımcısı; Npcap gerekir. |
| `mf297d-telnet-source.zip` | CFG aracının kaynağı, test ve lisans notları. |
| `mf297d-tools.zip` | OpenWrt için kexec ve RAM/NAND yardımcıları. |
| `openwrt-mf297d-6.18.60-nss-initramfs.itb` | RAM'de çalışan geçici sistem. |
| `openwrt-mf297d-6.18.60-nss-nand.bin` | Mevcut proje NAND düzenine özel bileşen paketi. |

**NAND `.bin` dosyasını stok panelinin firmware güncelleme ekranına verme.
Standart `sysupgrade` imajı da değildir.**

## 1. İlk iş: LAN Telnet aç

Doğrulanan stok sürüm **CR_TKCTURMF297DV1.0.0B18**. Modem zaten OpenWrt
çalıştırıyorsa bu adımı atla; stok CFG'yi OpenWrt'ye yükleme.

### 1A. CFG dosyasıyla

**PC / Windows:**

1. Kendi modeminin **yapılandırma yedeğini (`.CFG`)** al. Firmware `.bin` veya
   ham flash yedeği değil. Panelde yedekleme yoksa 1B'deki uygulamanın
   **Yedekler → Config** işlemiyle alınabilir.
2. Orijinal CFG'yi sakla. `MF297D-Telnet-CFG.exe` dosyasına çift tıkla.
3. İlk pencerede kendi orijinal CFG dosyanı seç.
4. İkinci pencerede yeni dosyayı **MF297D-LAN-Telnet.CFG** adıyla kaydet.
5. Araç yalnız `telnet_lan_enable=0` değerini `1` yapar. Şifreleri değiştirmez;
   modeme kendisi dosya göndermez.
6. Stok panelinde **ayar/config geri yükleme** seçeneği varsa yeni CFG'yi
   oradan yükle. Bu, firmware güncelleme ekranı değildir. Modemin yeniden
   açılmasını bekle. **Config içe aktarma menüsü yoksa 1B yöntemini kullan.**

Bizim testte kullanılan eski CFG, test cihazının şifrelerini ve kimlik
bilgilerini içeriyor. Herkese o dosyayı vermek yerine bu araç herkesin kendi
yedeğinden aynı Telnet değişikliğini üretir. Çıktı dosyasını GitHub'a yükleme.

Python ile alternatif, **PC terminalinde**:

```sh
python tools/telnet_cfg.py kendi-yedegim.CFG --out MF297D-LAN-Telnet.CFG
```

### 1B. sUser şifresini bilmiyorsan veya CFG geri yükleme menün yoksa

**PC / Windows ve stok modem paneli:**

1. [Npcap](https://npcap.com/#download) kur. Diğer TR069ACS uygulamalarını kapat.
2. `MF297D-Yerel-Yonetici.exe` aç. **Yönetici olarak yeniden aç** düğmesine
   basıp Windows onayını ver.
3. Modemin panelinde çalışma modunu **Kablolu genişbant**, WAN bağlantı türünü
   **Dinamik IP / DHCP** yap.
4. Ethernet kablosunu **PC ↔ modem WAN** olarak bağla.
5. Uygulamada doğru fiziksel **Ethernet** adaptörünü seç. **WAN servislerini
   başlat** düğmesine bas. Bu aşamada PC Ethernet'i `192.168.50.1/24` yapılır.
6. Modemi normal yeniden başlat. Uygulamada cihazın ve **sUser** hesabının
   görülmesini bekle.
7. Kullanacağın sUser parolasını gir. Mevcut parolayı bilmiyorsan **sUser
   parolasını değiştir** kutusunu seç. **sUser + LAN Telnet uygula** düğmesine bas.
8. Başarı ve geçici WAN Telnet'in kapatıldığı sonucu gelince, kablo hâlâ
   WAN'dayken **WAN servislerini durdur** düğmesine bas.
9. Kabloyu **WAN'dan çıkarıp LAN1/LAN2/LAN3'e** tak.
10. **LAN root bağlantısını doğrula** düğmesine bas. PC `192.168.1.2/24` olur;
    modem `192.168.1.1:2323` üzerinden kontrol edilir.

ACS EXE'sinin bütün akışı fabrika ayarlı ikinci cihazda uçtan uca denenmedi;
aynı modem üzerindeki erişim adımları ayrı komutlarla doğrulandı.
[Uygulama ayrıntıları](tools/windows-manager/README.md).

### 1C. Açıldığını kontrol et

**PC / Windows:** PuTTY'de tür **Telnet**, adres **192.168.1.1**, port **2323**.
Kullanıcı **sUser**, parola yukarıda belirlediğin sUser parolası. Paneldeki
`admin` parolasıyla aynı olmak zorunda değil. Windows Telnet istemcin kuruluysa:

```text
telnet 192.168.1.1 2323
```

**MODEM / Telnet — giriş yaptıktan sonra:**

```sh
id
uname -m
uname -r
nv get telnet_lan_enable
```

`id` içinde **uid=0**, son komutta **1** görmelisin.

## 2. Kexec/yükleyici ekle

### 2A. Cihaz hâlâ stok Turkcell yazılımındaysa: burada eksik var

**MODEM / Telnet — yalnız kontrol:**

```sh
command -v kexec
zcat /proc/config.gz | grep KEXEC
```

Stok B18'de normal kexec desteği yoktu. Stok sistem 32 bit ARM; Release'teki
`kexec-aarch64` ise 64 bit OpenWrt içindir. **Bu dosyayı TFTP ile stok modeme
göndermek ilk geçişi sağlamaz.**

İlk RAM açılışını stok sürüme ve imaja özel kernel modülü/trampoline ile
yaptık. [Araştırma kaynakları](reference/stock-ramboot/README.md) var; fakat
sürüm kontrolü, eşleşen dosyalar ve başlatma aracı bir arada olan genel paket
Release'te yok. **Stok cihaz için burada dur.** Eski modülü rastgele `insmod`
ile yüklemek bu rehberin bir kurulum adımı değildir.

### 2B. Bu projenin OpenWrt'si zaten kuruluysa

**PC / Windows — Ubuntu terminaline gir:**

```powershell
wsl -d MF297D-Ubuntu -u build
```

**PC / Ubuntu — araçları ve dosyaları indir:**

```sh
sudo apt update
sudo apt install gh unzip python3 openssh-client
gh auth login
mkdir -p ~/MF297D-kurulum
cd ~/MF297D-kurulum
gh release download mf297d-2026.11.20-nss.2 --repo ozgunokan/ZTE-MF297D-OpenWRT -p mf297d-tools.zip -p openwrt-mf297d-6.18.60-nss-initramfs.itb -p openwrt-mf297d-6.18.60-nss-nand.bin
unzip mf297d-tools.zip
cd mf297d-tools
```

Depo private ise `gh auth login` sırasında erişimi olan kendi GitHub hesabını
kullan. Bu indirme komutları modeme yazmaz.

**PC / Ubuntu — kexec'i modemin geçici belleğine gönder:**

```sh
ssh root@192.168.1.1 'mkdir -p /tmp/mf297d-ram'
scp -O kexec-aarch64 root@192.168.1.1:/tmp/mf297d-ram/
ssh root@192.168.1.1 'chmod 500 /tmp/mf297d-ram/kexec-aarch64; /tmp/mf297d-ram/kexec-aarch64 --help'
```

Yardım yazısı gelirse dosya çalışıyor. Henüz RAM sistemi başlatılmadı.
Aktarım **SCP** ile yapıldı; TFTP sunucusu gerekmiyor. `/tmp`, modemin RAM'idir;
modem yeniden başlayınca içindeki dosyalar silinir.

## 3. Önce RAM'den başlat

Bu bölüm **2B'deki mevcut OpenWrt** için geçerli; 2A'da duran stok cihaz için değil.

**PC / Ubuntu — kendi cihazının iki MAC adresini oku:**

```sh
cd ~/MF297D-kurulum/mf297d-tools
ssh root@192.168.1.1 'cat /sys/class/net/eth0/address; cat /sys/class/net/wan/address'
```

İlk adresi aşağıdaki `LAN_MAC`, ikinciyi `WAN_MAC` yerine yaz:

```sh
python3 tools/personalise_release.py ../openwrt-mf297d-6.18.60-nss-initramfs.itb --lan-mac LAN_MAC --wan-mac WAN_MAC
```

PC'de `ready` klasörü oluşur. Bu klasör zaten varsa önceki denemeyle
karıştırma; yeni bir çalışma klasörü kullan.

**PC / Ubuntu — NSS'yi bir açılış için kapatıp yeniden başlat:**

```sh
ssh root@192.168.1.1 'uci set nss.general.enabled=0; uci set nss.general.wifi_offload=0; uci commit nss; reboot'
```

**90 saniye bekle.** Yeniden başlatma önceki geçici dosyaları sildiği için
kexec dahil **hepsini yeniden gönderiyoruz**:

```sh
ssh root@192.168.1.1 'mkdir -p /tmp/mf297d-ram'
scp -O ready/* kexec-aarch64 tools/ram-boot-manual.sh root@192.168.1.1:/tmp/mf297d-ram/
ssh root@192.168.1.1 'sh /tmp/mf297d-ram/ram-boot-manual.sh'
```

SSH kesilir. **90 saniye bekle**, sonra **PC / Ubuntu**:

```sh
ssh -o HostKeyAlias=mf297d-ram root@192.168.1.1
```

**MODEM / SSH — yeni RAM sisteminde kontrol:**

```sh
uname -r
cat /proc/cmdline
cat /proc/mounts
cat /sys/devices/system/cpu/online
nss-status -j
```

Kernel `6.18.60`, komut satırında `root=/dev/ram0`, CPU listesi `0-1` olmalı.
Tarayıcıdan `http://192.168.1.1` açılabilir. Genel RAM profilinde Wi-Fi başlangıçta
kapalıdır; Ethernet'i kullan. RAM'deki ayarlar kalıcı değildir.
NAND'daki önceki sisteme dönmek için **MODEM / SSH**: `reboot`.

## 4. RESET tuşu ile kurtarma

**Yalnız projenin kurtarma bölümü ve açılış seçicisi önceden kurulmuşsa geçerli.**
Stok modemde RESET'e basmak bu kurtarmayı kurmaz; fabrika ayarına döndürebilir.
Stoktan ilk kurtarma kurucusu henüz dağıtılan pakette yok.

Kurtarması kurulu düzende:

1. Ethernet **LAN1/LAN2/LAN3'te**, PC `192.168.1.2/24` olsun.
2. Modemin güç fişini çıkar.
3. **RESET'e basılı tutarken** güç fişini tak.
4. Gücü taktıktan yaklaşık **7 saniye sonra RESET'i bırak**.
5. **90 saniye bekle.** RESET'e yeniden uzun basma.
6. **PC / Ubuntu** terminalinden bağlan:

```sh
ssh -o HostKeyAlias=mf297d-recovery root@192.168.1.1
```

**MODEM / SSH:** `cat /proc/cmdline` ve `cat /proc/mounts` çalıştır.
Kök RAM'de olmalı (`root=/dev/ram0`). Normal kurtarma NAND'ı salt okunur açar.
**PC'den TFTP dosyası beklemez; modemde kayıtlı kurtarma imajını açar.**
Normal sisteme dönmek için `reboot` yaz; bu sefer RESET'e basma.
Kurtarmayı gerçekten açıp doğrulamadan NAND'a yazma aşamasına geçme.

## 5. En son NAND'a yaz

### Stoktan ilk kurulum

Kendi yedeğini alan, uygun bölümleri hazırlayan, kurtarmayı önce kurup
doğrulayan ve cihazın açılış ayarını üreten **ilk kurulum aracı eksik**.
Bu nedenle burada stoktan doğrudan çalıştırılacak silme/yazma komutu yok.
Mevcut `nand.bin` bu eksik aracı içermiyor.

### Mevcut proje NAND düzenini güncelleme

Yalnız şu birimler zaten varsa: `wifi_fw`, `bt_fw`, `owrt_kernel`,
`owrt_rootfs`, `rootfs_data`, `owrt_recovery`. Betik stok cihazı kabul etmez.
Genelleştirilmiş kurucu bütünüyle canlı flash testinden geçmedi: **deneysel**.

RAM/kurtarma oturumundaysan önce `reboot` ile **normal NAND OpenWrt'ye dön**;
90 saniye bekle. Hazırlama işlemi normal sistemden yedek alır, sonra ayrı RAM
bakım sistemine geçer. Bilgisayardaki dosyaları bu geçişte kaybetmezsin.

**PC / Ubuntu — hazırlama araçlarını al:**

```sh
sudo apt install git gcc-aarch64-linux-gnu libc6-dev-arm64-cross mtd-utils squashfs-tools
gh repo clone ozgunokan/ZTE-MF297D-OpenWRT ~/MF297D
cd ~/MF297D
python3 nss/tools/prepare-nand.py --router 192.168.1.1 --firmware ~/MF297D-kurulum/openwrt-mf297d-6.18.60-nss-nand.bin --kexec ~/MF297D-kurulum/mf297d-tools/kexec-aarch64 --out ~/MF297D-ready
```

Bu komut henüz flash yazmaz. `~/MF297D-ready/backups` eski sistemi ve özel
ayarlarını içerir. Klasörü başka yere kopyalayıp sakla; GitHub'a yükleme.
Kontrol hata verirse sonraki komuta geçme.

**PC / Ubuntu — RAM bakım sistemini başlat:**

```sh
sh ~/MF297D-ready/boot-maintenance.sh
```

**90 saniye bekle.** RAM değiştiği için dosyaları **yeniden SCP ile** gönder:

```sh
ssh -o HostKeyAlias=mf297d-maintenance root@192.168.1.1 'touch /tmp/mf297d-source-keep; mkdir -p /tmp/mf297d-install'
cd ~/MF297D-ready
scp -O -o HostKeyAlias=mf297d-maintenance Image maintenance.dtb bootargs.txt kernel.bin rootfs.bin overlay.ubifs env-helper kexec SHA256SUMS install-from-ram.sh prefix.before.sha256 root@192.168.1.1:/tmp/mf297d-install/
```

**Sıradaki komut NAND'a gerçekten yazar.** Betik hashleri/mevcut düzeni kontrol
eder; kurtarma ve radyo birimlerini korur, kerneli en son yazar.

**PC / Ubuntu:**

```sh
ssh -o HostKeyAlias=mf297d-maintenance root@192.168.1.1 'chmod 500 /tmp/mf297d-install/env-helper; sh /tmp/mf297d-install/install-from-ram.sh'
```

Bitince modem yeniden başlar. **90 saniye bekle**, sonra **PC / Ubuntu**:

```sh
ssh root@192.168.1.1 'uname -r; cat /sys/devices/system/cpu/online; nss-status -j; df -h /overlay'
```

Kernel `6.18.60`, CPU `0-1`, NSS `active` olmalı. Tarayıcıdan
`http://192.168.1.1` aç; kendi root şifreni, Wi-Fi ve SIM/APN ayarlarını yap.
Genel profilde Wi-Fi/LTE kullanıcı tarafından yapılandırılır.

## TFTP mi, SCP mi, RESET mi?

| İş | Nasıl? |
| --- | --- |
| Telnet CFG hazırlamak | PC'deki EXE; yalnız yerel dosya değişir. |
| CFG geri yüklemek | Stok config içe aktarma yolu varsa o yol; firmware ekranı değil. |
| ACS ile Telnet açmak | PC ↔ modem **WAN**; sonra kablo LAN'a alınır. |
| OpenWrt'ye kexec/RAM dosyası göndermek | PC Ubuntu'dan **SCP**, modem `/tmp` klasörüne. |
| RAM sistemi başlatmak | Modemde **kexec**; dosya aktarımı değil. |
| RESET kurtarma | Modemde kayıtlı kurtarma açılır; TFTP gerekmez. |
| Stoktan ilk RAM/NAND geçişi | Tam dağıtım yolu henüz eksik; SCP komutları bunun yerine geçmez. |

## Ubuntu'da paket ekleyip derlemek

Mevcut bilgisayardaki alan duruyor. **PC / Windows**:

```powershell
wsl -d MF297D-Ubuntu -u build
```

**PC / Ubuntu**:

```sh
cd /home/build/openwrt-mf297d-nss-ipq50
cp .config .config.backup
make menuconfig
make defconfig
make -j8
```

Paketlerini `menuconfig` ekranında seçip kaydet. Derlemek kendiliğinden
modeme yazmaz. [Başka Ubuntu'da temiz derleme](docs/NSS-GUNCELLEME.md#başka-bir-ubuntuda-temiz-alan).

[NSS/CPU test kapsamı](docs/NSS-RELEASE.md) · [Kurtarma](docs/RECOVERY.md) ·
[İlk cihazdaki tarihsel geçiş](docs/INSTALL.md) · [Lisanslar](NOTICE.md).

Genel yayın profili ve genelleştirilmiş NAND kurucu bütünüyle canlı flash
testinden geçmedi. Çalışan test cihazı ile temiz genel profilin kapsamları
NSS test belgesinde ayrı açıklanır.
