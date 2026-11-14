/* MF297D raw NAND reader. Opens only /dev/mtd0ro..mtd24ro, O_RDONLY.
 * No erase, flash write, boot, module, /dev/mem or configuration operations. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
struct mtd_info_user { uint8_t type; uint32_t flags,size,erasesize,writesize,oobsize; uint64_t padding; };
struct mtd_oob_buf64 { uint64_t start; uint32_t pad,length; uint64_t usr_ptr; };
#define MEMGETINFO _IOR('M',1,struct mtd_info_user)
#define MEMREADOOB64 _IOWR('M',22,struct mtd_oob_buf64)
#define MEMGETBADBLOCK _IOW('M',11,int64_t)
#define MTDFILEMODE _IO('M',19)
_Static_assert(sizeof(struct mtd_info_user)==32,"info ABI");
_Static_assert(sizeof(struct mtd_oob_buf64)==24,"oob ABI");
static uint32_t crc_table[256];
static uint32_t crc_update(uint32_t crc,const unsigned char *p,size_t n) {
    for(size_t i=0;i<n;i++) crc=crc_table[(crc^p[i])&255]^(crc>>8);
    return crc;
}
static int send_all(int s,const void *data,size_t n) {
    const unsigned char *p=data;
    while(n) { ssize_t w=send(s,p,n,MSG_NOSIGNAL); if(w<0 && errno==EINTR)continue; if(w<=0)return -1; p+=w;n-=w; }
    return 0;
}
static void be64(unsigned char *p,uint64_t v) { for(int i=7;i>=0;i--) {p[i]=v&255;v>>=8;} }
int main(int argc,char **argv) {
    if(argc!=5) {fprintf(stderr,"Usage: nand-readonly /dev/mtdNro PC_IP PORT TOKEN\n");return 2;}
    unsigned index;char tail,path[32];
    if(sscanf(argv[1],"/dev/mtd%uro%c",&index,&tail)!=1 || index>24)return 2;
    snprintf(path,sizeof(path),"/dev/mtd%uro",index);if(strcmp(path,argv[1]))return 2;
    if(strlen(argv[4])!=32 || strspn(argv[4],"0123456789abcdef")!=32)return 2;
    char *end;long port=strtol(argv[3],&end,10);if(*end || port<1024 || port>65535)return 2;
    struct sockaddr_in dest={.sin_family=AF_INET,.sin_port=htons((uint16_t)port)};
    /* This build sends only to this PC's isolated modem-facing address. */
    if(strcmp(argv[2],"192.168.1.2") || inet_pton(AF_INET,argv[2],&dest.sin_addr)!=1)return 2;
    signal(SIGPIPE,SIG_IGN);
    int fd=open(path,O_RDONLY|O_CLOEXEC);if(fd<0){perror("open readonly");return 3;}
    struct mtd_info_user m;
    if(ioctl(fd,MEMGETINFO,&m)<0 || m.type!=4 || m.writesize!=2048 || m.oobsize!=64 || m.erasesize!=131072 || m.size%m.erasesize){fprintf(stderr,"Unsupported NAND geometry\n");close(fd);return 4;}
    if(ioctl(fd,MTDFILEMODE,3)<0){perror("raw file mode");close(fd);return 5;}
    char bad[8192];size_t used=0;unsigned bad_count=0;
    for(uint32_t off=0;off<m.size;off+=m.erasesize) {
        int64_t addr=off;int rc=ioctl(fd,MEMGETBADBLOCK,&addr);
        if(rc<0){perror("bad block read");close(fd);return 6;}
        if(rc>0){int n=snprintf(bad+used,sizeof(bad)-used,"%s%u",bad_count?",":"",off);if(n<0 || (size_t)n>=sizeof(bad)-used){close(fd);return 6;}used+=(size_t)n;bad_count++;}
    }
    bad[used]=0;
    int s=socket(AF_INET,SOCK_STREAM,0);if(s<0){perror("socket");close(fd);return 7;}
    struct timeval limit={.tv_sec=60,.tv_usec=0};
    if(setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&limit,sizeof(limit)) || setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&limit,sizeof(limit))){perror("socket timeout");close(s);close(fd);return 7;}
    if(connect(s,(struct sockaddr*)&dest,sizeof(dest))<0){perror("connect");close(s);close(fd);return 7;}
    char header[9000];int hl=snprintf(header,sizeof(header),"{\"token\":\"%s\",\"index\":%u,\"data_bytes\":%u,\"page\":%u,\"oob\":%u,\"erase\":%u,\"raw\":true,\"bad_block_offsets\":[%s]}\n",argv[4],index,m.size,m.writesize,m.oobsize,m.erasesize,bad);
    if(hl<0 || (size_t)hl>=sizeof(header) || send_all(s,header,(size_t)hl)<0){close(s);close(fd);return 8;}
    char ack[3];size_t ar=0;
    while(ar<3){ssize_t n=recv(s,ack+ar,3-ar,0);if(n<=0){close(s);close(fd);return 8;}ar+=(size_t)n;}
    if(memcmp(ack,"GO\n",3)){close(s);close(fd);return 8;}
    for(unsigned i=0;i<256;i++){uint32_t c=i;for(int k=0;k<8;k++)c=(c>>1)^((c&1)?0xedb88320U:0);crc_table[i]=c;}
    uint32_t crc=0xffffffffU;uint64_t sent=0;unsigned char block[64*(2048+64)];
    for(uint32_t off=0;off<m.size;off+=m.erasesize) {
        for(unsigned page=0;page<64;page++) {
            unsigned char *p=block+page*2112;uint64_t pos=(uint64_t)off+page*2048;
            ssize_t got=pread(fd,p,2048,(off_t)pos);
            if(got!=2048){fprintf(stderr,"Raw data read failed at 0x%"PRIx64", got %ld errno %d\n",pos,(long)got,errno);close(s);close(fd);return 9;}
            struct mtd_oob_buf64 o={.start=pos,.length=64,.usr_ptr=(uintptr_t)(p+2048)};
            int rc=ioctl(fd,MEMREADOOB64,&o);
            if(rc || o.length!=64){fprintf(stderr,"Raw OOB read failed at 0x%"PRIx64", rc %d length %u errno %d\n",pos,rc,o.length,errno);close(s);close(fd);return 10;}
        }
        crc=crc_update(crc,block,sizeof(block));
        if(send_all(s,block,sizeof(block))<0){perror("send payload");close(s);close(fd);return 11;}
        sent+=sizeof(block);
    }
    crc^=0xffffffffU;unsigned char trailer[20];memcpy(trailer,"ENDRAW1\n",8);be64(trailer+8,sent);uint32_t network_crc=htonl(crc);memcpy(trailer+16,&network_crc,4);
    if(send_all(s,trailer,sizeof(trailer))<0){close(s);close(fd);return 12;}
    shutdown(s,SHUT_WR);close(s);close(fd);
    printf("{\"index\":%u,\"raw_bytes\":%"PRIu64",\"crc32\":\"%08"PRIx32"\",\"bad_blocks\":%u}\n",index,sent,crc,bad_count);
    return 0;
}
