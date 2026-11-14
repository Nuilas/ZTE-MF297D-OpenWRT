from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();needle='\t{ USB_DEVICE_AND_INTERFACE_INFO(ZTE_VENDOR_ID, 0x1485, 0xff, 0xff, 0xff),'
assert s.count(needle)==1
s=s.replace(needle,'\t/* MF297D control UARTs only; diagnostic, RmNet and ADB excluded. */\n\t{ USB_DEVICE_AND_INTERFACE_INFO(ZTE_VENDOR_ID, 0x1485, 0xff, 0xff, 0x40) },\n'+needle);p.write_text(s)
