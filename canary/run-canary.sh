#!/bin/sh
# QEMU-half canary: compile the guest payload, boot it under QEMU on
# this VM, capture the serial console, assert the guest markers.
# (The QNX half needs the myQNX-licensed SDP + QSTI — docs/CANARY.md.)
set -e
cd "$(dirname "$0")"

QEMU="${QEMU:-$HOME/workspace/tools/qemu}"
KERNEL=vmlinuz-virt
KERNEL_URL=https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/netboot/vmlinuz-virt

[ -f "$KERNEL" ] || curl -sSL -o "$KERNEL" "$KERNEL_URL"
gcc -static -O2 -o guest-root/init init.c
python3 make_initramfs.py guest-root/init initramfs-canary.gz

timeout 150 "$QEMU" -machine pc -cpu max -m 256 -smp 1 \
  -kernel "$KERNEL" -initrd initramfs-canary.gz \
  -append "console=ttyS0 panic=-1" \
  -display none -serial file:canary-boot.log -monitor none -no-reboot

grep -q "CANARY-GUEST-HELLO" canary-boot.log
grep -q "CANARY-GUEST-DONE" canary-boot.log
echo "CANARY (QEMU half): GREEN — guest booted, payload ran as PID 1, markers captured."
