/* Exactly one write() to the root-only RAM handoff control file.
 * No shell printf buffering; no flash or reboot environment access. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv) {
    if(argc!=2 || (strcmp(argv[1],"--check") && strcmp(argv[1],"--execute")))return 2;
    static const char check[]="CHECK\n";
    static const char execute[]="MF297D_EXECUTE_RAM_ONLY\n";
    int real=!strcmp(argv[1],"--execute");
    const char *data=real?execute:check;
    size_t length=real?sizeof(execute)-1:sizeof(check)-1;
    int fd=open("/proc/mf297d_ramboot",O_WRONLY|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0){perror("RAM control open");return 3;}
    /* Deliberately do not retry or split: the guard requires one exact request. */
    ssize_t written=write(fd,data,length);int error=errno;close(fd);
    fprintf(stderr,"RAM_CONTROL_RETURN bytes=%ld requested=%u errno=%d\n",(long)written,(unsigned)length,error);
    return written<0?111:112;
}
