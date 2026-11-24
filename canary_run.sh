#!/bin/sh
# canary_run.sh — full QNX canary, staged end to end (2026-11-21).
#
# Phase 0 (runnable NOW, no SDP): re-proves the QEMU half.
# Phase 1 (BLOCKED): install QNX Software Center from the on-disk
#   installer. The installer content failed an automated
#   execution-risk check in this environment; an agent must not run
#   it without Don's explicit go-ahead. Command below is the official
#   unattended form from QNX's own documentation (running it accepts
#   the installer EULA automatically).
# Phases 2-4 (SDP-DEPENDENT): activation, SDP 8.0 + QEMU quickstart
#   install, payload build, real-QNX boot + marker capture. These
#   fire the moment Phase 1 lands.
#
# Usage: sh canary_run.sh [phase]   (default: 0)
set -e
cd "$(dirname "$0")"
ROOT="$PWD"
QSC_DIR="${QSC_DIR:-$HOME/qnxinstall/qnxsoftwarecenter}"
SDP_DIR="${SDP_DIR:-$HOME/qnx800}"
PHASE="${1:-0}"

phase0() {
  echo "== Phase 0: QEMU-half canary (Alpine stand-in guest) =="
  sh canary/run-canary.sh
}

phase1() {
  echo "== Phase 1: install QNX Software Center 2.0.4 (unattended) =="
  echo "!! Requires Don's explicit approval to run the on-disk installer."
  # Official unattended form (QNX docs, "Unattended installation on
  # Linux or macOS"): installs into ~/qnxinstall/qnxsoftwarecenter/
  "$ROOT/qnx-setup-linux.run" force-override disable-auto-start \
    agree-to-license-terms "$HOME/qnxinstall"
  "$QSC_DIR/qnxsoftwarecenter_clt" -version
  echo "Phase 1 done: QNX Software Center CLI verified."
}

phase2() {
  echo "== Phase 2 (SDP-DEPENDENT): activate Don's SDP 8.0 license =="
  CLT="$QSC_DIR/qnxsoftwarecenter_clt"
  [ -x "$CLT" ] || { echo "QSC not installed — run phase 1 first"; exit 1; }
  if [ -n "$QNX_LICENSE_KEY" ]; then
    # Preferred route: license KEY only, no password on this host.
    # Key string is read from the signed-in myQNX portal:
    #   qnx.com -> account profile -> Registered Products ->
    #   QNX SDP 8.0 entry -> license key / License Certificate.
    "$CLT" -addLicenseKey "$QNX_LICENSE_KEY" -listLicenseKeys
  elif [ -n "$MYQNX_USER" ] && [ -n "$MYQNX_PASSWORD" ]; then
    # Credential route: Don's account holds exactly one deployed
    # license, so -activateAll is sufficient (no key needed).
    "$CLT" -syncLicenseKeys -myqnx.user="$MYQNX_USER" \
      -myqnx.password="$MYQNX_PASSWORD" -activateAll -listLicenseKeys
  else
    echo "Set QNX_LICENSE_KEY (portal route) or MYQNX_USER/MYQNX_PASSWORD."
    exit 1
  fi
  echo "Phase 2 done: license activated."
  # Fully-offline fallback (if activation above cannot reach qnx.com):
  #   qlicense -userEmail don@lifeofmorr.com -generateManualActivationPromptKey "$QNX_LICENSE_KEY"
  #   -> enter the prompt key on the myQNX manual-activation page in
  #      the signed-in browser -> response key ->
  #   qlicense -userEmail don@lifeofmorr.com -manualActivationCode <response_key>
  # (qlicense ships with the SDP; run after phase 3 with qnxsdp-env sourced.
  #  Note: a valid unactivated key carries a 7-day grace period.)
}

phase3() {
  echo "== Phase 3 (SDP-DEPENDENT): install SDP 8.0 + QEMU quickstart =="
  CLT="$QSC_DIR/qnxsoftwarecenter_clt"
  [ -x "$CLT" ] || { echo "QSC not installed — run phase 1 first"; exit 1; }
  : "${MYQNX_USER:?set MYQNX_USER}"; : "${MYQNX_PASSWORD:?set MYQNX_PASSWORD}"
  "$CLT" -mirror -myqnx.user="$MYQNX_USER" -myqnx.password="$MYQNX_PASSWORD"
  "$CLT" -cleanInstall -destination "$SDP_DIR" \
    -installBaseline com.qnx.qnx800 \
    -myqnx.user="$MYQNX_USER" -myqnx.password="$MYQNX_PASSWORD"
  # QSTI for QEMU (SDP 8.0.5): produces $SDP_DIR/images/qemu
  "$CLT" -destination "$SDP_DIR" \
    -i com.qnx.qnx800.quickstart.qemu \
    -myqnx.user="$MYQNX_USER" -myqnx.password="$MYQNX_PASSWORD"
  "$CLT" -destination "$SDP_DIR" -verifyInstallation
  echo "Phase 3 done: SDP 8.0 at $SDP_DIR"
}

phase4() {
  echo "== Phase 4 (SDP-DEPENDENT): build payload, boot REAL QNX, capture markers =="
  [ -d "$SDP_DIR" ] || { echo "SDP not installed — run phase 3 first"; exit 1; }
  . "$SDP_DIR/qnxsdp-env.sh"
  # Build the QNX-native canary payload (x86-64 target).
  qcc -V gcc_ntox86_64 -O2 -o canary/qnx-payload canary/qnx-payload.c -lslog2
  echo "Payload built: $(file canary/qnx-payload 2>/dev/null || echo canary/qnx-payload)"
  # Package/boot via the QSTI for QEMU. First run: verify on the live
  # surface — mkqnximage's generated project lives under
  # $SDP_DIR/images/qemu; copy the payload in per the QSTI readme so
  # it runs at boot, then build the image:
  cd "$SDP_DIR/images/qemu"
  echo "!! FIRST-RUN CHECK: place $ROOT/canary/qnx-payload into the QSTI"
  echo "   image per its readme (startup script), then: mkqnximage"
  mkqnximage
  # Boot with REDUCED resources (this VM: ~8 GB RAM, TCG, no KVM).
  # mkqnximage --run uses the SDP's QEMU + Developer-Desktop defaults
  # (too heavy here); prefer booting the produced image with the
  # project user-space QEMU at -m 1024 -smp 1, serial to file:
  echo "!! FIRST-RUN CHECK: boot the mkqnximage output with"
  echo "   $HOME/workspace/tools/qemu -m 1024 -smp 1 -display none"
  echo "   -serial file:$ROOT/canary/canary-qnx-boot.log -monitor none -no-reboot"
  echo "   (exact image args from the QSTI readme), timeout 300."
  cd "$ROOT"
  grep -q "CANARY-GUEST-HELLO" canary/canary-qnx-boot.log
  grep -q "CANARY-GUEST-DONE" canary/canary-qnx-boot.log
  PYTHONPATH=src python3 -m qnxtrace.cli check \
    --log canary/canary-qnx-boot.log \
    --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE
  echo "CANARY (QNX half): GREEN — real QNX kernel booted, markers captured."
}

case "$PHASE" in
  0) phase0 ;;
  1) phase1 ;;
  2) phase2 ;;
  3) phase3 ;;
  4) phase4 ;;
  all) phase0; phase1; phase2; phase3; phase4 ;;
  *) echo "usage: sh canary_run.sh [0|1|2|3|4|all]"; exit 2 ;;
esac
