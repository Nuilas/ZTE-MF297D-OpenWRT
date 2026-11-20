/* Fetch whitelisted files only into /tmp tmpfs. No device/flash access. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/time.h>
#include <unistd.h>
static int exact(int fd,void *data,size_t n) {
    unsigned char *p=data;
    while(n){ssize_t r=recv(fd,p,n,0);if(r<0 && errno==EINTR)continue;if(r<=0)return -1;p+=r;n-=r;}return 0;
}
int main(int argc,char **argv) {
    if(argc!=3 || strlen(argv[2])!=32 || strspn(argv[2],"0123456789abcdef")!=32)return 2;
    const char *target=0;
    if(!strcmp(argv[1],"Image"))target="/tmp/mf297d-Image";
    if(!strcmp(argv[1],"dtb"))target="/tmp/mf297d-ram.dtb";
    if(!strcmp(argv[1],"initrd"))target="/tmp/mf297d-initramfs.cpio";
    if(!strcmp(argv[1],"prepare"))target="/tmp/mf297d_ramboot.ko";
    if(!strcmp(argv[1],"execute"))target="/tmp/mf297d_ramboot_exec.ko";
    if(!target)return 2;
    struct statfs fs;if(statfs("/tmp",&fs) || fs.f_type!=0x01021994){fprintf(stderr,"/tmp must be tmpfs\n");return 3;}
    struct stat info;if(lstat(target,&info)==0 || errno!=ENOENT){fprintf(stderr,"Target already exists or cannot be checked\n");return 4;}
    char temp[180];snprintf(temp,sizeof(temp),"%s.%s.partial",target,argv[2]);
    int fd=open(temp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0){perror("RAM create");return 4;}
    int s=socket(AF_INET,SOCK_STREAM,0);if(s<0){close(fd);unlink(temp);return 5;}
    struct timeval timeout={.tv_sec=45};setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    struct sockaddr_in peer={.sin_family=AF_INET,.sin_port=htons(18869)};inet_pton(AF_INET,"192.168.1.2",&peer.sin_addr);
    int error=0;
    if(connect(s,(struct sockaddr*)&peer,sizeof(peer))){perror("connect");error=6;goto done;}
    char line[160];int n=snprintf(line,sizeof(line),"{\"token\":\"%s\",\"name\":\"%s\"}\n",argv[2],argv[1]);
    if(send(s,line,(size_t)n,MSG_NOSIGNAL)!=n){error=6;goto done;}
    unsigned char h[8];if(exact(s,h,8)){error=7;goto done;}
    uint64_t length=0;for(int i=0;i<8;i++)length=(length<<8)|h[i];
    if(!length || length>32*1024*1024){error=7;goto done;}
    uint64_t received=0;unsigned char data[65536];
    while(received<length){size_t want=(length-received)>sizeof(data)?sizeof(data):(size_t)(length-received);ssize_t got=recv(s,data,want,0);if(got<=0){error=8;goto done;}ssize_t off=0;while(off<got){ssize_t written=write(fd,data+off,(size_t)(got-off));if(written<=0){error=9;goto done;}off+=written;}received+=(uint64_t)got;}
    if(recv(s,data,1,0)!=0){error=8;goto done;}
    if(fsync(fd)){error=9;goto done;}
    if(link(temp,target)){perror("No-overwrite RAM install");error=10;goto done;}
    printf("RAM_FETCH_OK %s %llu\n",argv[1],(unsigned long long)received);
done:
    close(s);close(fd);unlink(temp);return error;
}
