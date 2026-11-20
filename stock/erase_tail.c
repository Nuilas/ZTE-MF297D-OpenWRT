/* SPDX-License-Identifier: GPL-2.0-only
 * Fixed MF297D stock tail only: [58MiB,211.25MiB) inside physical MTD21.
 * Never touches its original UBI prefix, ENV, bootloader or calibration.
 */
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
struct info {uint8_t type;uint32_t flags,size,erase,page,oob;uint64_t padding;};
struct erase {uint32_t start,length;};
#define MEMGETINFO _IOR('M',1,struct info)
#define MEMERASE _IOW('M',2,struct erase)
#define MEMGETBADBLOCK _IOW('M',11,int64_t)
_Static_assert(sizeof(struct info)==32,"MTD ABI");
static void fail(const char *s){perror(s);exit(1);}
static void value(const char *p,const char *v){char b[160];int fd=open(p,O_RDONLY|O_NOFOLLOW);if(fd<0)fail(p);ssize_t n=read(fd,b,sizeof(b)-1);close(fd);if(n<=0)fail(p);b[n]=0;b[strcspn(b,"\r\n")]=0;if(strcmp(b,v)){errno=EINVAL;fail(p);}}
int main(int argc,char **argv){
 int write_requested=argc==2&&!strcmp(argv[1],"--erase-tail");
 if(argc!=2||(!write_requested&&strcmp(argv[1],"--check")))return 2;
 struct utsname u;if(uname(&u)||strcmp(u.machine,"aarch64")||strcmp(u.release,"6.18.60"))return 3;
 char line[2048]={0};int c=open("/proc/cmdline",O_RDONLY);if(c<0)fail("cmdline");ssize_t n=read(c,line,sizeof(line)-1);close(c);if(n<=0||!strstr(line,"mf297d.install_stock=2")||!strstr(line,"root=/dev/ram0"))return 4;
 value("/sys/class/mtd/mtd21/name","maintenance_storage");value("/sys/class/mtd/mtd21/size","221511680");value("/sys/class/mtd/mtd21/flags","0x400");
 if(access("/sys/class/ubi/ubi0/mtd_num",F_OK)==0)return 5;
 int fd=open(write_requested?"/dev/mtd21":"/dev/mtd21ro",(write_requested?O_RDWR|O_SYNC:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW);if(fd<0)fail("MTD21");
 struct stat st;struct info m;if(fstat(fd,&st)||!S_ISCHR(st.st_mode)||major(st.st_rdev)!=90||minor(st.st_rdev)!=(write_requested?42:43)||ioctl(fd,MEMGETINFO,&m))fail("MTD identity");
 if(m.type!=4||m.size!=0xd340000||m.erase!=131072||m.page!=2048||m.oob!=64)return 6;
 unsigned skipped=0,blocks=0;unsigned char page[2048];
 for(uint32_t at=0x3a00000;at<0xd340000;at+=131072){
  int64_t off=at;int bad=ioctl(fd,MEMGETBADBLOCK,&off);if(bad<0)fail("badblock query");if(bad){skipped++;continue;}blocks++;
  if(write_requested){struct erase e={at,131072};if(ioctl(fd,MEMERASE,&e))fail("tail erase; NO AUTOMATIC RETRY");for(uint32_t p=0;p<131072;p+=2048){if(pread(fd,page,sizeof(page),at+p)!=(ssize_t)sizeof(page))fail("tail readback");for(size_t i=0;i<sizeof(page);i++)if(page[i]!=255){errno=EIO;fail("tail not erased");}}}
 }
 if(close(fd))fail("close");
 printf("{\"tail_only\":true,\"write_requested\":%s,\"good_blocks\":%u,\"bad_blocks_skipped\":%u}\n",write_requested?"true":"false",blocks,skipped);
 return 0;
}
