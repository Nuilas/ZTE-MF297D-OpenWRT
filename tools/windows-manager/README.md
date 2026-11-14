# MF297D Yerel Yönetici 1.0

Windows için bağımsız ACS, sUser parola yönetimi ve LAN root Telnet yardımcısı.
Python ve ayrı TR069ACS uygulaması EXE çalıştırılırken gerekmez. Windows'ta Npcap sürücüsü kurulu olmalıdır: https://npcap.com/#download

## Destek kapsamı

ZTE MF297D ve Turkcell `CR_TKCTURMF297DV1.0.0B18` üzerinde bu sohbette doğrulanan işlem akışı temel alınmıştır. Başka model veya firmware için destek iddiası yoktur.

- Uygulama yalnız seçilen fiziksel Ethernet adaptörünü yapılandırır.
- ACS HTTP 80 ve HTTPS 443, DHCP, sınırlı DNS ve saat yanıtı uygulamanın içindedir.
- DNS yalnız modemin ACS ve NTP adlarına, seçili Ethernet ve tek istemci MAC adresine yanıt verir. Bilgisayarın başka adaptörlerinin DNS trafiği yönlendirilmez.
- Hesap `InternetGatewayDevice.User.1.Username = sUser` olarak doğrulanmadan parola yazılmaz.
- Geçici WAN Telnet portu **2323** üzerinden root `uid=0` doğrulanır.
- `nv set telnet_lan_enable=1` ve `nv save` ile LAN erişimi kaydedilir.
- Geçici WAN Telnet işlem sonunda tekrar kapatılır. Kapatma doğrulanmazsa hata gösterilir ve servisler açık tutulur.
- Parola uygulama ayarına veya günlüğe kaydedilmez. Config/flash yedeğinin kendi içeriği gizli veriler barındırabilir.

## Kullanım

1. Başka ACS/web sunucularını, özellikle TR069ACS'yi kapatın. Port 80/443 çakışırsa uygulama başlamaz; başka süreci kendiliğinden kapatmaz.
2. EXE'yi açın ve **Yönetici olarak yeniden aç** düğmesini kullanın. Windows onayını kullanıcı verir.
3. Modemde kablolu genişbant modunu seçin. WAN bağlantı türünü **Dinamik IP/DHCP** yapın. Alternatif statik ayar: `192.168.50.2`, maske `255.255.255.0`, ağ geçidi ve DNS `192.168.50.1`.
4. Kabloyu modemin WAN portuna takın. Uygulamada doğru fiziksel Ethernet adaptörünü açıkça seçip **WAN servislerini başlat** düğmesine basın. Uygulama bilgisayar Ethernet'ini `192.168.50.1/24`, ağ geçidi olmadan ayarlar. Modemi normal yeniden başlatın.
5. ACS bağlantısı ve sUser hesabı doğrulanınca mevcut/yeni parolayı girin. **sUser parolasını değiştir** kutusu açıksa bu hesap parolası değişir; kapalıysa girilen mevcut parola kullanılır.
6. **sUser + LAN Telnet uygula** işlemini başlatın. Sonuç ve WAN kapatma onayı gelene kadar kabloyu WAN'da tutun.
7. Modem hâlâ WAN'a bağlıyken **WAN servislerini durdur** düğmesine basın. Bu adım geçici servisleri ve uygulamanın eklediği dar kapsamlı güvenlik duvarı kurallarını kaldırır; eski Ethernet ayarını ve ACS bilgilendirme aralığını geri yükler.
8. Kabloyu LAN'a taşıyıp **LAN root bağlantısını doğrula** düğmesine basın. Bilgisayar `192.168.1.2/24` yapılır ve `192.168.1.1:2323` üzerinde sUser ile root doğrulanır.

## Yedekleme

**Config:** WAN/ACS bağlantısı açıkken Yedekler sekmesinden alınır. Cihaz Upload yöntemini desteklediğini bildirirse vendor config dosyası bilgisayara kaydedilir. Bu uygulama config veya firmware geri yüklemez.

**Flash veri alanı:** WAN servislerini durdurup LAN'a geçin. Mevcut sUser parolasını girin. Yedekler sekmesinde üst klasörü seçin. Uygulama yalnız `/dev/mtdNro` aygıtlarından okur. Her bölümün beklenen boyutu, alınan boyutu ve SHA256 özeti manifest'e kaydedilir. Eksik aktarım tamamlanmış sayılmaz.

Bu işlem **NAND OOB alanını içermez** ve programlayıcıya hazır ham NAND imajı üretmez. UBI mantıksal hacimleri fiziksel bölümlerin bir kısmını tekrar içerdiği için toplam dosya boyutu NAND kapasitesinden büyük olabilir. Canlı sistemde yazılabilir bölümler atomik bir anlık görüntü değildir. Otomatik flash yazma, silme veya geri yükleme kodu yoktur.

## Sınırlamalar ve test

Bu sürüm bir prototiptir. CWMP protokolü, alan/IP kısıtlaması, hata halinde WAN Telnet kapatma ve TFTP aktarım bütünlüğü sentetik testlerle doğrulanmıştır. Windows Ethernet/Npcap eşlemesi ve GUI açılışı bu bilgisayarda doğrulanmıştır. Ayrı komutlarla aynı modem üzerinde sUser, root Telnet, LAN Telnet ve tam MTD veri alanı aktarımı çalışmıştır. Paketlenmiş uygulamanın tüm kurulum akışı henüz fabrika ayarlı bir modem üzerinde uçtan uca denenmemiştir.

Modem sunucu sertifikasını kabul etmezse bağlantı kurulmayabilir. Uygulama cihazın sertifika doğrulama ayarını kapatmaz. Geçici WAN erişimi kapatma işlemi sonuçlanmadan uygulamayı zorla kapatmayın. Bir sonraki başlangıçta bekleyen temizlik kaydı kontrol edilir.

Çalışma dosyaları varsayılan olarak `%LOCALAPPDATA%\MF297DManager` içindedir. Burada yerel TLS sertifikası, ağ ayarı geri dönüş kaydı ve bekleyen temizlik kaydı bulunur; sUser parolası bulunmaz.

## Kaynaktan test ve derleme

Windows x64, Python 3.14 ile hazırlanmıştır.

```powershell
python -m pip install -r requirements.txt
python test_app.py
python test_flash_backup.py
python -m PyInstaller --noconfirm MF297D-Yerel-Yonetici.spec
```

Yerel önizleme, tüm modem/ağ işlemleri kapalı olarak:

```powershell
python gui.py --preview --data-dir .\preview-data
```
