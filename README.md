# ZTE MF297D — Telnet'ten OpenWrt NAND'a kurulum

Sıra: **1. Telnet → 2. yükleyiciyi aktar/hazırla → 3. RAM'de aç ve yedekle →
4. RESET kurtarmasını doğrula → 5. en son NAND'a kur.**

Bu sürümde stok RAM yükleyicisi, iki aşamalı ilk NAND/kurtarma kurucusu ve
CPU/Wi-Fi LED düzeltmeli imajlar birlikte veriliyor. **Yeni stoktan ilk kurulum
kiti canlı bir stok cihazda henüz baştan sona denenmedi; deneysel ön sürümdür.**
Emülasyon, stok yedekleriyle hazırlama ve mevcut çekirdekte rootfs testleri geçti.
Genel RAM imajı ayrıca mevcut OpenWrt üzerinden canlı açıldı: iki CPU, NSS,
iki Wi-Fi radyosu ve IPv4/IPv6 iletimi geçti. Bu, stoktan ilk NAND kurulumunun
canlı testi değildir.
Çalışan cihazı stok yazılıma döndürerek test edilmedi.

Doğrulanan donanım/firmware: **ZTE MF297D, Turkcell B18**. Başka model/sürüm
desteklenmez. Stok sistem 32 bit ARM'dır; `kexec-aarch64` dosyasını tek başına
stokta çalıştıramazsın. İlk RAM geçişini aşağıdaki **Stok RAM** aracı yapar;
sonraki bakım geçişlerinde gerçek AArch64 kexec kullanılır.

## Komutları nerede çalıştıracağım?

| Etiket | Neresi? |
| --- | --- |
| PC Windows | Bilgisayardaki PowerShell, tarayıcı veya EXE. |
| PC Ubuntu | Bilgisayardaki Ubuntu/WSL terminali; modem terminali değil. |
| Modem Telnet/SSH | Modeme bağlandıktan sonraki komut ekranı. |

Kurulumda kablo **PC ↔ modem LAN1/LAN2/LAN3** arasında kalır. Yalnız 1B'deki ACS
Telnet açma işlemi için WAN kullanılır; ne zaman LAN'a dönüleceği orada yazıyor.
PC Ethernet **192.168.1.2/24**, modem **192.168.1.1**. Ethernet ağ geçidi/DNS
boş; PC'nin internet için kullandığı Wi-Fi değişmeyecek.

## İndir

