# Stok kernel RAM geçişi — araştırma kaynakları

Bu dosyalar stok 32-bit kernelden AArch64 initramfs'e geçiş araştırması ve
read-only NAND/OOB okuyucularının kaynaklarıdır. Çalışan normal OpenWrt bunları
yüklemez. `ramboot_config.h` eski stok sürüme/imaja bağlı adres ve CRC sabitleri
taşır; bir dağıtım konfigürasyonu değildir. Derleme için araştırma sırasında
üretilen imaj/trampoline header'ları ve eşleşen stok kernel ABI gerekir.
Bu kaynaklar eksiksiz evrensel RAM boot kurucusu diye sunulmaz.

Eski module symbol adresini başka firmware üzerinde kullanmak kernel çökmesine
yol açabilir. Yeni native OpenWrt geçişi için kexec-tools reçetesi BUILD.md'dedir.
NAND okuyucuları veri/OOB ABI ve mtd geometri kontrolü incelenerek kullanılmalıdır;
data-only çıktı raw page+OOB programlayıcı imajına eşdeğer değildir.
