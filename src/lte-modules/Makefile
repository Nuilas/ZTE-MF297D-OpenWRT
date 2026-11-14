obj-m += usbserial.o usb_wwan.o option.o usbnet.o cdc_ether.o rndis_host.o
obj-m += wwan.o cdc-wdm.o qmi_wwan.o
wwan-y := wwan_core.o
usbserial-y := usb-serial.o generic.o bus.o
ccflags-y += -DCONFIG_USB_NET_RNDIS_HOST_MODULE=1 -DCONFIG_USB_NET_CDCETHER_MODULE=1 -DCONFIG_USB_USBNET_MODULE=1 -DCONFIG_USB_SERIAL_MODULE=1 -DCONFIG_USB_SERIAL_WWAN_MODULE=1
ccflags-y += -DCONFIG_WWAN_MODULE=1 -DCONFIG_USB_WDM_MODULE=1 -DCONFIG_USB_NET_QMI_WWAN_MODULE=1
