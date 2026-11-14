# Kurulum — yapılan geçişin ayrıntılı sırası

Bu belge test cihazında tamamlanan geçişi açıklar. Yeni bir stok cihaz için
çalıştır-ve-bitir kurucu değildir. Kaynaklardan tam rootfs yeniden üretimi ve
standart factory/sysupgrade henüz tamamlanmadığı için bu depodaki dosyaları
stok arayüzün firmware yükleme alanına vermeyin. Mevcut çalışan cihazda tekrar
kurulum gerekmiyor. Aşağıdaki NAND/ENV evreleri burada yeniden çalıştırılmadı.

## 1. Stok erişimi

Doğrulanan stok arayüz sürümü CR_TKCTURMF297DV1.0.0B18; başka sürümlerde önce
read-only envanter alın. İlk LAN yönetim adresi 192.168.1.1 idi.
Stok CWMP ACS URL'si `https://acs.superonline.net/cwmpWeb/CPEmgt` idi.
TR-069 bağlantısını başlatan modemdir; bilgisayardan web adresini açmak bir
Inform oturumu oluşturmaz. Gizli menüde `#tr069` bulunması backend'in bunu
açacağı anlamına gelmez. `setNV` ile LAN Telnet yazımı failure dönebilir.

[Windows yönetici uygulaması](../tools/windows-manager/README.md) kendi ACS,
DHCP ve sınırlı DNS servisini barındırır. Fiziksel Ethernet'i açıkça seçin;
diğer ACS uygulamalarını kapatın. Stok modemde kablolu genişbant ve Dinamik IP
seçilip modem WAN portu PC'ye bağlanır. Uygulama PC Ethernet'ini 192.168.50.1/24
yapar; modem DHCP ile veya 192.168.50.2 statik adresle ulaşır.

CWMP `InternetGatewayDevice.User.1.Username` gerçekten `sUser` olarak okunmadan
`User.1.Password` değiştirilmez. `TelnetSwitch.WAN_Enable` geçici kullanılır;
Telnet 2323 üzerinden `id` çıktısında uid=0 doğrulanır. Ardından
`nv set telnet_lan_enable=1` / `nv save` ile LAN erişimi kalıcı yapılır.
WAN Telnet kapatılıp doğrulanır; PC ağ ayarı geri alınır; kablo LAN'a taşınır.
App README prototipin sentetik test ile gerçek cihaz testinin farkını açıklar.

## 2. Her cihazın kendi yedeği

Önce `/proc/mtd`, kernel/board sürümü, MTD offset/size/erase/page/OOB ve badblock
haritasını kaydedin. UBI mantıksal MTD'lerini fiziksel bölümlerden ayırın.
Bootloader, ENV, ART, MAC, modem/NV ve tüm fiziksel NAND için ayrı manifest,
tam uzunluk ve SHA256 doğrulaması alın. Yedekleri en az iki yerde saklayın.
Özel config yedeği tek başına bootloader/ART/ham NAND yedeği yerine geçmez.

Windows uygulamasının flash yedeği **data-only** `/dev/mtdNro` okumadır; OOB
içermez. OOB için MTD ioctl destekli okuyucu ve cihazın ECC/raw modunun
doğrulanması gerekir (`reference/stock-ramboot/nand_readonly.c`, `oob_probe.c`).
ECC düzeltilmiş veri, raw page+OOB ve badblock işaretleri farklıdır; programlayıcı
imajı oldukları varsayılmaz. Canlı yazılabilir dosya sistemi atomik snapshot
değildir. Testte sonraki RAM bakım evresinde tam NAND/OOB yedekleri de alındı.

## 3. İlk RAM sistemi

Kullanılan ilk initramfs arkadaş tarafından sağlanmış IPQ50xx MF297D FIT idi.
Bunun tüm userspace kaynakları/üretim manifesti depoda yoktur; aynı isimli
internet dosyasının eşdeğer olduğu varsayılmaz. Önce FIT hash, mimari, load/entry,
DT bellek aralıkları ve firmware sürümü kontrol edildi. Stok çekirdekte hazır
kexec yoktu; özel kernel modülü/trampoline geliştirildi. Tarihsel kaynaklar
çalıştırılabilir genel paket değildir; eski sabit adreslerle yeniden yüklemeyin.

İlk RAM testi tüm NAND'ı read-only yapar. LAN yönetimi, kökün RAM'de olması,
bellek rezervleri, watchdog, doğru SPI NAND/Foresee ID ve Ethernet doğrulanır.
PC LAN'da ve aynı alt ağda kalır. Panel görünmesi tek başına RAM boot kanıtı
sayılmaz: `uname`, `/proc/cmdline`, `mount` ve imaj kimliği birlikte kontrol edilir.
Ağ dönmezse hemen flash yazılmadı diye varsaymak yerine durum ölçülür; güç
döngüsü stok sistemin geri geldiğini gösterebilir. Güç döngüsüyle kurtarma
sadece boot ortamı henüz korunmuşsa anlamlıdır.

