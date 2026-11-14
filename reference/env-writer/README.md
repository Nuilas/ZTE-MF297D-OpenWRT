# Tarihsel, sabit girdili ENV yazıcısı

`wifi_env_install.c` testte son Wi-Fi FIT bootcmd geçişinde kullanılan kaynak
kodudur. **Genel kurulum/güncelleme aracı değildir.** Yorumların bir kısmı eski
deneme evresinden kalır; gerçek sınır ve kontroller koddan incelenmelidir.
Dahil ettiği `wifi_env_payload.h` kendi cihazının tam önce/sonra ENV verisini
içerdiğinden dağıtılmaz. Bu nedenle dosya tek başına derlenmez; bu kasıtlıdır.

Yeni cihazda eski header'ı veya CRC/uzunluk sabitlerini yeniden kullanmayın.
Yeni plan; exact-before eşleşmesi, endian/CRC, tüm değişkenlerin korunması,
eski hush davranışı, fiziksel mtd10 adı/geometrisi, aarch64 native RAM kernel,
UBI bağlı olmaması, badblock/OOB ve yazılabilir bölüm whitelist kontrolü ister.
Yazma ilk iki 128KiB eraseblock ile sınırlandırılmıştır; kalan 256KiB raw/OOB
ve tam512KiB geri okuma doğrulanmıştır. Elektrik kesilmesinde atomiklik yoktur.
