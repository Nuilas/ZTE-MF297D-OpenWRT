// SPDX-License-Identifier: GPL-2.0-only
/* MF297D sysupgrade validation and in-place FIT MAC personalisation.
 * This program NEVER opens an MTD/UBI device for writing.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

#define FIT_MAX (16U*1024*1024)
#define ENV_SIZE 262144U
#define BOOTARGS "console=ttyMSM0,115200n8 root=/dev/ubiblock0_5 rootfstype=squashfs ro rootwait ubi.mtd=21 ubi.block=0,owrt_rootfs clk_ignore_unused maxcpus=1 panic=20 mf297d.permanent=1 mf297d.boot_span=wide coherent_pool=2M mf297d.nss_nand=20261114"
#define MAIN_BOOT "if ubi read 0x44000000 owrt_kernel; then if setenv verify yes; then if setenv bootargs '" BOOTARGS "'; then bootm 0x44000000#config@mp03.3; fi; fi; fi;"

static void fail(const char *why) { fprintf(stderr,"MF297D: %s\n",why);exit(1); }
static void need(int ok,const char *why) { if(!ok)fail(why); }
static uint32_t be32(const void *v) { const unsigned char *p=v;return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
static uint32_t le32(const unsigned char *p) { return (uint32_t)p[3]<<24|(uint32_t)p[2]<<16|(uint32_t)p[1]<<8|p[0]; }
static uint64_t le64(const unsigned char *p) { return (uint64_t)le32(p+4)<<32|le32(p); }
static void put32(unsigned char *p,uint32_t v) { for(int i=0;i<4;i++)p[i]=(unsigned char)(v>>(24-8*i)); }
static uint32_t crc32(const unsigned char *p,size_t n) { uint32_t c=~0U;while(n--){c^=*p++;for(int j=0;j<8;j++)c=(c>>1)^(0xedb88320U&-(c&1));}return ~c; }
static uint32_t rol(uint32_t x,unsigned n) { return x<<n|x>>(32-n); }
static void sha1(const unsigned char *p,size_t n,unsigned char out[20]) {
 uint32_t h[5]={0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0};
 size_t blocks=(n+9+63)/64;
 for(size_t block=0;block<blocks;block++) {
  unsigned char b[64]={0};size_t off=block*64;
  for(size_t j=0;j<64;j++){size_t at=off+j;if(at<n)b[j]=p[at];else if(at==n)b[j]=0x80;}
  if(block+1==blocks){uint64_t bits=(uint64_t)n*8;for(int j=0;j<8;j++)b[63-j]=(unsigned char)(bits>>(8*j));}
  uint32_t w[80];for(int j=0;j<16;j++)w[j]=be32(b+j*4);for(int j=16;j<80;j++)w[j]=rol(w[j-3]^w[j-8]^w[j-14]^w[j-16],1);
  uint32_t a=h[0],c=h[2],d=h[3],e=h[4],bb=h[1];
  for(int j=0;j<80;j++){uint32_t f,k;if(j<20){f=(bb&c)|(~bb&d);k=0x5a827999;}else if(j<40){f=bb^c^d;k=0x6ed9eba1;}else if(j<60){f=(bb&c)|(bb&d)|(c&d);k=0x8f1bbcdc;}else{f=bb^c^d;k=0xca62c1d6;}uint32_t t=rol(a,5)+f+e+k+w[j];e=d;d=c;c=rol(bb,30);bb=a;a=t;}
  h[0]+=a;h[1]+=bb;h[2]+=c;h[3]+=d;h[4]+=e;
 }
 for(int j=0;j<5;j++)put32(out+j*4,h[j]);
}
typedef struct {unsigned char *p;size_t n;} Blob;
static Blob load(const char *name,size_t max) {
 int fd=open(name,O_RDONLY|O_NOFOLLOW);need(fd>=0,"cannot open input");struct stat s;need(!fstat(fd,&s),"cannot stat input");
 need(S_ISREG(s.st_mode)||S_ISCHR(s.st_mode),"input is not a file/device");size_t size=S_ISCHR(s.st_mode)?max:(size_t)s.st_size;
 need(size>0 && size<=max,"input size out of range");Blob b={malloc(size),size};need(b.p!=NULL,"allocation failed");
 size_t done=0;while(done<b.n){ssize_t n=read(fd,b.p+done,b.n-done);need(n>0,"short input read");done+=(size_t)n;}close(fd);return b;
}
typedef struct {unsigned char *p;size_t n,st,en,strings,slen;} Fdt;
typedef struct {unsigned char *p;size_t n;int found;} Prop;
static Fdt fdt(Blob b) {
 need(b.n>=40 && be32(b.p)==0xd00dfeed,"invalid FDT magic");size_t n=be32(b.p+4),st=be32(b.p+8),ss=be32(b.p+12),sz=be32(b.p+32),ts=be32(b.p+36);
 need(n==b.n && st>=40 && st%4==0 && st<=n && ts<=n-st && ss<=n && sz<=n-ss,"invalid FDT bounds");
 need(be32(b.p+20)==17 && be32(b.p+24)<=17,"unsupported FDT version");Fdt f={b.p,n,st,st+ts,ss,sz};return f;
}
typedef void (*Visitor)(const char *,const char *,unsigned char *,size_t,void *);
static void walk(Fdt f,Visitor visit,void *arg) {
 size_t at=f.st,depth=0,previous[32];char path[2048]="";int ended=0;
 while(at<f.en){need(f.en-at>=4,"truncated FDT token");uint32_t token=be32(f.p+at);at+=4;
  if(token==1){need(depth<32,"FDT too deep");unsigned char *end=memchr(f.p+at,0,f.en-at);need(end!=NULL,"unterminated node");size_t len=(size_t)(end-(f.p+at)),used=strlen(path);previous[depth]=used;
   if(depth==0){need(len==0,"invalid root node");strcpy(path,"/");}else{need(len>0 && len<256 && !memchr(f.p+at,'/',len),"invalid node name");need(used+len+2<sizeof(path),"node path too long");if(used>1)path[used++]='/';memcpy(path+used,f.p+at,len);path[used+len]=0;}
   depth++;at=(at+len+1+3)&~(size_t)3;need(at<=f.en,"node exceeds structure");
  }else if(token==2){need(depth>0,"unbalanced FDT");path[previous[--depth]]=0;
  }else if(token==3){need(depth>0 && f.en-at>=8,"invalid FDT property");size_t len=be32(f.p+at),no=be32(f.p+at+4);at+=8;need(len<=f.en-at && no<f.slen,"property exceeds FDT");const char *name=(const char*)f.p+f.strings+no;need(memchr(name,0,f.slen-no)!=NULL,"unterminated property name");visit(path,name,f.p+at,len,arg);at=(at+len+3)&~(size_t)3;need(at<=f.en,"unaligned property bounds");
  }else if(token==4){}else if(token==9){need(depth==0,"unclosed FDT node");ended=1;break;}else fail("unknown FDT token");
 }
 need(ended,"missing FDT end");
}
typedef struct {const char *path,*name;Prop value;} Lookup;
static void lookup(const char *path,const char *name,unsigned char *p,size_t n,void *v) {
 Lookup *l=v;if(!strcmp(path,l->path)&&!strcmp(name,l->name)){need(!l->value.found,"duplicate property");l->value=(Prop){p,n,1};}
}
static Prop optional(Fdt f,const char *path,const char *name) {Lookup l={path,name,{0}};walk(f,lookup,&l);return l.value;}
static Prop prop(Fdt f,const char *path,const char *name) {Prop p=optional(f,path,name);need(p.found,"required FDT property missing");return p;}
static void eq(Fdt f,const char *path,const char *name,const char *value) {Prop p=prop(f,path,name);need(p.n==strlen(value)+1 && !memcmp(p.p,value,p.n),"unexpected FDT property");}
static void number(Fdt f,const char *path,const char *name,uint32_t value) {Prop p=prop(f,path,name);need(p.n==4 && be32(p.p)==value,"unexpected FDT address");}
static void hashes(Fdt f,const char *image,int update) {
 Prop data=prop(f,image,"data");char path[256];need(data.n>0,"empty FIT data");
 snprintf(path,sizeof(path),"%s/hash-1",image);eq(f,path,"algo","crc32");Prop crc=prop(f,path,"value");need(crc.n==4,"invalid CRC field");unsigned char c[4];put32(c,crc32(data.p,data.n));
 snprintf(path,sizeof(path),"%s/hash-2",image);eq(f,path,"algo","sha1");Prop sha=prop(f,path,"value");need(sha.n==20,"invalid SHA1 field");unsigned char s[20];sha1(data.p,data.n,s);
 if(update){memcpy(crc.p,c,4);memcpy(sha.p,s,20);}else need(!memcmp(crc.p,c,4)&&!memcmp(sha.p,s,20),"FIT data hash mismatch");
}
static const uint32_t part_offset[22]={0,0x80000,0x100000,0x140000,0x180000,0x280000,0x380000,0x3c0000,0x400000,0x440000,0x480000,0x500000,0x640000,0x780000,0x880000,0x900000,0x9a0000,0xa20000,0x1e20000,0x2420000,0x24c0000,0x2cc0000};
static const uint32_t part_size[22]={0x80000,0x80000,0x40000,0x40000,0x100000,0x100000,0x40000,0x40000,0x40000,0x40000,0x80000,0x140000,0x140000,0x100000,0x80000,0xa0000,0x80000,0x1400000,0x600000,0xa0000,0x800000,0xd340000};
typedef struct {Fdt f;unsigned seen;} Parts;
static void partition(const char *path,const char *name,unsigned char *p,size_t n,void *v) {
 Parts *a=v;const char *part=strstr(path,"/partitions/partition@");
 if(strcmp(name,"reg") || !part || strchr(part+strlen("/partitions/partition@"),'/'))return;
 need(n==8,"unexpected NAND partition cells");int index=-1;for(int j=0;j<22;j++)if(be32(p)==part_offset[j]&&be32(p+4)==part_size[j])index=j;
 need(index>=0 && !(a->seen&(1U<<index)),"NAND partition layout mismatch");a->seen|=1U<<index;
 Prop ro=optional(a->f,path,"read-only");need(index==21?!ro.found:(ro.found&&ro.n==0),"unsafe NAND write protection");
}
static void macs(const char *path,const char *name,unsigned char *p,size_t n,void *v) {
 if(strcmp(name,"local-mac-address"))return;need(n==6,"invalid Ethernet MAC property");uint64_t base=*(uint64_t*)v;uint64_t mac=base-(strstr(path,"/ethernet-port@5")?0x10000:0x20000);for(int j=0;j<6;j++)p[j]=(unsigned char)(mac>>(8*(5-j)));
}
static Fdt check_fit(Blob b) {
 Fdt f=fdt(b);eq(f,"/images/kernel-1","type","kernel");eq(f,"/images/kernel-1","arch","arm64");eq(f,"/images/kernel-1","os","linux");eq(f,"/images/kernel-1","compression","lzma");number(f,"/images/kernel-1","load",0x41000000);number(f,"/images/kernel-1","entry",0x41000000);
 eq(f,"/images/fdt-1","type","flat_dt");eq(f,"/images/fdt-1","compression","none");eq(f,"/configurations","default","config@mp03.3");eq(f,"/configurations/config@mp03.3","kernel","kernel-1");eq(f,"/configurations/config@mp03.3","fdt","fdt-1");
 hashes(f,"/images/kernel-1",0);hashes(f,"/images/fdt-1",0);Prop data=prop(f,"/images/fdt-1","data");Fdt d=fdt((Blob){data.p,data.n});eq(d,"/","model","ZTE MF297D");eq(d,"/chosen","bootargs",BOOTARGS);Parts parts={d,0};walk(d,partition,&parts);need(parts.seen==0x3fffff,"missing NAND partitions");return f;
}
static void check_env(Blob b) {
 need(b.n==ENV_SIZE*2,"ENV size mismatch");need(le32(b.p)==crc32(b.p+4,ENV_SIZE-4),"ENV CRC mismatch");for(size_t j=ENV_SIZE;j<b.n;j++)need(b.p[j]==255,"unexpected ENV tail");
 int marker=0,main=0;size_t at=4;
 while(at<ENV_SIZE && b.p[at]){unsigned char *end=memchr(b.p+at,0,ENV_SIZE-at);need(end!=NULL,"unterminated ENV variable");const char *s=(const char*)b.p+at;
  if(!strcmp(s,"mf297d_sysupgrade=fit-v1"))marker++;
  if(!strncmp(s,"bootcmd=",8)){need(strstr(s,MAIN_BOOT)!=NULL && strstr(s,"owrt_recovery")!=NULL && strstr(s,"setexpr.l mf297d_button *0x01020004 '&' 1;")!=NULL,"unrecognised upgrade boot command");main++;}
  at=(size_t)(end-b.p)+1;
 }
 need(marker==1&&main==1,"one-time sysupgrade boot migration required");
}
int main(int argc,char **argv) {
 if(argc==3 && !strcmp(argv[1],"--check-fit")){Blob b=load(argv[2],FIT_MAX);check_fit(b);free(b.p);puts("MF297D FIT validated");return 0;}
 if(argc==3 && !strcmp(argv[1],"--check-env")){Blob b=load(argv[2],ENV_SIZE*2);check_env(b);free(b.p);puts("MF297D sysupgrade boot layout ready");return 0;}
 if(argc==4 && !strcmp(argv[1],"--check-root")){Blob b=load(argv[2],4096);char *end;uint64_t size=strtoull(argv[3],&end,10);need(*argv[3]&&!*end&&size>=4096&&size%4096==0,"rootfs not 4KiB aligned");need(b.n>=96&&le32(b.p)==0x73717368&&b.p[20]==4&&b.p[21]==0&&b.p[28]==4&&b.p[29]==0,"unsupported squashfs");uint64_t used=le64(b.p+40);need(used>=96&&used<=size&&size-used<4096,"squashfs exceeds payload");free(b.p);puts("MF297D squashfs validated");return 0;}
 if((argc==4||argc==5)&&!strcmp(argv[1],"--personalise")){
  Blob b=load(argv[2],FIT_MAX);Fdt f=check_fit(b);const char *source=argc==5?argv[4]:"/dev/mtd16ro";int fd=open(source,O_RDONLY|O_NOFOLLOW);unsigned char mac[6];need(fd>=0&&read(fd,mac,6)==6,"factory MAC read failed");close(fd);uint64_t base=0;for(int j=0;j<6;j++)base=base<<8|mac[j];need(!(mac[0]&1)&&base>=0x20000&&base<0xfffffffffffcULL,"invalid factory MAC");Prop dt=prop(f,"/images/fdt-1","data");walk(fdt((Blob){dt.p,dt.n}),macs,&base);hashes(f,"/images/fdt-1",1);check_fit(b);
  fd=open(argv[3],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);need(fd>=0,"output must be a new regular file");size_t at=0;while(at<b.n){ssize_t n=write(fd,b.p+at,b.n-at);need(n>0,"output write failed");at+=(size_t)n;}need(!fsync(fd)&&!close(fd),"output sync failed");free(b.p);puts("MF297D kernel personalised; no flash writes");return 0;
 }
 fprintf(stderr,"Use --check-fit FILE | --check-env FILE | --check-root PREFIX BYTES | --personalise INPUT OUTPUT [MAC_FILE]\n");return 2;
}
