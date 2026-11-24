# Real-QNX evidence — QNX 8.0 target boot, captured 2026-11-21

**Verdict: the full pipeline is proven on the real target OS.**
Install QNX SDP 8.0 → cross-compile the payload with `qcc` → build the
QEMU system image with `mkqnximage` → boot under QEMU → payload runs
in QNX userspace → console captured → qnxtrace gates the result.

## Environment

- Host: Ubuntu 24.04 x86_64 VM, no /dev/kvm (TCG emulation), QEMU 8.2.2
  (user-space install).
- SDP: QNX Software Development Platform 8.0, QNX Everywhere
  non-commercial license (myQNX), installed at `~/qnx800`.
- Image: `mkqnximage --type=qemu` project in `imgbuild/`; local
  snippets place the payload at `/system/bin/qnx-payload` and run it
  at the end of startup.
- Boot: `-machine pc -cpu max -m 1024 -smp 1`, serial console to file.

## Evidence (verbatim from canary/canary-qnx-boot.log)

The capture is 31 lines: the QSTI startup script starting slogger2,
PCI services, filesystems, networking, sshd, misc — then the payload:

```
CANARY-GUEST-HELLO: QNX target userspace alive (pid 274450)
CANARY-GUEST-UNAME: QNX 8.0.0 2026/10/30-09:10:05EDT x86pc
CANARY-GUEST-DONE

To exit QEMU, type <ctrl>a x

Process count:21
Startup complete
QNX noname 8.0.0 2026/10/30-09:10:05EDT x86pc x86_64
```

And the finding qnxtrace exists for — three lines earlier in the
same boot:

```
---> Starting sshd
Memory fault (core dumped)
```

The stock QNX 8.0 QEMU image's sshd crashes during startup on this
configuration. The boot still completes and every success marker
fires. A marker-only check calls this boot healthy; qnxtrace names
the crash, attributes it to sshd (the service whose start line
precedes it), and reports it as a crash warning — or a hard failure
under `--strict`:

```
$ qnxtrace check --target qnx --log canary/canary-qnx-boot.log \
    --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
qnxtrace health report: PASS
  events parsed: 31
  markers seen: CANARY-GUEST-HELLO, CANARY-GUEST-DONE
  clean exit: yes
  process crash warnings (not fatal; use --strict to fail):
    - process crash (service: sshd): Memory fault (core dumped)

$ qnxtrace check --target qnx --strict ...   # exit code 1
qnxtrace health report: FAIL
  ...
  reasons:
    - 1 process crash(es) in log (strict mode)
```

## Payload v2

`canary/qnx-payload.c` (v2) keeps the markers and adds:

- **slog2 structured logging** — registers its own `qnxtrace` buffer
  set (`slog2_register`) and writes INFO telemetry records plus a
  deliberate WARNING severity probe (`slog2f`). The image's startup
  snippet runs `slog2info` right after the payload so the structured
  stream lands in the same console capture, between
  `QNXT:SLOG2INFO-BEGIN` / `QNXT:SLOG2INFO-END` markers that the
  adapter keys on.
- **System-page telemetry** — `SYSPAGE_ENTRY(qtime)->cycles_per_sec`,
  `SYSPAGE_ENTRY(cpuinfo)`, `_syspage_ptr->num_cpu`, printed as a
  `QNXT:TELEMETRY` line.
- **ClockCycles() timing** — the microkernel cycle counter brackets a
  self-test (including a `/dev/slog` liveness check) and prints
  elapsed microseconds as `QNXT:SELFTEST`.

Build (verified 2026-11-22, compiles clean against SDP 8.0):

```sh
. ~/qnx800/qnxsdp-env.sh
qcc -V gcc_ntox86_64 -O2 -Wall -o canary/qnx-payload canary/qnx-payload.c -lslog2
# ELF 64-bit LSB pie executable, x86-64, QNX, interpreter /usr/lib/ldqnx-64.so.2
```

## Rebuild + recapture (the image step)

```sh
cd imgbuild && mkqnximage --type=qemu --noprompt && cd ..
~/workspace/tools/qemu -machine pc -cpu max -m 1024 -smp 1 \
  -drive file=imgbuild/output/disk-qemu,format=raw,if=ide \
  -serial file:canary/canary-qnx-boot.log
```

The v1 capture above was produced by exactly this route. Rebuilding
with payload v2 additionally lands the `QNXT:` telemetry lines and
the slog2info section in the capture; the adapter parses both today
(console half verified against the real v1 capture; the slog2
section parser is covered by unit tests using the slog2info output
shapes documented in the SDP 8.0 utilities reference).
