# Donanım, NAND ve açılış düzeni

## Kalıcı sistem

IPQ5018 platformu, AArch64 Linux 6.18.55, 256 MiB seri NAND.
NAND sayfa 2048 bayt, eraseblock 131072 bayt, UBI LEB 126976 bayttır.
Stok ilk aşama bootloader zinciri korunur; stok işletim sistemi artık yoktur.
OpenWrt RAM recovery ikinci bir stok işletim sistemi değildir.

Fiziksel ön alan `[0, 0x2cc0000)` (44.75 MiB) korunur. Son UBI bölümü:

| Alan | Değer |
| --- | --- |
| Linux MTD | mtd21, UBI taşıyan fiziksel son bölüm |
| Başlangıç | 0x2cc0000 |
| Boyut | 0xd340000 = 211.25 MiB |
| Bitiş | 0x10000000 = 256 MiB |
| Fiziksel eraseblock | 1690 |
| Kötü blok rezervi | 40; testte görülen kötü blok 0 |

MTD numaraları yalnız bu son düzene aittir. Stokta UBI'nin mantıksal hacimleri
de MTD gibi görünebilir; sayıları fiziksel NAND bölümü sanıp toplamayın.
Etiket, offset, boyut ve erase/page geometrisi birlikte doğrulanmalıdır.

| UBI ID | İsim | Tür | Ayrılan LEB | İşlev |
| --- | --- | --- | ---: | --- |
| 1 | wifi_fw | static | 50 | Orijinal cihaza ait radyo firmware |
| 2 | bt_fw | static | 3 | Korunan kontrolcü firmware |
| 4 | owrt_kernel | static | 37 | Native Linux + DTB FIT |
| 5 | owrt_rootfs | static | 67 | SquashFS alt dosya sistemi |
| 6 | rootfs_data | dynamic | 1399 | Kalıcı UBIFS overlay |
| 7 | owrt_recovery | static | 90 | Initramfs içeren RAM recovery FIT |

ID boşlukları tarihseldir; yeniden numaralandırmayın. Root `/dev/ubiblock0_5`,
`ubi.mtd=21 ubi.block=0,owrt_rootfs`. UBIFS mantıksal hacmi 177639424 bayt;
dosya sistemi günlük/metadata alanları yüzünden `df` bunun tamamını göstermez.
17 MiB eski küçük overlay düzeniydi; mevcut kapasite yaklaşık 155 MiB'dir.

## DT varyantları

- `native`: 22 fiziksel MTD, yalnız mtd21 yazılabilir, kök NAND'da.
- `recovery`: kök initramfs; tüm fiziksel NAND bölümleri salt okunur.
- `maintenance`: kök initramfs; yalnız mtd21 yazılabilir.
- `maintenance-env`: kök initramfs; yalnız mtd10 ENV ve mtd21 yazılabilir.

Son iki varyant kurulum/bakım içindir. Normal başlangıç hedefi değildir.
Dekompile DTS'lerde sayısal phandle değerleri korunmuştur. Bunlar upstream için
temizlenmiş `dtsi` tabanlı kart tanımı değildir. İki Ethernet MAC fallback alanı
public şablonda 02:00:00:00:00:01/02 olarak değiştirilmiştir; derleme gerçek
cihazın kendi değerlerini gerektirir. Wi-Fi MAC/kalibrasyonu ayrıca ART'tan gelir.

## Boot seçimi

Korunan U-Boot, UBI içindeki ana FIT'i uzunluk + CRC32 ile doğrular; ana imaj
geçmezse doğrulanmış recovery kullanılır. RESET GPIO32 seviye biti, MMIO
0x01020004 bit0 düşükken recovery seçer. Kurulmuş bootcmd eski stok hush
ayrıştırıcısında koşul senaryolarıyla test edilmiştir; `saveenv`/OEM `bootipq`
normal akışta kullanılmaz. Mevcut ENV başka bir cihaza kopyalanmaz.

ENV 512 KiB'dır; kullanılan veri+CRC alanı ilk 256 KiB, iki eraseblock'tur.
Laboratuvar yazıcısı sadece bu aralığı değiştirdi; kalan veri/OOB korundu ve
tam okuma karşılaştırıldı. ENV güncellemesi tek adımda atomik değildir:
erase/program sırasında güç kaybına karşı UART'sız güvence verilmez.

## RAM geçişi

Stok 32-bit çekirdekte çalışan kexec bulunmadığı için ilk geçiş özel bir
stok-kernel modülü + AArch64 trampoline ile araştırıldı. Kaynakları
`reference/stock-ramboot/` altında tarihsel referanstır; stok sürüm adresleri ve
imaj sabitleri başka firmware'de geçerli değildir. Kurulu yeni native çekirdekte
CONFIG_KEXEC + CONFIG_SUSPEND/PM_SLEEP_SMP ve statik kexec-tools 2.0.32 kullanılır.
Doğrulanan yol: normal başlangıç → UBI bağlanmamış RAM maintenance → yeni hedef.
NAND kökten doğrudan başka NAND köke kexec genel güvenilir yöntem olarak geçmedi.
