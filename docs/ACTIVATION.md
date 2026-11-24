# QNX activation routes — researched from official QNX docs, 2026-11-21

Account: don@lifeofmorr.com (myQNX). Holds ONE deployed license:
QNX SDP 8.0, perpetual, non-commercial (registered Nov 12, 2026).

## The blocker in front of all of this

The on-disk installer `qnx-setup-linux.run` (QNX Software Center
2.0.4) failed an automated execution-risk check in the agent
environment. Agents must not run/extract/install it without Don's
explicit go-ahead. Once Don approves, everything below is scripted
in `../canary_run.sh` (phases 1–4).

## Install (phase 1, official unattended form)

```
~/workspace/opportunities/qnx/qnx-setup-linux.run \
  force-override disable-auto-start agree-to-license-terms ~/qnxinstall
```
Installs the Software Center into `~/qnxinstall/qnxsoftwarecenter/`;
CLI is `qnxsoftwarecenter_clt` in that directory. (Running the
installer with `agree-to-license-terms` accepts the EULA
automatically — QNX's own doc warns of exactly this.)

## Activation — three routes, in preference order

### Route A — license KEY only (no password ever touches this VM) ⭐
1. In the signed-in browser: qnx.com → sign in → **account profile**
   (https://www.qnx.com/account/) → **Registered Products** section →
   the **QNX SDP 8.0** entry shows its **license key** (also on the
   product's License Certificate). Copy the key string.
2. Hand the key string to the agent (it is a product key, not a
   credential for the account).
3. Agent runs: `qnxsoftwarecenter_clt -addLicenseKey <key> -listLicenseKeys`
   (adds + activates; documented to work for offline QSC use too —
   activation completes over this VM's normal internet connection).

### Route B — CLI credential sync (password required on the VM)
```
qnxsoftwarecenter_clt -syncLicenseKeys -myqnx.user=don@lifeofmorr.com \
  -myqnx.password=<pw> -activateAll -listLicenseKeys
```
`-activateAll` suffices because exactly one license is deployed to
the account. Needs Don's unified password entered by whoever runs
it — the agent does not hold it and must not ask for it in chat.

### Route C — fully offline manual activation (post-SDP, via qlicense)
```
qlicense -userEmail don@lifeofmorr.com -generateManualActivationPromptKey <key>
# -> take prompt key to the manual-activation page in the signed-in
#    myQNX portal -> receive response key ->
qlicense -userEmail don@lifeofmorr.com -manualActivationCode <response_key>
```
Also: a valid but unactivated key is treated as temporarily
activated for a **7-day grace period**, so Route C never blocks a
same-week canary. QSC also has an `-offline` mode with packages
imported into its dropins directory if package download ever needs
to go offline.

## SDP 8.0 install (phase 3, after activation)
```
qnxsoftwarecenter_clt -mirror -myqnx.user=... -myqnx.password=...
qnxsoftwarecenter_clt -cleanInstall -destination ~/qnx800 \
  -installBaseline com.qnx.qnx800 -myqnx.user=... -myqnx.password=...
qnxsoftwarecenter_clt -destination ~/qnx800 \
  -i com.qnx.qnx800.quickstart.qemu -myqnx.user=... -myqnx.password=...
```
QSTI for QEMU lands at `~/qnx800/images/qemu`; payload build + boot
+ marker capture are phase 4 of `../canary_run.sh` (reduced
resources: -m 1024 -smp 1, TCG, no KVM on this VM).

Sources (official QNX documentation, read 2026-11-21):
- "Unattended installation on Linux or macOS" — QSC docs
  (create_headless_installation_linux_macos)
- "Using the QNX Software Center Command Line" — QSC User's Guide
  (commandline_qsc: -myqnx.user/-myqnx.password, -syncLicenseKeys,
  -addLicenseKey, -offline)
- `qlicense` utility reference — QNX SDP 8.0 Utilities Reference
  (manual activation prompt/response flow, 7-day grace)
- "Manage Your Product Licenses" — QSC User's Guide (activation and
  manual deactivation from the myQNX profile)
