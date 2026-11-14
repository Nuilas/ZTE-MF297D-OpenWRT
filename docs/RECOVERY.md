# Kurtarma ve güncelleme

Kurulu düzende U-Boot kalır; varsayılan OpenWrt NAND, ikinci hedef OpenWrt RAM
recovery'dir. Recovery stok OS değildir. Fiziksel RESET seçimi bootloader
evresinde doğrulandı. Çalışan Linux'ta RESET'e uzun basmanın fabrika ayarı
davranışı ayrıca test edilmedi; çalışma anında rastgele uzun basmayın.

Boot sırasında RESET düşük seviyesi GPIO32 bit0 üzerinden okunur. Testte tuş
yeniden başlatmadan önce basılı tutuldu, recovery erişimi görülünce bırakıldı.
UART olmayan yeni cihazda bu davranış bootcmd ve fiziksel kart revizyonu için
doğrulanmadan geçerli kabul edilmez. LAN kablosu LAN1/2/3'te, PC 192.168.1.x/24
olmalıdır. Recovery erişimini `uname`, RAM root ve salt okunur MTD ile doğrulayın.

## Recovery açıldığında

Önce sadece `preflight.sh` ile envanter alın. Ağ/MTD geometri ve mevcut FIT/ENV
hash'lerini son özel yedek manifestiyle karşılaştırın. Recovery normalde tüm
NAND'ı read-only açar; bu kasıtlıdır. Yazma yetkisi gerekiyorsa ayrı maintenance
DT ve plan gerekir. ENV'yi writable açmak normal recovery'nin görevi değildir.

## Güncelleme sınırı

Genel `sysupgrade` ve LuCI firmware yükleme henüz doğrulanmadı. Bootcmd ana ve
recovery FIT'lerini belirli uzunluk/CRC ile kabul eder. Bir bayt değişen yeni
DTB, sıkıştırılmış Image veya FIT yeni CRC gerektirir. Yeni FIT'i doğrudan
`owrt_kernel` üzerine yazmak otomatik güncelleme değildir: bootloader reddedip
recovery'ye düşebilir. Bozuk recovery de mevcutsa yönetim kaybolabilir.

Yeni sürüm için önce ayrı RAM test, rootfs/kernel/module ABI eşleşmesi, gerçek
recovery boot'u, per-device ENV planı, offline hush koşul testi ve geri okuma
kontrolleri gerekir. Otomatik kurucunun güç kesilmesindeki davranışı henüz
tamamlanmadı. Mevcut tek kopyalı ENV erase/program işlemi atomik değildir.

Bootloader/ENV/ART bozulursa Ethernet recovery garantisi yoktur; UART/JTAG veya
fiziksel NAND programlayıcı gerekebilir. Bu sınırlama mevcut donanım erişimiyle
kaldırılmış değildir. Stok OS geri dönüşü yalnız bu cihaza ait özel yedekler ve
uygun geri yükleme planıyla yapılabilir; repo bunları içermez.