[Bütün dosyalar — Release](https://github.com/ozgunokan/ZTE-MF297D-OpenWRT/releases/tag/mf297d-2026.11.20-install-kit.3)

| Dosya | Ne işe yarıyor? |
| --- | --- |
| MF297D-Telnet-CFG.exe | Kendi CFG yedeğinden LAN Telnet açık CFG üretir. |
| MF297D-Yerel-Yonetici.exe | ACS üzerinden sUser/LAN Telnet yardımcısı. |
| MF297D-Stok-RAM.zip | Stok B18 için EXE, ARM32 modüller, kernel ve RAM dosya sistemi. |
| mf297d-tools.zip | AArch64 kexec, kişiselleştirme ve ilk/güncelleme kurulum araçları. |
| openwrt-mf297d-6.18.60-nss-initramfs.itb | Genel RAM imajı ve kurucunun RAM şablonu. |
| RAM-PROFILE.json | Yukarıdaki RAM imajına ait hash ve yerleşim bilgisi; aynı sürümden indir. |
| openwrt-mf297d-6.18.60-nss-nand.bin | Kernel + hizalı rootfs paketi; kurucu kullanır. |
| mf297d-nss-source.zip | DTS, yamalar, profiller, stok yükleyici/kurucu kaynakları. |
| VALIDATION.json / SHA256SUMS | Test kapsamı ve bütün dosyaların SHA256 değerleri. |

**NAND `.bin` dosyası factory veya sysupgrade imajı değildir. Stok firmware
güncelleme ekranına yükleme.** Stok işletim sistemi ancak son B aşamasında
kaldırılır. Korunan stok yedekleri ve radyo verileri her cihazın kendisine aittir.

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

## 2. Stok RAM yükleyicisini hazırla ve kontrol et


PC Ethernet `192.168.1.2`, maske `255.255.255.0`, ağ geçidi/DNS boş.
Kablo **PC ↔ modem LAN1/LAN2/LAN3** arasında. Modem `192.168.1.1:2323` Telnet.

ZIP'i örneğin `C:\MF297D\MF297D-Stok-RAM` içine çıkar. PowerShell:

```powershell
cd C:\MF297D\MF297D-Stok-RAM
.\MF297D-Stok-RAM.exe --check
```

Sorunca **sUser parolasını** gir. Parola komuta yazılmaz, kaydedilmez.
Sürüm/ABI kontrolü hata verirse devam etme.

Dosyaları modem PC'den yerel TCP18869 üzerinden alır; **TFTP kullanılmaz**.
Windows engellerse **Yönetici PowerShell** ile yalnız bu bağlantıya izin ver:

```powershell
New-NetFirewallRule -DisplayName MF297D-RAM-Aktarim -Direction Inbound -Protocol TCP -LocalPort 18869 -LocalAddress 192.168.1.2 -RemoteAddress 192.168.1.1 -Action Allow
```

## 3. OpenWrt'yi önce RAM'de aç

Normal **PC Windows / PowerShell** terminalinde:

```powershell
.\MF297D-Stok-RAM.exe --boot
```

Araç dosyaları aktarır, SHA256/CRC ve hazırlık modülünü kontrol eder, Wi-Fi/USB
yardımcılarını durdurur ve RAM geçişini gönderir. **NAND/ENV yazmaz.** Yaklaşık
90 saniye sonra SSH22 açılmasını ve bütün 25 NAND bölümünün salt okunur olmasını
kontrol eder. Doğrulama başarısızsa otomatik tekrar yapmaz.

Bu ilk RAM ortamı kurulum içindir; NSS ve Wi-Fi başlangıçta kapalıdır, Ethernet
ve LuCI kullanılır. `reboot` stok sisteme döner; henüz kalıcı OpenWrt kurulmadı.
İş bitince eklenen Windows kuralını **Yönetici PowerShell** ile kaldır:

```powershell
Remove-NetFirewallRule -DisplayName MF297D-RAM-Aktarim
```

Python alternatifi: `python boot.py --bundle . --boot`; gözlem için Paramiko gerekir.

### 3A. PC Ubuntu: kendi yedeğini al, kurulum dosyalarını hazırla

Ubuntu 24.04/Python3.12 kullan. İndirilen `.itb`, `.bin`, `RAM-PROFILE.json`
dosyalarını `~/MF297D-kurulum` klasörüne koy; `mf297d-tools.zip` dosyasını da
bu klasöre aç. Kexec dosyası `~/MF297D-kurulum/mf297d-tools/kexec-aarch64` olacak.

```sh
sudo apt update
sudo apt install gh git python3 python3-paramiko gcc-aarch64-linux-gnu libc6-dev-arm64-cross mtd-utils squashfs-tools unzip
gh auth login
gh repo clone ozgunokan/ZTE-MF297D-OpenWRT ~/MF297D
cd ~/MF297D
python3 stock/prepare_install.py --nand ~/MF297D-kurulum/openwrt-mf297d-6.18.60-nss-nand.bin --ram ~/MF297D-kurulum/openwrt-mf297d-6.18.60-nss-initramfs.itb --profile ~/MF297D-kurulum/RAM-PROFILE.json --kexec ~/MF297D-kurulum/mf297d-tools/kexec-aarch64 --out ~/MF297D-ilk-kurulum
```

Bu komut **henüz flash yazmaz**. Bütün 25 fiziksel MTD veri alanını ve stok
UBI dosyalarını indirip boyut/SHA256 ile kontrol eder. `.CFG`, tam flash yedeğinin
yerine geçmez. Bu yedek data-only/ECC düzeltilmiştir; OOB'lu programlayıcı imajı değildir.
`~/MF297D-ilk-kurulum/backups` klasörünü ikinci bir yere kopyala.
Bu klasörü ve `owner` dosyalarını GitHub'a yükleme; sana özeldir.

Hazırlama sırasında kernel/model, tüm MTD'lerin salt okunur olması, stok hacim
düzeni, bootloader ve kendi MAC verin kontrol edilir. Hata varsa aşama A'ya geçilmez.

### 3B. Önce kurtarmayı kur — A aşaması

**Bu komut recovery hacmini ve bootloader ENV'sini yazar.** Stok işletim sistemi
hacimlerini henüz silmez. Güç kesilmemeli; hata sonrası otomatik tekrar yapılmaz.

```sh
cd ~/MF297D
python3 stock/install.py --ready ~/MF297D-ilk-kurulum --phase-a
```

Araç kexec/dosyaları **SCP yerine kendi SSH aktarımıyla** `/tmp` içine gönderir;
RAM bakım ortamını açar, dosyaları yeni RAM'e yeniden aktarır. Kurtarma imajını
yazıp geri okur; yalnız bu cihaza bağlı ENV yardımcı programını çalıştırır.
Stok kernel/rootfs hacimleri ve radyo firmware korunur. Sonunda yeniden başlar.

## 4. Fiziksel RESET kurtarmasını gerçekten dene

1. Ethernet LAN'da, PC `192.168.1.2/24` kalsın.
2. Modemin fişini çıkar.
3. **RESET'e basılı tutarken** fişi tak.
4. Fişi taktıktan **7 saniye sonra RESET'i bırak**.
5. Yaklaşık **90 saniye** bekle.

**PC Ubuntu:**

```sh
cd ~/MF297D
python3 stock/install.py --ready ~/MF297D-ilk-kurulum --verify-reset
```

Sadece paneli açılmış görmek yetmez: araç owner kimliğini, U-Boot'tan
**fiziksel RESET seçimiyle** açıldığını, RAM kökü, salt okunur NAND'ı ve korunan
bölüm hashlerini doğrular. Başarılıysa yerel RESET kanıtı kaydeder.
Bu kanıt olmadan B aşaması başlamaz. RESET kurtarma **TFTP beklemez**;
modemde kayıtlı kurtarma imajını açar.

## 5. PC Ubuntu: en son stok OS'yi kaldır ve NAND'a kur — B aşaması

**Bu komut stok işletim sistemi hacimlerini kaldırır.** Doğrulanmış kurtarma,
bootloader/ART/MAC ve radyo firmware korunur. Sonuç tek OpenWrt'dir.

```sh
cd ~/MF297D
python3 stock/install.py --ready ~/MF297D-ilk-kurulum --phase-b
```

Araç doğrulanan kurtarma oturumundan ayrı RAM bakımına geçer. Yedeklenmiş üst
NAND alanını hazırlar; eski UBI'nin alt 58MiB'inin ve korunan bölümlerin
değişmediğini kontrol eder. Rootfs ve boş overlay yazılıp doğrulanır; kernel
**en son** yazılır. İşlem sonunda normal yeniden başlar. Hata varsa logu ve
yedekleri sakla; komutu körlemesine tekrar çalıştırma. Otomatik yarım-kurulum
devam ettirme/rollback uygulaması bu kitte yoktur.

Yaklaşık 90 saniye sonra **PC Ubuntu**:

```sh
ssh root@192.168.1.1 'uname -r; cat /sys/devices/system/cpu/online; nss-status -j; df -h /overlay'
```

Kernel `6.18.60`, CPU `0-1`, NSS `active` beklenir. Tarayıcıda
`http://192.168.1.1` aç. Root parolasını belirle; Wi-Fi'ye şifre koyup etkinleştir;
SIM/APN'yi ayarla. Genel imaj kişisel Wi-Fi şifresi taşımaz ve radyolar başlangıçta kapalıdır.
İlk kurulumun başarılı sayılması için normal açılış ve RESET kurtarma geri dönüşü
cihaz üzerinde ayrıca doğrulanmalıdır. Kitin yeni sürümünde bu canlı uçtan uca
test henüz yapılmadı; çevrimdışı testler bunun yerine geçmez.

## Kaynak ve test

`loader/` ARM32 modül, ARM64 shim ve aktarım yardımcılarının kaynaklarını içerir.
Sabit paketi Zig ile yeniden derlemek: `python stock/build.py --bundle PAKET --zig ZIG_YOLU`.
Kernel/rootfs kaynak reçetesi `nss/` altındadır. `tests/test_handoff.py` gerçek
derlenmiş geçiş kodunu Unicorn ile çalıştırır; Capstone/Unicorn gerekir.
Yeni image/DTB ile eski sabit modül karıştırılmaz; CRC ve bellek tablosu birlikte üretilmelidir.

## Zaten bu projenin OpenWrt'si kuruluysa

Stok kurucusunu yeniden çalıştırma. [Mevcut NAND sistemini güncelleme ve temiz derleme](docs/NSS-GUNCELLEME.md)
anlatımını kullan. Kullanımdaki cihazda CPU ve LED düzeltmeleri ayrıca kalıcı kurulmuştur.

## Bu bilgisayardaki Ubuntu derleme alanı

PC Windows: `wsl -d MF297D-Ubuntu -u build`.
Ardından **PC Ubuntu**:

```sh
cd /home/build/openwrt-mf297d-nss-ipq50
cp .config .config.backup
make menuconfig
make defconfig
make -j8
```

Derlemek modeme kendiliğinden yazmaz. Kaynak reçetesi [nss/](nss/SOURCE.json),
test ayrıntıları [NSS-RELEASE](docs/NSS-RELEASE.md), lisanslar [NOTICE](NOTICE.md).
