include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=mf297d-host-tso
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKG_BUILD_DIR:=$(KERNEL_BUILD_DIR)/$(PKG_NAME)

include $(INCLUDE_DIR)/package.mk

define KernelPackage/mf297d-host-tso
  SUBMENU:=Network Devices
  TITLE:=MF297D NSS host IPv4 segmentation support
  DEPENDS:=@TARGET_qualcommax_ipq50xx +kmod-qca-dwmac-nss +ethtool
  FILES:=$(PKG_BUILD_DIR)/mf297d_host_tso.ko
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(KERNEL_MAKE) M="$(PKG_BUILD_DIR)" modules
	$(TARGET_CROSS)objcopy -O binary --only-section=.notes $(LINUX_DIR)/vmlinux $(PKG_BUILD_DIR)/kernel.notes
	sha256sum $(PKG_BUILD_DIR)/kernel.notes | cut -d ' ' -f 1 > $(PKG_BUILD_DIR)/kernel-notes.sha256
endef

define KernelPackage/mf297d-host-tso/install
	$(INSTALL_DIR) $(1)/usr/lib/mf297d-host-tso
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/kernel-notes.sha256 $(1)/usr/lib/mf297d-host-tso/kernel-notes.sha256
endef

$(eval $(call KernelPackage,mf297d-host-tso))
