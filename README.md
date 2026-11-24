# qnxtrace — boot-health CI for QNX 8.0 targets

**QNX Global Hackathon · Developer Tooling & Host Tools · deadline Dec 15, 2026**

qnxtrace answers one question for QNX developers who boot targets in
CI: **"did my QNX target actually boot and behave?"** — and answers it
from evidence, not vibes.

It has two halves:

1. **A host tool** (Linux, Python 3, stdlib only) that ingests a
   captured QNX target console log — including the target's structured
   **slog2** buffer dump — structures it into events, and emits a
   CI-style health verdict: expected markers present, no kernel
   failures, userspace crashes named (not buried), clean startup.
2. **An on-target canary payload** (C, QNX SDP 8.0 toolchain) that runs
   inside the QNX QEMU system image at boot: it prints boot-health
   markers, reads **system-page telemetry** (qtime / cpuinfo) timed
   with **ClockCycles()**, and writes structured records through the
   **slog2 API** for the host tool to parse.

## Why

QEMU target boots in CI produce a wall of console text. A service can
crash on page 1 and the boot still "succeeds." qnxtrace's own first
real QNX capture proves the point: the stock QNX 8.0 QEMU image boots,
our payload runs, every marker fires — and **sshd core-dumps during
startup** (`Memory fault (core dumped)`), invisible to any check that
only greps for success markers. qnxtrace names it, attributes it to
the service that started it, and lets you decide the policy: crash
warnings by default, hard failure with `--strict`.

## Status (honest, 2026-11-22)

- ✅ **Proven end-to-end on real QNX 8.0**: SDP 8.0 installed, payload
  cross-compiled with `qcc`, QEMU system image built with
  `mkqnximage`, booted, console captured — payload markers verified in
  the real QNX 8.0.0 x86_64 boot log. See
  [docs/QNX-BOOT.md](docs/QNX-BOOT.md) and
  `canary/canary-qnx-boot.log`.
- ✅ **QNX adapter implemented against that real capture** (console
  stream + slog2info sections), crash-tier reporting, `--strict`,
  JSON output for CI. 18/18 tests pass, including tests that run
  against the genuine captured QNX boot log.
- ✅ **Payload v2 compiles clean** with the SDP 8.0 toolchain
  (slog2 logging + system-page telemetry + ClockCycles timing).
  Its boot capture is produced by the same proven image-rebuild step
  documented in [docs/QNX-BOOT.md](docs/QNX-BOOT.md).
- ✅ QEMU-half canary (Linux guest stand-in) also proven — the
  mechanism qnxtrace consumes was validated before the QNX license
  landed. See [docs/CANARY.md](docs/CANARY.md).

## Run the host tool

```sh
# tests (stdlib only)
python3 -m unittest discover -s tests -v

# health-check the real captured QNX 8.0 boot log
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE

# same check, strict: a userspace crash during boot fails the gate
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx --strict \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE

# machine-readable verdict for CI
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx --format json \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE

# generic console logs (e.g. the Linux-guest canary)
PYTHONPATH=src python3 -m qnxtrace.cli check \
  --log canary/canary-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
```

Exit code 0 = PASS, 1 = FAIL.

Sample verdict on the real QNX capture:

```
qnxtrace health report: PASS
  events parsed: 31
  markers seen: CANARY-GUEST-HELLO, CANARY-GUEST-DONE
  clean exit: yes
  process crash warnings (not fatal; use --strict to fail):
    - process crash (service: sshd): Memory fault (core dumped)
```

## Build & run the QNX target canary

**Platform**: QNX OS 8.0 (QNX Everywhere, free non-commercial SDP
license) · **Target**: QEMU x86_64 system image (`mkqnximage
--type=qemu`) · **Toolchain**: QNX SDP 8.0 (`qcc`, gcc_ntox86_64).

```sh
# 1. Install QNX SDP 8.0 via QNX Software Center (free myQNX license),
#    then load the environment:
. ~/qnx800/qnxsdp-env.sh

# 2. Cross-compile the payload for the QNX target:
qcc -V gcc_ntox86_64 -O2 -o canary/qnx-payload canary/qnx-payload.c -lslog2

# 3. Rebuild the QEMU system image with the payload baked in
#    (imgbuild/ is an mkqnximage project; its local snippets place the
#    payload in /system/bin and run it at the end of startup, followed
#    by a slog2info dump to the console):
cd imgbuild && mkqnximage --type=qemu --noprompt && cd ..

# 4. Boot the image and capture the serial console:
~/workspace/tools/qemu -machine pc -cpu max -m 1024 -smp 1 \
  -drive file=imgbuild/output/disk-qemu,format=raw,if=ide \
  -serial file:canary/canary-qnx-boot.log
# (the guest stays up by design; stop QEMU after "Startup complete")

# 5. Gate the boot with qnxtrace:
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
```

`canary_run.sh` scripts the whole flow (phases 0–4) on a host with the
SDP installed.

## How QNX is used (evidence map)

| QNX technology | Where | What it does |
|---|---|---|
| QNX SDP 8.0 toolchain (`qcc`) | `canary/qnx-payload.c` build | Cross-compiles the payload for ntox86_64 |
| `mkqnximage` QSTI project | `imgbuild/` | Builds the bootable QEMU system image; local snippets add the payload + startup hook |
| slog2 API (`slog2_register`, `slog2f`) | `canary/qnx-payload.c` | Structured on-target logging into a dedicated `qnxtrace` buffer set |
| `slog2info` | image startup (`post_start` snippet) | Dumps the slog2 buffers to the console for host-side parsing |
| System page (`SYSPAGE_ENTRY(qtime/cpuinfo)`) | `canary/qnx-payload.c` | Target telemetry: cycles/sec, CPU count/speed |
| `ClockCycles()` | `canary/qnx-payload.c` | Microkernel cycle counter timing the boot self-test |
| QNX console/startup format | `src/qnxtrace/adapters.py` | Parser written against real captured QNX 8.0 output |

## Layout

- `src/qnxtrace/` — generic console parser, QNX adapter (console +
  slog2), health report (text + JSON), CLI
- `canary/` — the target canary: payload source (v1 markers + v2
  slog2/syspage), captured boot logs (Linux stand-in + real QNX 8.0),
  initramfs builder for the stand-in guest
- `imgbuild/` — the mkqnximage QEMU project that produces the target
  system image
- `docs/` — CANARY.md (first proof), QNX-BOOT.md (real-QNX evidence +
  rebuild steps), TUTORIAL.md (codelab: add a boot-health gate to your
  QNX CI)
- `tests/` — unit tests, incl. checks against both real captured logs

## License

MIT (see LICENSE). The canary stand-in guest kernel under `canary/`
is an Alpine Linux netboot image (GPL) downloaded for the proof; it
is not part of this project's source and is excluded from the repo
(.gitignore).
