# Stok B18 → RAM → RESET kurtarma → tek OpenWrt NAND

Bu kit yalnız **MF297D / CR_TKCTURMF297DV1.0.0B18 / Linux 4.4.60** içindir.
Kernel ABI, iç fonksiyon adresleri ve bootloader hashleri eşleşmezse durur.
İlk aşama normal kexec değildir: ARM32 stok modülüyle ARM64 RAM çekirdeğine
geçilir. NAND hazırlama/bakım geçişlerinde bundan sonra gerçek AArch64 kexec kullanılır.

**Canlı doğrulama sınırı:** Yeni kitin ilk stok geçişi ve bütün NAND kurulumu
ikinci bir stok cihazda henüz denenmedi. Önceki yükleyici bu cihazda çalıştı;
yeni sürümün ARM kod emülasyonu ve yedekler üstündeki hazırlama testleri geçti.
Bu kit deneysel olarak dağıtılır. ENV tek kopyalıdır; yazılırken güç kesilmesi
Ethernet kurtarmasını da bozabilir. UART olmadan geri dönüş garanti değildir.

## Dosyalar ve terminal

Release'ten `MF297D-Stok-RAM.zip`, `mf297d-tools.zip`, yeni initramfs `.itb`,
NAND `.bin` ve `RAM-PROFILE.json` indir. Aynı Release'in dosyalarını birlikte kullan.
**PC Windows** komutlarını PowerShell'e; **PC Ubuntu** komutlarını bilgisayarın
Ubuntu/WSL terminaline yaz. `ssh ...` komutunu da PC terminalinde çalıştır.
Telnet'i ana README 1. bölümündeki araçla aç; root sUser parolanı bilmelisin.

## 1. PC Windows: LAN ve stok RAM

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

Normal PowerShell'de RAM'i aç:

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

## 2. PC Ubuntu: kendi yedeğini al, kurulum dosyalarını hazırla

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

## 3. PC Ubuntu: önce kurtarmayı kur — A aşaması

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
