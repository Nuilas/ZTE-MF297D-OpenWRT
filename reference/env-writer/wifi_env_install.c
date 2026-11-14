/* Fixed, readback-verified MF297D Wi-Fi boot profile transition.
 * Only first256KiB of ENV10; matched native RAM maintenance required.
 * Existing expanded OpenWrt recovery remains unchanged. No general writer. */



#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <signal.h>
#include "wifi_env_payload.h"

struct mtd_info_user { uint8_t type; uint32_t flags,size,erasesize,writesize,oobsize; uint64_t padding; };
struct mtd_oob_buf64 { uint64_t start; uint32_t pad,length; uint64_t usr_ptr; };
struct erase_info_user { uint32_t start,length; };
#define MEMGETINFO _IOR('M',1,struct mtd_info_user)
#define MEMERASE _IOW('M',2,struct erase_info_user)
#define MEMGETBADBLOCK _IOW('M',11,int64_t)
#define MEMREADOOB64 _IOWR('M',22,struct mtd_oob_buf64)
#define MTDFILEMODE _IO('M',19)
_Static_assert(sizeof(struct mtd_info_user)==32,"MTD ABI");
_Static_assert(sizeof(struct mtd_oob_buf64)==24,"OOB ABI");


static volatile sig_atomic_t write_active;
static void finish_native_operation(void) { write_active=0; }
static void interrupted(int signal) {finish_native_operation();_exit(128+signal);}
static void fail(const char *message) {
    int error=errno;finish_native_operation();
    fprintf(stderr,"ABORT: %s (errno=%d, write_active=%d)\n",message,error,(int)write_active);exit(1);
}
static uint32_t crc32(const unsigned char *data,size_t n) {
    uint32_t crc=0xffffffffU;
    for(size_t i=0;i<n;i++) { crc^=data[i];for(int j=0;j<8;j++)crc=(crc>>1)^(0xedb88320U&-(crc&1)); }
    return ~crc;
}
static void fixture_check(void) {
    uint32_t stored=(uint32_t)probe_data[0]|(uint32_t)probe_data[1]<<8|
        (uint32_t)probe_data[2]<<16|(uint32_t)probe_data[3]<<24;
    if(sizeof(probe_data)!=262144 || crc32(probe_data+4,sizeof(probe_data)-4)!=stored)fail("embedded CRC");
    int count=0,bootcmd=0,marker=0;
    const char *p=(const char*)probe_data+4,*end=(const char*)probe_data+sizeof(probe_data);
    while(p<end && *p) {
        size_t len=strnlen(p,end-p);if(p+len>=end)fail("unterminated variable");
        if(!strncmp(p,"bootcmd=",8)) {if(strcmp(p,"bootcmd=sleep 2; if setexpr.l mf297d_button *0x01020004 '&' 1; then if itest.l ${mf297d_button} == 0; then if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery; then if crc32 0x44000000 0xad9cfc 0x43000000; then if itest.l *0x43000000 == 0x88e01cd0; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery_old; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_kernel; then if crc32 0x44000000 0x45f4ac 0x43000000; then if itest.l *0x43000000 == 0xc8e65233; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ubiblock0_5 rootfstype=squashfs ro rootwait ubi.mtd=21 ubi.block=0,owrt_rootfs clk_ignore_unused maxcpus=1 panic=20 mf297d.permanent=1 mf297d.boot_span=wide coherent_pool=2M'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery; then if crc32 0x44000000 0xad9cfc 0x43000000; then if itest.l *0x43000000 == 0x88e01cd0; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0xd340000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery_old; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=wide'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0x3a00000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=legacy'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; if setenv mtdids nand0=nand0; then if setenv mtdparts 'mtdparts=nand0:0x3a00000@0x2cc0000(fs)'; then if ubi part fs; then if ubi read 0x44000000 owrt_recovery_old; then if crc32 0x44000000 0xad9dec 0x43000000; then if itest.l *0x43000000 == 0x8082a1e6; then if setenv bootargs 'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs swiotlb=1 coherent_pool=2M reset_devices maxcpus=1 nr_cpus=1 clk_ignore_unused panic=20 mf297d.boot_span=legacy'; then bootm 0x44000000#config@mp03.3; fi; fi; fi; fi; fi; fi; fi; reset"))fail("changed bootcmd");bootcmd++;}
        if(!strncmp(p,"bootargs=",9) && strstr(p," mf297d_env_probe=1"))marker++;
        count++;p+=len+1;
    }
    if(count!=26 || bootcmd!=1 || marker!=1)fail("unexpected environment variables");
}
static void identify(int fd,int ro) {
    struct stat st;struct mtd_info_user info;
    if(fstat(fd,&st) || !S_ISCHR(st.st_mode) || major(st.st_rdev)!=90 || minor(st.st_rdev)!=(ro?21:20))fail("MTD node identity");
    if(ioctl(fd,MEMGETINFO,&info))fail("MEMGETINFO");
    if(info.type!=4 || info.size!=524288 || info.erasesize!=131072 || info.writesize!=2048 || info.oobsize!=64)fail("MTD geometry");
    for(int64_t offset=0;offset<524288;offset+=131072)if(ioctl(fd,MEMGETBADBLOCK,&offset)!=0)fail("bad block or query failure");
}
static void all_ff(const unsigned char *data,size_t n) {for(size_t i=0;i<n;i++)if(data[i]!=255)fail("environment not fully erased; never overwrite");}
static unsigned char tail_oob[8192];
static int tail_saved;
static void check_blank_raw(int fd,unsigned start,unsigned end,int erased_oob) {
    if(ioctl(fd,MTDFILEMODE,3))fail("raw read mode unavailable");
    unsigned char page[2048],oob[64];
    for(unsigned offset=start;offset<end;offset+=2048) {
        if(pread(fd,page,sizeof(page),offset)!=sizeof(page))fail("raw data read");
        all_ff(page,sizeof(page));memset(oob,0xa5,sizeof(oob));
        struct mtd_oob_buf64 request={.start=offset,.length=64,.usr_ptr=(uintptr_t)oob};
        if(ioctl(fd,MEMREADOOB64,&request) || request.length!=64)fail("raw OOB read");
        if(erased_oob)all_ff(oob,sizeof(oob));
        else {
            if(offset<262144 || offset>=524288)fail("tail snapshot bounds");
            unsigned char *saved=tail_oob+((offset-262144)/2048)*64;
            if(!tail_saved)memcpy(saved,oob,64);
            else if(memcmp(saved,oob,64))fail("tail OOB changed");
        }
    }
    if(!erased_oob && start==262144 && end==524288)tail_saved=1;
}
static void check_before(int fd) {
    unsigned char page[2048];
    for(unsigned offset=0;offset<524288;offset+=2048) {
        if(pread(fd,page,2048,offset)!=2048)fail("baseline read");
        if(offset<262144){if(memcmp(page,before_data+offset,2048))fail("ENV differs from fixed baseline");}
        else all_ff(page,2048);
    }
}
static void sys_value(const char *p,const char *expected) {
    char b[128];int fd=open(p,O_RDONLY|O_NOFOLLOW);if(fd<0)fail("UBI metadata open");
    ssize_t n=read(fd,b,sizeof(b)-1);close(fd);if(n<=0)fail("UBI metadata read");
    b[n]=0;b[strcspn(b,"\r\n")]=0;if(strcmp(b,expected))fail(p);
}
static void layout_ready(void) {
    sys_value("/sys/class/mtd/mtd21/name","maintenance_storage");
    sys_value("/sys/class/mtd/mtd21/size","221511680");
    sys_value("/sys/class/mtd/mtd10/flags","0x400");
    if(access("/sys/class/ubi/ubi0/mtd_num",F_OK)==0)fail("UBI must remain detached before ENV transition");
}

