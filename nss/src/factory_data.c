// SPDX-License-Identifier: GPL-2.0-only
/* Read the owner's factory data. Never writes an MTD device. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
static void die(const char *s) { perror(s); exit(1); }
static void readat(const char *p, void *b, size_t n, off_t off) {
 int f=open(p,O_RDONLY); if(f<0)die(p);
 if(pread(f,b,n,off)!=(ssize_t)n)die("factory read"); close(f);
}
static uint16_t checksum(const unsigned char *b) {
 uint16_t x=0; for(size_t i=0;i<0x20000;i+=2)x^=(uint16_t)b[i]|((uint16_t)b[i+1]<<8); return x;
}
static void format(uint64_t v, char s[18]) {
 snprintf(s,18,"%02x:%02x:%02x:%02x:%02x:%02x",(unsigned)(v>>40)&255,(unsigned)(v>>32)&255,(unsigned)(v>>24)&255,(unsigned)(v>>16)&255,(unsigned)(v>>8)&255,(unsigned)v&255);
}
int main(int argc,char **argv) {
 if(argc!=3 && argc!=5) {fprintf(stderr,"Use: factory-data macs MAC_FILE | cal ART_FILE MAC_FILE OUTPUT_DIR\n");return 2;}
 int cal=!strcmp(argv[1],"cal"); if((cal && argc!=5)||(!cal && strcmp(argv[1],"macs")))return 2;
 unsigned char mac[6]; readat(argv[cal?3:2],mac,6,0);uint64_t base=0;
 for(int i=0;i<6;i++)base=(base<<8)|mac[i];
 if((mac[0]&1)||base<0x20000||base>=0xfffffffffffcULL)return 3;
 if(!cal) {char s[18];const char *names[]={"lan","wan","wifi2g","wifi5g"};uint64_t values[]={base-0x20000,base-0x10000,base+2,base+3};for(int i=0;i<4;i++){format(values[i],s);printf("%s=%s\n",names[i],s);}return 0;}
 const off_t offsets[]={0x1000,0x26800};const char *names[]={"IPQ5018/hw1.0/cal-ahb-c000000.wifi.bin","QCN6122/hw1.0/cal-ahb-b00a040.wifi.bin"};
 unsigned char b[0x20000];
 for(int i=0;i<2;i++) {
  readat(argv[2],b,sizeof(b),offsets[i]);if(checksum(b)!=0xffff){fprintf(stderr,"Invalid ART checksum\n");return 4;}
  uint64_t value=base+2+i;for(int j=0;j<6;j++)b[14+j]=(value>>(8*(5-j)))&255;
  b[10]=b[11]=0;uint16_t c=checksum(b)^0xffff;b[10]=c&255;b[11]=c>>8;if(checksum(b)!=0xffff)return 5;
  char path[1024];if(snprintf(path,sizeof(path),"%s/%s",argv[4],names[i])>=(int)sizeof(path))return 6;
  int f=open(path,O_WRONLY|O_CREAT|O_EXCL,0644);if(f<0)die(path);
  if(write(f,b,sizeof(b))!=(ssize_t)sizeof(b))die("calibration output");if(close(f))die("close");
 }
 return 0;
}