## 4. Kaynak çekirdek ve kurtarmayı önce doğrulama

[BUILD](BUILD.md) ile Linux 6.18.55 ve eşleşen modüller üretilir. KEXEC'in
PM_SLEEP_SMP bağımlılığı korunur. RAM recovery kökü tamamen initramfs'tedir;
tüm fiziksel MTD'ler read-only olur. Normal NAND ve RAM recovery ayrı FIT'tir.
Linux Image başlığındaki image_size gerçek açılan bellek sınırlarıyla kontrol
edilir. FIT load/entry değeri mevcut test şablonundan alınır; tahmin edilmez.

Yeni native kök kurulmadan önce recovery gerçekten boot edilip LAN ve yönetim
erişimi doğrulanır. Fiziksel RESET ile kurtarma seçimi de test edilir. Kexec load
komutunun başarılı olması kernelin çalıştığını kanıtlamaz; boot sonrası kanıt alınır.

## 5. Tek OpenWrt NAND düzenine geçiş

Testte korunan fiziksel ön alan değişmeden, OEM işletim sistemi alanı OpenWrt
hacimlerine dönüştürüldü. Sonra eski 58 MiB UBI görünümü 211.25 MiB'e genişletildi.
Bu, stok MIBIB/bootloader değiştirilerek yapılmadı; bootloader UBI görünümü ve
Linux DT son bölüm sınırı birlikte ele alındı. Mevcut düzende stok OS yoktur.

İşlem yalnız UBI bağlanmamış RAM maintenance ortamından yapıldı:

1. Eski ENV/UBI/overlay ve kalan NAND kuyruğunun yedeği doğrulandı.
2. NAND yüksek adres sınırı erase/program/read geri okuma ile test edildi;
   düşük adres alias bozulması olmadığı ve korunan alan hash'leri doğrulandı.
3. Geniş geometriyi tanıyan geçiş bootcmd'si, eski ve yeni recovery CRC yolları
   birlikte korunarak yazıldı. İlk 256 KiB dışı ENV/OOB değişmedi.
4. Henüz eski hacimler silinmeden U-Boot'un 211.25 MiB UBI'den recovery
   okuyabildiği gerçek cihaz boot'u ile kanıtlandı.
5. Yeni recovery ID7 yazılıp okuma hash'i doğrulandı, hacim isimleri atomik
   UBI rename ile geçirildi; **yeni recovery gerçek boot** ile tekrar doğrulandı.
6. Ancak bundan sonra eski recovery ve küçük overlay hacimleri kaldırıldı.
   `rootfs_data` ID6, 1399 LEB olarak oluşturuldu. Üst dosyalar, sahiplik,
   izinler, xattr ve whiteout aygıtları korunarak UBIFS'e aktarıldı.
7. Overlay `.fs_state` symlink hedefi `2` (READY) korundu. Bu işaret olmazsa
   fstools geçerli üst dizini yeni/bozuk kabul ederek sıfırlayabilir.
8. Ana native FIT **en son** yazıldı. Boyut + hash geri okuması ve bootcmd
   CRC eşleşmesi doğrulanınca normal NAND açılışı seçildi.

Son hacim tablosu [ARCHITECTURE](ARCHITECTURE.md) içindedir. Referans ENV
yazıcı kaynak kodu [burada](../reference/env-writer/README.md); cihaz yedeği
içeren payload header bilerek dağıtılmaz. `dd` ile tüm NAND'a veya genel
`ubiformat /dev/mtd21` komutuyla mevcut UBI'ye yazmak bu geçişe eşdeğer değildir;
recovery ve radyo firmware hacimlerini de siler. Evrensel flash komut dizisi
ancak per-device plan/backup/CRC/power-loss tasarımı doğrulanınca eklenebilir.

## 6. İlk açılış ve kalıcılık

Salt okunur envanter: `sh tools/preflight.sh`. Root'un ubiblock0_5 olduğunu,
overlay'in rootfs_data olduğunu, `df -h /overlay` kapasitesini ve sadece son
fiziksel NAND bölümünün yazılabilir olduğunu kontrol edin. Yönetim adresi
192.168.1.1, LuCI yolu `/cgi-bin/luci/admin/`.
`passwd` ile güçlü yönetim parolası belirleyin; WAN yönetimini kapalı tutun.
Başlangıç adımında kullanılan geçici WAN Telnet'i OpenWrt'de tekrar açmayın.
[RADIOS](RADIOS.md) ile Wi-Fi/LTE'yi yapılandırın. En az yeniden başlatma,
ardından ayrıca gerçek güç kes-aç testi, veri korunması ve recovery testi gerekir.
Mevcut kayıtlarda iki normal reboot ve LTE reboot geçti; ikisi de fiziksel
güç kes-aç testi diye sunulmaz.