int main(int argc,char **argv) {
    fixture_check();
    if(argc==2 && !strcmp(argv[1],"--selftest")) {puts("{\"embedded_fixture_valid\":true,\"bootcmd\":\"expanded-layout-auto-crc\",\"writes\":0}");return 0;}
    int write_requested=argc==2 && !strcmp(argv[1],"--install-wifi-profile");
    if(argc!=2 || (!write_requested && strcmp(argv[1],"--check"))) {fprintf(stderr,"Use --check or --selftest. Writing requires --install-wifi-profile.\n");return 2;}
    struct utsname uts;
    if(uname(&uts) || strcmp(uts.machine,"aarch64") || strcmp(uts.release,"6.18.55"))fail("requires matched native AArch64 RAM maintenance kernel");
    layout_ready();
    char name[64]={0};int namefd=open("/sys/class/mtd/mtd10/name",O_RDONLY|O_NOFOLLOW);
    if(namefd<0)fail("MTD name");ssize_t n=read(namefd,name,sizeof(name)-1);close(namefd);
    if(n<=0)fail("MTD name read");name[strcspn(name,"\r\n")]=0;
    if(strcasecmp(name,"0:APPSBLENV"))fail("wrong partition name");
    int raw=open("/dev/mtd10ro",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(raw<0)fail("readonly environment open");identify(raw,1);check_before(raw);check_blank_raw(raw,262144,524288,0);close(raw);
    if(!write_requested) {puts("{\"native_ram_driver\":true,\"fixed_baseline_matches\":true,\"tail_oob_snapshot_valid\":true,\"erase_required\":true,\"bad_blocks\":0,\"writes\":0}");return 0;}
    int fd=open("/dev/mtd10",O_RDWR|O_SYNC|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0)fail("environment open");identify(fd,0);
    
    unsigned char page[2048];
    check_before(fd);
    
    if(atexit(finish_native_operation))fail("cleanup registration");
    signal(SIGTERM,interrupted);signal(SIGINT,interrupted);signal(SIGHUP,interrupted);
    write_active=1;
    sys_value("/sys/class/mtd/mtd10/flags","0x400");
    for(unsigned offset=0;offset<262144;offset+=131072) {
        struct erase_info_user erase={.start=offset,.length=131072};
        if(ioctl(fd,MEMERASE,&erase))fail("fixed ENV erase failed; no retry");
    }
    raw=open("/dev/mtd10ro",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(raw<0)fail("post-erase raw open");identify(raw,1);
    check_blank_raw(raw,0,262144,1);check_blank_raw(raw,262144,524288,0);close(raw);
    for(unsigned offset=0;offset<sizeof(probe_data);offset+=2048)
        if(pwrite(fd,probe_data+offset,2048,offset)!=2048)fail("program failed; no retry or erase attempted");
    finish_native_operation();
    if(write_active)fail("native operation state error");
    
    if(close(fd))fail("close/sync failed; verify before reboot");
    fd=open("/dev/mtd10ro",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0)fail("readback reopen");identify(fd,1);
    for(unsigned offset=0;offset<524288;offset+=2048) {
        if(pread(fd,page,sizeof(page),offset)!=sizeof(page))fail("readback failed");
        if(offset<sizeof(probe_data)) {if(memcmp(page,probe_data+offset,2048))fail("probe readback mismatch");}
        else all_ff(page,sizeof(page));
    }
    close(fd);
    raw=open("/dev/mtd10ro",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(raw<0)fail("tail raw reopen");identify(raw,1);check_blank_raw(raw,262144,524288,0);close(raw);
    puts("{\"programmed_bytes\":262144,\"readback_verified\":true,\"erase_operations\":2,\"erased_range\":\"ENV offset 0..262143 only\",\"bootcmd\":\"expanded-layout-auto-crc\",\"native_write_scope_completed\":true,\"reboot_performed\":false}");
    return 0;
}
