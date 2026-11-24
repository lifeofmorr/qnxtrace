# Codelab: Add a boot-health gate to your QNX 8.0 QEMU workflow

**Time: ~30 minutes · Level: intermediate · You will:** boot a real
QNX 8.0 target under QEMU, teach a tiny on-target program to report
its own health, and gate the whole thing in CI with a pass/fail check
that catches services which crash *during an otherwise successful
boot*.

## What you need

- A Linux host (Ubuntu 22.04/24.04) with QEMU.
- A free **myQNX account** and the **QNX Everywhere** non-commercial
  license for **QNX SDP 8.0** (qnx.com/getqnx). The license appears
  in your myQNX profile shortly after you accept the terms.
- This repository cloned locally.

## Step 1 — Install the SDP and load the environment

Install QNX Software Center, sign in, and install the QNX SDP 8.0
baseline. Then, in every shell that builds for the target:

```sh
. ~/qnx800/qnxsdp-env.sh
qcc -V gcc_ntox86_64 -version   # sanity: the target toolchain answers
```

## Step 2 — Meet the canary payload

`canary/qnx-payload.c` is a normal QNX user program. At boot it:

1. prints `CANARY-GUEST-HELLO` / `CANARY-GUEST-DONE` markers,
2. reads **system-page** telemetry (`SYSPAGE_ENTRY(qtime)`,
   `SYSPAGE_ENTRY(cpuinfo)`) and times a self-test with
   **ClockCycles()**,
3. writes structured records through the **slog2 API**
   (`slog2_register`, `slog2f`) into its own buffer set.

Build it for the target:

```sh
qcc -V gcc_ntox86_64 -O2 -o canary/qnx-payload canary/qnx-payload.c -lslog2
file canary/qnx-payload   # ELF 64-bit ... QNX ... x86-64
```

> The `-lslog2` matters: slog2 lives in its own library, and the
> linker will tell you so if you forget it.

## Step 3 — Bake the payload into a QEMU system image

`imgbuild/` is an `mkqnximage` project. Two local snippets do the
integration:

- `local/snippets/system_files.custom` adds the payload as
  `bin/qnx-payload`,
- `local/snippets/post_start.custom` runs it at the end of startup,
  then dumps the slog2 buffers with `slog2info` between
  `QNXT:SLOG2INFO-BEGIN` / `QNXT:SLOG2INFO-END` markers.

```sh
cd imgbuild && mkqnximage --type=qemu --noprompt && cd ..
```

## Step 4 — Boot and capture the console

```sh
~/workspace/tools/qemu -machine pc -cpu max -m 1024 -smp 1 \
  -drive file=imgbuild/output/disk-qemu,format=raw,if=ide \
  -serial file:canary/canary-qnx-boot.log
```

The guest stays up by design; stop QEMU after you see
`Startup complete` and the closing banner
(`QNX noname 8.0.0 ... x86_64`).

## Step 5 — Gate the boot with qnxtrace

```sh
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
echo "exit code: $?"
```

On the stock image you should get a PASS — with a catch:

```
qnxtrace health report: PASS
  events parsed: 31
  markers seen: CANARY-GUEST-HELLO, CANARY-GUEST-DONE
  clean exit: yes
  process crash warnings (not fatal; use --strict to fail):
    - process crash (service: sshd): Memory fault (core dumped)
```

**This is the lesson of the codelab.** The stock image's sshd
core-dumps during startup, the boot completes, and every success
marker fires. Marker-grep CI calls this healthy. qnxtrace parses the
console stream (service starts, the closing QNX banner, crash lines)
and the slog2 stream (severity-mapped records), attributes the crash
to the service that started it, and lets *you* pick the policy:

```sh
# crashes fail the gate:
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx --strict \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE   # exit 1

# machine-readable verdict for your pipeline:
PYTHONPATH=src python3 -m qnxtrace.cli check --target qnx --format json \
  --log canary/canary-qnx-boot.log \
  --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
```

## Step 6 — Make it yours

- Add `--expect` markers for *your* application's boot milestones;
  have your app print them (or log them via slog2 with your own
  buffer set — the adapter maps slog2 severities CRITICAL/ERROR to
  failures and WARNING to warnings).
- Run the strict gate on release branches and the relaxed gate on
  developer branches while you burn down known crashes.
- Feed `--format json` into your CI dashboard; the `crashes` array
  is the list your future self will thank you for.

## Troubleshooting

- **`undefined reference to slog2_register`** — you forgot `-lslog2`.
- **No slog2info section in the capture** — the `post_start` snippet
  didn't make it into the image; rebuild with `mkqnximage` after
  editing snippets (they are baked in at image-build time).
- **Networking lines complain in the boot log** (`if_up: tries
  exhausted`) — the plain QEMU config has no usable NIC; harmless
  for boot-health purposes and qnxtrace does not fail on it.
- **sshd crash** — observed on the stock QSTI image under this QEMU
  configuration. It's the codelab's teaching example, not your bug.
