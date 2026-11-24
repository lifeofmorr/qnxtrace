# Canary record — 2026-11-20

> **UPDATE 2026-11-22:** the gate below was cleared the next day.
> The QNX half is GREEN on real QNX 8.0 (SDP installed, payload
> booted on the QNX QEMU target, markers captured) — see
> [QNX-BOOT.md](QNX-BOOT.md). This file remains as the historical
> record of the first proof.

**Verdict: PARTIAL.** QEMU half GREEN (proven below). QNX half GATED
on a human license action (named exactly below). No QNX code has run
on this project yet, and nothing here claims otherwise.

## QEMU half — GREEN (evidence)

Host: this VM, Ubuntu 24.04.5 x86_64, **no /dev/kvm** (TCG emulation).

1. QEMU 8.2.2 installed user-space (Ubuntu debs extracted to
   `~/workspace/tools/qemu-root`, wrapper `~/workspace/tools/qemu`) —
   no system install. `--version` verified; ldd clean.
2. Guest: Alpine Linux 6.6.134-0-virt kernel (official netboot image,
   no license/click) + a static C payload (`canary/init.c`) compiled
   on this VM, packed as initramfs PID 1.
3. Boot captured to `canary/canary-boot.log` (330 lines), QEMU exit 0,
   guest powered itself down. Verbatim from the log:

   ```
   Linux version 6.6.134-0-virt (buildozer@build-3-20-x86_64) ... #1-Alpine SMP PREEMPT_DYNAMIC
   CANARY-GUEST-HELLO: guest userspace alive (PID 1)
   CANARY-GUEST-UNAME: Linux 6.6.134-0-virt ... x86_64
   CANARY-GUEST-DONE
   reboot: Power down
   ```

   Reproduce: `sh canary/run-canary.sh`

This proves the whole canary mechanism on this VM: compile payload →
boot target under QEMU → capture serial console → assert markers —
which is also exactly how qnxtrace consumes target output.

## QNX half — GATED (the exact gate)

The only route to QNX SDP 8.0 + the QEMU target image (verified
2026-11-20 against qnx.software, QNX docs, and community guides —
there is no ungated download):

1. **A human** browses to **qnx.com/getqnx**, creates a **myQNX
   account** (new-account password), submits the **QNX Everywhere
   license form**, and **accepts the QNX Development License —
   Non-Commercial (QDL) terms** for SDP 8.0. (Free; license appears
   in the myQNX profile within ~1 hour.)
2. Agent-side from there: install QNX Software Center, sign in,
   install **QNX SDP 8.0**, then package
   **com.qnx.qnx800.quickstart.qemu** (QSTI for QEMU, SDP 8.0.5) →
   `~/qnx800/images/qemu`; boot via `mkqnximage --run`.
3. Then the real canary: compile hello-world with the SDP toolchain,
   run it on the QNX QEMU target, capture output, and land the QNX
   adapter in `src/qnxtrace/adapters.py` against that real output.

Notes for whoever fires the gate: host OS requirement (Ubuntu
22.04/24.04) is met; QNX docs recommend QEMU 10 (8.2.2 works for the
proof above; revisit if the QSTI objects); the QSTI Developer Desktop
defaults (8 CPU / 4 GB) exceed this VM's free RAM — use the plain
QSTI / reduced `-m`/`-smp` for the canary.
