# Wi-Fi ve LTE

## Wi-Fi'nin çalışan kombinasyonu

IPQ5018 hw1.0 + QCN6122 hw1.0; eşleşen stok firmware
`WLAN.HK.2.5.r4-00745-QCAHKSWPL_SILICONZ-1` (fw_version 0x250282e9).
Yeni 2.7 firmware ile eski board/cal verisini karıştırmak QCN anten-axis assert
üretti; son çözüm aynı cihazın stok 2.5 firmware + board + ART eşleşmesidir.

Firmware dağıtılmaz. Kendi `wifi_fw` yedeğinizi salt okunur açarak
`q6_fw.*`, `m3_fw.*` dosyalarını ilgili
`/lib/firmware/ath11k/{IPQ5018,QCN6122}/hw1.0/` dizinine koyun.
IPQ5018 `bdwlan.b24`, QCN6122 `qcn6122/bdwlan.b60` kendi alt dizinlerinde
`board.bin` olarak kullanıldı (toplam 33 dosya). Referans paketleme aracı
`tools/package_stock_fw.py` sadece açılmış yerel klasörden özel tar üretir.
Testte stok squashfs'in XZ options kaydı standart decoder tarafından
okunamadı; sadece ayrı decoder kopyasının 96. offset metadata kaydı düzeltildi.
Bu kopya hiçbir zaman NAND'a yazılmadı; başka firmware'de aynı offset varsayılmaz.

DT: `/soc@0/remoteproc@cd00000`, `wifi@c000000`, `wifi@b00a040` açık;
`wifi@b00b040` ve pd-3 kapalı. Q6 0x4b000000/0x3900000; mode1 root DDR
0x4c000000/0xe00000, QCN DDR 0x4d200000/0x1000000. M3 dump sırasıyla
0x4ce00000/0x4e200000, caldb 0x4d000000/0x4e400000. Boot-args altı u32:
`1,4,2,15,0,0`. RAM denemesinde `coherent_pool=2M` gerekir; Q6 loader'ın
GFP_DMA isteği varsayılan havuza sığmadı. Native/recovery bootargs farklıdır;
public DT'ler son çalışan varyantların MAC değiştirilmiş kopyalarıdır.

Kendi ART yedeğinden IPQ5018 offset 0x1000 ve QCN6122 offset 0x26800,
her biri 0x20000 bayt kalibrasyon alınır. MAC tabanı kendi MAC bölümü ilk
6 baytından; radyo MAC'leri base+2/base+3. Kalibrasyon MAC alanı offset0xe,
checksum offset0xa; bütün 16-bit little-endian kelimelerin XOR'u 0xffff olmalı.
`tools/prepare_caldata.py` bunu dosya üzerinde yapar; cihaza yazmaz.
Başka cihazın ART'ını kullanmayın. Ortaya çıkan dosyalar private tutulmalıdır.

Eşleşen backports 7.2 modülleri compat/cfg80211/mac80211/ath/qmi_helpers/ath11k/
ath11k_ahb. Deneysel platform-glue ve DMA-prepare modülleri son çözümden
çıkarıldı. `files/etc/init.d/mf297d-wifi` START95 servisi ve
`/usr/sbin/mf297d-wifi-start` başlangıcı en az 35. saniyeye/netifd hazır olana
kadar erteler, sırayla modprobe ve wifi reload yapar. Shell dosyaları LF olmalı;
CRLF ilk otomatik yükleme denemesini bozdu. Dosyalar hedefte executable olmalı.

Örnek ilk doğrulama: ülke TR, 2.4GHz ch6 HE20; 5GHz ch36 HE80,
WPA2/WPA3 SAE-mixed, güçlü size özel PSK. Sonradan seçtiğiniz kanalı/PSK'yi
şablon yükleyerek ezmeyin. Bölge/DFS ve güç limitlerini yerel kurala göre kullanın.
Beacon görmek, istemciyle aktarım hızı/menzil/uzun süre kararlılık testi değildir.

## LTE

Modem USB 19d2:1485; test modeli MF297D, baseband
BD_TKCTURMF297DMODV1.0.0B15. Interface3/4 ff:ff:40 AT portlarıdır; option
patch sadece bu sınıfa eklenir. Interface2 diagnostic,5 QMI RmNet,6 ADB'dir.
QMI'nin interface5 eşleşmesi Linux qmi_wwan içinde zaten vardır.
Seri portları körlemesine tüm ff arayüzlerine bağlamayın.

`src/lte-modules/build.sh` eşleşen Linux ağacından 9 modül derler. Runtime
autoload listesi usbnet,wwan,cdc-wdm,qmi_wwan,usbserial,usb_wwan,option'dır.
QMI aygıtı `/dev/cdc-wdm0`, veri arayüzü wwan0. RNDIS usb0 ilk denemede
DHCP lease vermedi; son bağlantı QMI/raw-IP üzerinden yapıldı.

Gereken userspace: `uqmi`, `kmod` modül yükleme altyapısı, netifd QMI protokolü,
isteğe bağlı LuCI QMI protokol paketi. Örnek UCI (APN'yi kendi hattınız için seçin):

```uci
config interface 'lte'
  option proto 'qmi'
  option device '/dev/cdc-wdm0'
  option apn 'OPERATOR_APN'
  option auth 'none'
  option pdptype 'ip'
  option dhcp '0'
  option autoconnect '1'
  option peerdns '1'
  option metric '20'
  option delay '8'
  option timeout '30'
```

Firewall mevcut WAN zone'una `lte` ağı tek kez eklenir; masquerade ve LAN→WAN
forwarding doğrulanır. Bu şablon mevcut ağ/firewall dosyanızı bütünüyle değiştirmez.
PIN gerekiyorsa özel UCI dosyasında yapılandırılır; PIN/ICCID/IMSI loglara konmaz.
IMS/SOS modem profillerine dokunulmaz. MTU testte modemden gelen 1500 bırakıldı.
`uqmi -d /dev/cdc-wdm0 --get-signal-info` ve `ubus call network.interface.lte status`
tanı için kullanılabilir; ikinci çıktıda IP bilgisi vardır, public logdan çıkarın.

SIM READY, Vodafone TR LTE kayıt, CGATT1, QMI IP/route/DNS ve reboot sonrası
otomatik bağlantı geçti. Operatör web sitesi hem HTTP hem HTTPS erişildi.
Google/OpenWrt genel erişimi geçmedi; kullanıcı **SIM'de paket olmadığını**
doğruladı. Durum kotasız hatla uyumlu; tam internet çalışıyor diye raporlanmaz.
Paketli SIM ile genel HTTPS, DNS, hız, uzun süre bağlantı ve yeniden bağlanma
testleri sıradadır. NDISDUP denemesi/RNDIS son kalıcı yöntem değildir.
