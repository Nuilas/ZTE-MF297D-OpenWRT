/* Read-only MTD capability probe. No flash write/erase ioctls exist here. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

struct mtd_info_user {
    uint8_t type;
    uint32_t flags, size, erasesize, writesize, oobsize;
    uint64_t padding;
};
struct mtd_oob_buf64 {
    uint64_t start;
    uint32_t pad, length;
    uint64_t usr_ptr;
};
struct mtd_oob_buf { uint32_t start, length; unsigned char *ptr; };
#define MEMGETINFO _IOR('M', 1, struct mtd_info_user)
#define MEMREADOOB _IOWR('M', 4, struct mtd_oob_buf)
#define MEMREADOOB64 _IOWR('M', 22, struct mtd_oob_buf64)
#define MTDFILEMODE _IO('M', 19)
_Static_assert(sizeof(struct mtd_info_user) == 32, "MTD ABI mismatch");
_Static_assert(sizeof(struct mtd_oob_buf64) == 24, "OOB ABI mismatch");

static void hex(const unsigned char *p, size_t n) {
    for (size_t i=0; i<n; ++i) printf("%02x", p[i]);
}
static void oob(int fd, unsigned page, const struct mtd_info_user *info,
                const char *mode) {
    unsigned char buf[4096]; memset(buf, 0xa5, sizeof(buf));
    struct mtd_oob_buf64 b = {
        .start = (uint64_t)page * info->writesize,
        .length = info->oobsize, .usr_ptr = (uintptr_t)buf
    };
    errno=0; int rc=ioctl(fd,MEMREADOOB64,&b), error=errno;
    printf("{\"mode\":\"%s\",\"page\":%u,\"api\":\"MEMREADOOB64\",\"rc\":%d,\"errno\":%d,\"length\":%u,\"hex\":\"",mode,page,rc,error,b.length);
    if (rc==0 && b.length<=sizeof(buf)) hex(buf,b.length);
    printf("\"}\n");
    if (rc<0 && (error==ENOTTY || error==EINVAL || error==EOPNOTSUPP)) {
        memset(buf,0xa5,sizeof(buf));
        struct mtd_oob_buf old = {.start=page*info->writesize,
            .length=info->oobsize,.ptr=buf};
        errno=0; rc=ioctl(fd,MEMREADOOB,&old); error=errno;
        printf("{\"mode\":\"%s\",\"page\":%u,\"api\":\"MEMREADOOB\",\"rc\":%d,\"errno\":%d,\"length\":%u,\"hex\":\"",mode,page,rc,error,old.length);
        if (rc==0 && old.length<=sizeof(buf)) hex(buf,old.length);
        printf("\"}\n");
    }
}
int main(int argc,char **argv) {
    if (argc!=2) { fprintf(stderr,"Usage: oob-probe /dev/mtdNro (N=0..24)\n"); return 2; }
    unsigned n; char tail;
    if(sscanf(argv[1],"/dev/mtd%uro%c",&n,&tail)!=1 || n>24) return 2;
    char expected[32]; snprintf(expected,sizeof(expected),"/dev/mtd%uro",n);
    if(strcmp(expected,argv[1])) return 2;
    int fd=open(argv[1],O_RDONLY|O_CLOEXEC);
    if(fd<0) { perror("open readonly MTD"); return 3; }
    struct mtd_info_user info;
    if(ioctl(fd,MEMGETINFO,&info)<0) { perror("MEMGETINFO"); close(fd); return 4; }
    printf("{\"device\":\"%s\",\"type\":%u,\"size\":%u,\"erase\":%u,\"page\":%u,\"oob\":%u,\"readonly\":true}\n",argv[1],info.type,info.size,info.erasesize,info.writesize,info.oobsize);
    if(!info.writesize || !info.oobsize || info.oobsize>4096 || info.writesize>16384) { close(fd); return 5; }
    unsigned char data[16384];
    for(int raw=0;raw<2;++raw) {
        if(raw) {
            errno=0; int rc=ioctl(fd,MTDFILEMODE,3); int error=errno;
            printf("{\"raw_mode_rc\":%d,\"errno\":%d}\n",rc,error);
            if(rc<0) break;
        }
        const char *mode=raw?"raw":"normal";
        errno=0; ssize_t got=pread(fd,data,info.writesize,0); int error=errno;
        printf("{\"mode\":\"%s\",\"data_read\":%ld,\"errno\":%d,\"prefix\":\"",mode,(long)got,error);
        if(got>0) hex(data,got>64?64:(size_t)got);
        printf("\"}\n");
        oob(fd,0,&info,mode); oob(fd,1,&info,mode);
    }
    close(fd); return 0;
}
