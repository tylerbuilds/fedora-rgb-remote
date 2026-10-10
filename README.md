# Fedora RGB remote

A small private web remote for motherboard-connected PC lights: on/off, custom
colour, nine colour presets, cycle colours and Rainbow wave. Python standard
library server with systemd restart/watchdog support.

## Supported hardware

This version targets the **MSI MS-7D75 Mystic Light USB controller (1462:7d75)**,
used by the MAG B650 TOMAHAWK WIFI. It is intentionally specific; it does not
auto-detect other motherboard families. RAM, GPU and separate hubs are excluded.
RAM control code and RAM research dumps are not included.

On uses static colour at 40% brightness; Off sends static black. ARGB headers
use one virtual LED for uniform colour. Rainbow wave selects that effect; it
does not restore an exact previous appearance. Physical coverage depends on
what is connected to the motherboard headers.

## Prepare the runtime

Dependencies: Python 3, bubblewrap, rpm2cpio, cpio and the shared libraries
required by the Fedora OpenRGB package. On Fedora 43 the packaging tools can
be installed with `sudo dnf install bubblewrap rpm cpio`.

Obtain the Fedora-signed RPM through a trusted Fedora package source:
`openrgb-1.0~rc2-3.20260126git74cbdcc.fc43.x86_64.rpm`.
This project deliberately pins that revision; other versions are refused.
The binary and package are not redistributed here. Verify its signature using
Fedora's package tooling, then run:

```sh
python3 prepare-runtime.py /path/to/openrgb-1.0~rc2-3.20260126git74cbdcc.fc43.x86_64.rpm
RGB_HOST=127.0.0.1 python3 server.py
```

Open `http://127.0.0.1:8769/`. Preparation extracts only the binary and sends no
hardware commands. The binary is hash-checked again before each lighting command.
The existing desktop session must have permission to the matching hidraw node.
No root access, global device permission changes or driver unbinding are required.

For remote access, set `RGB_HOST` to the PC's own Tailscale IPv4 address and
connect through your tailnet. `RGB_PORT` defaults to 8769. Binding is restricted
to loopback or the Tailscale IPv4 range. Do not expose this server through port
forwarding, a public reverse proxy, Tailscale Funnel or a public tunnel.
Tailnet access rules determine who can control the lights; there is no separate
account/password system. Any process/user permitted to access this page can
obtain its CSRF token and operate it.

## Start after login/restart

Create `~/.config/fedora-rgb-remote/local.env` outside the repository, with your
chosen `RGB_HOST` and `RGB_PORT`. Replace `@PROJECT@` in
`fedora-rgb-remote.service.in` with this checkout's absolute path, save it as
`~/.config/systemd/user/fedora-rgb-remote.service`, then run:

```sh
systemctl --user daemon-reload
systemctl --user enable --now fedora-rgb-remote.service
```

Paths with spaces require systemd quoting. Run one service instance per
controller. User lingering can start the web server before login, but controller
permissions may still depend on the desktop session. No lighting command is
sent on startup: only the last successfully selected colour is remembered.
Service restart policy retries if the bind address is not yet available.

## Hardware and access boundaries

Every OpenRGB subprocess runs with an isolated `/dev`, exposing only one matching
MSI USB controller, no I2C/SMBus nodes, no network and a read-only host filesystem
except its local configuration directory. The detector list enables only MSI
Mystic Light MS_7D75. This removes access to RAM controllers from the subprocess;
it does not promise zero risk from the supported USB lighting protocol.

The web API checks exact Host and Origin, a per-process CSRF token, action,
content type, body size and colour. These checks prevent common cross-origin
requests; they do not replace the private network trust boundary. The service
is a small trusted-network tool, not a public internet server.

## Verification and privacy

```sh
python3 -m unittest discover -s tests -v
```

Tests mock hardware commands and exercise request validation and command
boundaries; they do not touch lights. The originating private installation's
controller commands and restart/watchdog recovery were exercised, but this
sanitised checkout has not been deployed to hardware or tested through a reboot.

Only source, generic detector names and documentation are published. Runtime
binaries, device profiles, local addresses/settings, SPD dumps, research and
state files are ignored and excluded. MIT covers this project's code;
OpenRGB is separately licensed by its upstream project.

Protocol reference: [OpenRGB MSI 185-byte controller source](https://github.com/CalcProgrammer1/OpenRGB/blob/74cbdcc/Controllers/MSIMysticLightController/MSIMysticLight185Controller/RGBController_MSIMysticLight185.cpp).
