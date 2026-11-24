/* Canary guest payload: runs as PID 1 in the QEMU guest.
 * Prints a marker + guest uname to the console, then powers off.
 * This is the QEMU-half proof payload (Linux guest standing in for the
 * gated QNX target); it makes no claim about QNX. */
#include <stdio.h>
#include <sys/utsname.h>
#include <sys/reboot.h>
#include <unistd.h>

int main(void) {
    struct utsname u;
    printf("CANARY-GUEST-HELLO: guest userspace alive (PID 1)\n");
    if (uname(&u) == 0) {
        printf("CANARY-GUEST-UNAME: %s %s %s %s\n", u.sysname, u.release, u.version, u.machine);
    }
    printf("CANARY-GUEST-DONE\n");
    fflush(stdout);
    sync();
    reboot(RB_POWER_OFF);
    return 0;
}
