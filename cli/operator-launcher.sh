#!/bin/sh
# One isolated installation; never adopts another profile.
exec /usr/bin/env -i \
 HOME=/home/kali/.local/share/omnis-settings-c-9e51d10/h \
 XDG_CONFIG_HOME=/home/kali/.local/share/omnis-settings-c-9e51d10/c \
 XDG_DATA_HOME=/home/kali/.local/share/omnis-settings-c-9e51d10/d \
 XDG_STATE_HOME=/home/kali/.local/share/omnis-settings-c-9e51d10/s \
 XDG_RUNTIME_DIR=/home/kali/.local/share/omnis-settings-c-9e51d10/r \
 PATH=/home/kali/.local/share/omnis-settings-c-9e51d10/cli/bin:/usr/bin:/bin \
 TMPDIR=/home/kali/.hermes/cache/scratch \
 OMNIS_DESKTOP_HOME="${HOME-}" \
 OMNIS_DESKTOP_XDG_CONFIG_HOME="${XDG_CONFIG_HOME-}" \
 OMNIS_DESKTOP_XDG_DATA_HOME="${XDG_DATA_HOME-}" \
 OMNIS_DESKTOP_XDG_STATE_HOME="${XDG_STATE_HOME-}" \
 OMNIS_DESKTOP_XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR-}" \
 DISPLAY="${DISPLAY-}" \
 WAYLAND_DISPLAY="${WAYLAND_DISPLAY-}" \
 XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP-}" \
 DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS-}" \
 XAUTHORITY="${XAUTHORITY-}" \
 LANG="${LANG-}" \
 /home/kali/.local/share/omnis-settings-c-9e51d10/cli/bin/omnis "$@"
