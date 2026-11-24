/* qnxtrace canary payload v2 — runs ON the real QNX 8.0 target.
 *
 * A normal QNX user program (built with the SDP 8.0 toolchain, run
 * inside the QEMU system image at boot) that does three jobs:
 *
 *   1. Prints the CANARY-GUEST-* boot-health markers the host tool
 *      (qnxtrace) asserts on the captured console log.
 *   2. Emits QNXT: telemetry lines read from the QNX system page
 *      (qtime / cpuinfo entries) and timed with ClockCycles() — the
 *      microkernel's own cycle counter.
 *   3. Writes structured records through the QNX slog2 logging API
 *      (slog2_register / slog2f) into its own buffer set, so the
 *      startup script can dump them with slog2info right after the
 *      payload exits and qnxtrace can parse the structured stream
 *      alongside the console stream.
 *
 * Everything printed goes to the serial console, which the host
 * captures to a file (see docs/QNX-BOOT.md).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/utsname.h>
#include <sys/syspage.h>
#include <sys/neutrino.h>
#include <sys/slog2.h>

/* One slog2 buffer set, one buffer, registered under our own name so
 * slog2info output is attributable to this program. */
static slog2_buffer_t slog_handles[1];

static int slog2_setup(void) {
    slog2_buffer_set_config_t config;
    memset(&config, 0, sizeof(config));
    config.num_buffers = 1;
    config.buffer_set_name = "qnxtrace";
    config.verbosity_level = SLOG2_DEBUG2; /* log every severity we emit */
    config.buffer_config[0].buffer_name = "boot";
    config.buffer_config[0].num_pages = 4;
    if (slog2_register(&config, slog_handles, 0) != 0) {
        return -1;
    }
    return 0;
}

int main(void) {
    const uint64_t t_start = ClockCycles();
    struct utsname u;
    int have_uname = (uname(&u) == 0);

    printf("CANARY-GUEST-HELLO: QNX target userspace alive (pid %d)\n",
           getpid());
    if (have_uname) {
        printf("CANARY-GUEST-UNAME: %s %s %s %s\n",
               u.sysname, u.release, u.version, u.machine);
    }

    /* --- System-page telemetry (QNX-specific) -------------------- */
    const unsigned long long cycles_per_sec =
        (unsigned long long)SYSPAGE_ENTRY(qtime)->cycles_per_sec;
    const unsigned num_cpu = (unsigned)_syspage_ptr->num_cpu;
    const unsigned long cpu_speed =
        (unsigned long)SYSPAGE_ENTRY(cpuinfo)[0].speed;

    printf("QNXT:TELEMETRY sysname=%s release=%s num_cpu=%u "
           "cycles_per_sec=%llu cpu0_speed_hz=%lu\n",
           have_uname ? u.sysname : "?", have_uname ? u.release : "?",
           num_cpu, cycles_per_sec, cpu_speed);

    /* --- slog2 structured logging (QNX-specific) ----------------- */
    int slog_ok = (slog2_setup() == 0);
    int slog_records = 0;
    if (slog_ok) {
        if (slog2f(slog_handles[0], 0, SLOG2_INFO,
                   "qnxtrace payload self-test started pid=%d",
                   getpid()) == 0) {
            slog_records++;
        }
        if (slog2f(slog_handles[0], 0, SLOG2_INFO,
                   "telemetry num_cpu=%u cycles_per_sec=%llu",
                   num_cpu, cycles_per_sec) == 0) {
            slog_records++;
        }
        /* Deliberate severity probe: proves WARNING records route
         * through the buffer with their severity intact. Not a fault. */
        if (slog2f(slog_handles[0], 0, SLOG2_WARNING,
                   "self-test severity probe (deliberate, not a fault)") == 0) {
            slog_records++;
        }
    }
    printf("QNXT:SLOG2 status=%s records=%d buffer_set=qnxtrace\n",
           slog_ok ? "ok" : "unavailable", slog_records);

    /* --- Timed self-test ------------------------------------------ */
    /* slogger2 must be up (startup waits for /dev/slog before us). */
    int dev_slog_ok = (access("/dev/slog", F_OK) == 0);
    volatile unsigned long acc = 0;
    for (unsigned long i = 0; i < 1000000UL; i++) {
        acc += i ^ (acc << 1);
    }
    const uint64_t t_end = ClockCycles();
    unsigned long long elapsed_us = 0;
    if (cycles_per_sec > 0) {
        elapsed_us = (unsigned long long)((t_end - t_start) * 1000000ULL /
                                          cycles_per_sec);
    }
    printf("QNXT:SELFTEST dev_slog=%s syspage=ok clock=ok "
           "elapsed_us=%llu checksum=%lu\n",
           dev_slog_ok ? "ok" : "missing", elapsed_us, acc);

    printf("CANARY-GUEST-DONE\n");
    fflush(stdout);
    return 0;
}
