#!/bin/sh
set -eu

DISK="/dev/mmcblk0"
ROOTPART="/dev/mmcblk0p2"
WIFI_IF="mlan0"
COUNTRY_DEFAULT="RO"
DNS1="8.8.8.8"
DNS2="8.8.4.4"

die() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command '$1' is not installed."
}

echo "============================================================"
echo " FRDM-i.MX95 OUT-OF-BOX PROVISIONING v1.3"
echo "============================================================"

[ "$(id -u)" -eq 0 ] || die "Run this script as root."

for c in findmnt lsblk blockdev sfdisk dd sync systemctl ip \
         wpa_supplicant wpa_passphrase wpa_cli udhcpc getent curl \
         resize2fs awk sed grep cut tr date stty readlink mktemp install pgrep kill; do
    need_cmd "$c"
done

echo
echo "=== 1. VALIDATE BOARD / ROOT STORAGE ==="

[ -b "$DISK" ] || die "$DISK does not exist."
[ -b "$ROOTPART" ] || die "$ROOTPART does not exist."

ROOT_SOURCE="$(findmnt -n -o SOURCE /)"
ROOT_SOURCE_REAL="$(readlink -f "$ROOT_SOURCE" 2>/dev/null || true)"
ROOTPART_REAL="$(readlink -f "$ROOTPART" 2>/dev/null || true)"
ROOT_BY_LSBLK="$(lsblk -nrpo NAME,MOUNTPOINT "$DISK" 2>/dev/null | awk '$2=="/"{print $1; exit}')"

ROOT_OK=0
[ "$ROOT_SOURCE" = "$ROOTPART" ] && ROOT_OK=1
[ -n "$ROOT_SOURCE_REAL" ] && [ "$ROOT_SOURCE_REAL" = "$ROOTPART_REAL" ] && ROOT_OK=1
[ "$ROOT_BY_LSBLK" = "$ROOTPART" ] && ROOT_OK=1

[ "$ROOT_OK" -eq 1 ] || die "Root filesystem is not on $ROOTPART (findmnt reports '$ROOT_SOURCE')."

ROOT_FS="$(findmnt -n -o FSTYPE /)"
[ "$ROOT_FS" = "ext4" ] || die "Root filesystem is '$ROOT_FS', expected ext4."

PART_COUNT="$(lsblk -nr -o TYPE "$DISK" | awk '$1=="part"{n++} END{print n+0}')"
[ "$PART_COUNT" -eq 2 ] || die "Expected exactly 2 partitions on $DISK; found $PART_COUNT."

LABEL="$(sfdisk -d "$DISK" 2>/dev/null | awk -F': *' '/^label:/{print $2; exit}')"
[ "$LABEL" = "dos" ] || die "Expected DOS/MBR partition table; found '$LABEL'."

P1_START="$(cat /sys/class/block/mmcblk0p1/start)"
P1_SIZE="$(cat /sys/class/block/mmcblk0p1/size)"
P2_START="$(cat /sys/class/block/mmcblk0p2/start)"
P2_SIZE="$(cat /sys/class/block/mmcblk0p2/size)"
DISK_SECTORS="$(blockdev --getsz "$DISK")"
DISK_BYTES="$(blockdev --getsize64 "$DISK")"

[ "$P1_START" -eq 16384 ] || die "Unexpected p1 start sector: $P1_START (expected 16384)."
[ "$P1_SIZE" -eq 524288 ] || die "Unexpected p1 size: $P1_SIZE sectors (expected 524288)."
[ "$P2_START" -eq 540672 ] || die "Unexpected p2 start sector: $P2_START (expected 540672)."

[ "$DISK_BYTES" -ge 30000000000 ] || die "eMMC is smaller than expected: $DISK_BYTES bytes."
[ "$DISK_BYTES" -le 33000000000 ] || die "eMMC is larger/different than expected: $DISK_BYTES bytes."

echo "Root device:        $ROOTPART"
echo "Root filesystem:    $ROOT_FS"
echo "Partition table:    $LABEL"
echo "eMMC bytes:         $DISK_BYTES"
echo "eMMC sectors:       $DISK_SECTORS"
echo "p2 start sector:    $P2_START"
echo "p2 current sectors: $P2_SIZE"

echo
echo "=== 2. WAIT FOR IW612 / mlan0 ==="

i=0
while [ ! -e "/sys/class/net/$WIFI_IF" ]; do
    i=$((i + 1))
    [ "$i" -lt 30 ] || die "$WIFI_IF did not appear within 30 seconds."
    sleep 1
done

ip link set "$WIFI_IF" up || true
sleep 1

echo "$WIFI_IF is present."

if command -v iw >/dev/null 2>&1; then
    echo
    echo "Nearby SSIDs:"
    iw dev "$WIFI_IF" scan 2>/dev/null \
        | awk -F'SSID: ' '/SSID: /{print $2}' \
        | sed '/^$/d' \
        | sort -u \
        | sed 's/^/  /' || true
fi

echo
echo "=== 3. ENTER WI-FI SETTINGS ==="

printf "SSID: "
IFS= read -r SSID
[ -n "$SSID" ] || die "SSID cannot be empty."

printf "Country code [%s]: " "$COUNTRY_DEFAULT"
IFS= read -r COUNTRY
COUNTRY="${COUNTRY:-$COUNTRY_DEFAULT}"

trap 'stty echo 2>/dev/null || true' EXIT INT TERM
printf "Wi-Fi password: "
stty -echo
IFS= read -r WIFI_PASS
stty echo
printf "\n"
trap - EXIT INT TERM

[ -n "$WIFI_PASS" ] || die "Wi-Fi password cannot be empty."

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="/root/frdm-provision-backup-$STAMP"
mkdir -p "$BACKUP"

echo
echo "=== 4. BACK UP CURRENT CONFIGURATION ==="
echo "Backup directory: $BACKUP"

sfdisk -d "$DISK" >"$BACKUP/mmcblk0-before.sfdisk"
dd if="$DISK" of="$BACKUP/mmcblk0-first-1MiB-before.img" bs=1M count=1 status=none

for f in \
    /etc/connman/main.conf \
    /etc/wpa_supplicant.conf \
    /etc/systemd/system/frdm-wifi.service \
    /etc/systemd/system/frdm-wifi.service.d/10-dns.conf \
    /etc/systemd/system/autowifi.service \
    /usr/local/sbin/frdm-wifi-connect.sh \
    /usr/local/sbin/frdm-dns-config.sh; do
    if [ -e "$f" ]; then
        mkdir -p "$BACKUP$(dirname "$f")"
        cp -a "$f" "$BACKUP$f"
    fi
done

echo "Backups complete."

echo
echo "=== 5. TAKE OWNERSHIP OF WI-FI + CONFIGURE CREDENTIALS ==="

echo "Stopping any previous FRDM provisioner Wi-Fi service..."
systemctl stop frdm-wifi.service >/dev/null 2>&1 || true

if systemctl cat autowifi.service >/dev/null 2>&1; then
    echo "Legacy autowifi.service detected."
    echo "Stopping and disabling it so only one service owns mlan0..."
    systemctl stop autowifi.service || true
    systemctl disable autowifi.service >/dev/null 2>&1 || true
fi

# A well-behaved systemd stop should kill the service cgroup, but clean up
# any residual mlan0-specific processes as a safeguard. Do not touch
# supplicants/DHCP clients for other interfaces.
for pid in $(pgrep -f 'wpa_supplicant.*mlan0' 2>/dev/null || true); do
    kill "$pid" 2>/dev/null || true
done
for pid in $(pgrep -f 'udhcpc.*mlan0' 2>/dev/null || true); do
    kill "$pid" 2>/dev/null || true
done

sleep 1

for pid in $(pgrep -f 'wpa_supplicant.*mlan0' 2>/dev/null || true); do
    kill -9 "$pid" 2>/dev/null || true
done
for pid in $(pgrep -f 'udhcpc.*mlan0' 2>/dev/null || true); do
    kill -9 "$pid" 2>/dev/null || true
done

systemctl reset-failed frdm-wifi.service autowifi.service >/dev/null 2>&1 || true

if pgrep -f 'wpa_supplicant.*mlan0' >/dev/null 2>&1; then
    die "A wpa_supplicant process still owns mlan0 after cleanup."
fi

if pgrep -f 'udhcpc.*mlan0' >/dev/null 2>&1; then
    die "An udhcpc process still owns mlan0 after cleanup."
fi

echo "mlan0 ownership cleanup: PASS"

mkdir -p /usr/local/sbin
mkdir -p /etc/connman
mkdir -p /var/run/wpa_supplicant
mkdir -p /etc/systemd/system/frdm-wifi.service.d
mkdir -p /var/lib/frdm-provision

WPA_TMP="$(mktemp /tmp/frdm-wpa.XXXXXX)"
trap 'rm -f "$WPA_TMP"; stty echo 2>/dev/null || true' EXIT INT TERM

cat >"$WPA_TMP" <<EOF
ctrl_interface=/var/run/wpa_supplicant
ctrl_interface_group=0
update_config=1
country=$COUNTRY
EOF

# This NXP image's wpa_passphrase may try to use tcgetattr when the
# passphrase is piped on stdin.  Supplying it as the documented second
# argument avoids that failure.  The generated plaintext #psk comment is
# stripped before the config is installed.
wpa_passphrase "$SSID" "$WIFI_PASS" \
    | sed '/^[[:space:]]*#psk=/d' \
    >> "$WPA_TMP"

unset WIFI_PASS

PSK_COUNT="$(grep -c '^[[:space:]]*psk=' "$WPA_TMP" 2>/dev/null || true)"
NET_COUNT="$(grep -c '^[[:space:]]*network={' "$WPA_TMP" 2>/dev/null || true)"

[ "$PSK_COUNT" -eq 1 ] || die "Failed to generate exactly one WPA PSK line."
[ "$NET_COUNT" -eq 1 ] || die "Failed to generate exactly one network block."

install -m 600 "$WPA_TMP" /etc/wpa_supplicant.conf
rm -f "$WPA_TMP"
trap - EXIT INT TERM

cat >/etc/connman/main.conf <<'EOF'
[General]
NetworkInterfaceBlacklist=vmnet,vboxnet,virbr,ifb,ve-,vb-,ham,veth,mlan0,uap0,wfd0
EOF

cat >/usr/local/sbin/frdm-wifi-connect.sh <<'EOF'
#!/bin/sh
set -eu

IFACE="mlan0"
CONF="/etc/wpa_supplicant.conf"

echo "[wifi] Waiting for ${IFACE}..."

i=0
while [ ! -e "/sys/class/net/${IFACE}" ]; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "[wifi] ERROR: ${IFACE} did not appear"
        exit 1
    fi
    sleep 1
done

echo "[wifi] ${IFACE} exists"

mkdir -p /var/run/wpa_supplicant
ip link set "${IFACE}" up

wpa_cli -i "${IFACE}" terminate >/dev/null 2>&1 || true
sleep 1
rm -f "/var/run/wpa_supplicant/${IFACE}"

echo "[wifi] Starting wpa_supplicant..."
wpa_supplicant -B -D nl80211 -i "${IFACE}" -c "${CONF}"

echo "[wifi] Waiting for authentication..."

i=0
while :; do
    STATE="$(wpa_cli -i "${IFACE}" status 2>/dev/null | sed -n 's/^wpa_state=//p')"
    echo "[wifi] state=${STATE:-unknown}"

    if [ "${STATE:-}" = "COMPLETED" ]; then
        break
    fi

    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "[wifi] ERROR: authentication timeout"
        exit 1
    fi
    sleep 1
done

echo "[wifi] Authentication complete"

ip addr flush dev "${IFACE}" || true

echo "[wifi] Requesting DHCP lease..."
udhcpc -i "${IFACE}" -n -t 5 -T 3

echo "[wifi] Connection ready"
ip -br addr show "${IFACE}"
ip route
EOF

chmod 700 /usr/local/sbin/frdm-wifi-connect.sh

cat >/usr/local/sbin/frdm-dns-config.sh <<EOF
#!/bin/sh
set -eu

cat >/etc/resolv-conf.connman <<'DNS'
nameserver $DNS1
nameserver $DNS2
options timeout:2 attempts:2
DNS

chmod 644 /etc/resolv-conf.connman
EOF

chmod 700 /usr/local/sbin/frdm-dns-config.sh

cat >/etc/systemd/system/frdm-wifi.service <<'EOF'
[Unit]
Description=FRDM-i.MX95 persistent Wi-Fi on mlan0
After=connman.service systemd-modules-load.service
Wants=connman.service

[Service]
Type=oneshot
Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/usr/local/sbin/frdm-wifi-connect.sh
RemainAfterExit=yes
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/frdm-wifi.service.d/10-dns.conf <<'EOF'
[Service]
ExecStartPost=/usr/local/sbin/frdm-dns-config.sh
EOF

sh -n /usr/local/sbin/frdm-wifi-connect.sh
sh -n /usr/local/sbin/frdm-dns-config.sh

systemctl daemon-reload
systemctl enable frdm-wifi.service >/dev/null
systemctl enable connman >/dev/null 2>&1 || true

if systemctl cat autowifi.service >/dev/null 2>&1; then
    if systemctl is-enabled autowifi.service >/dev/null 2>&1; then
        die "Legacy autowifi.service is still enabled."
    fi
    echo "Legacy autowifi.service: disabled"
fi
echo "FRDM Wi-Fi service: enabled"

echo
echo "=== 6. TEST WI-FI + DHCP + DNS + INTERNET BEFORE STORAGE CHANGE ==="

echo "Validating installed WPA configuration..."
grep -q '^[[:space:]]*network={' /etc/wpa_supplicant.conf \
    || die "Installed WPA config has no network block."
grep -q '^[[:space:]]*psk=' /etc/wpa_supplicant.conf \
    || die "Installed WPA config has no PSK."

systemctl restart connman
sleep 2
if ! systemctl restart frdm-wifi.service; then
    echo
    echo "Wi-Fi service failed. Diagnostic status follows:"
    systemctl status frdm-wifi.service --no-pager -l || true
    journalctl -u frdm-wifi.service --no-pager -n 60 || true
    die "Wi-Fi service failed. Storage was not modified."
fi

STATE="$(wpa_cli -i "$WIFI_IF" status 2>/dev/null | sed -n 's/^wpa_state=//p')"
[ "$STATE" = "COMPLETED" ] || die "Wi-Fi did not reach COMPLETED state. Storage was not modified."

IPV4="$(ip -4 -o addr show dev "$WIFI_IF" scope global | awk '{print $4; exit}')"
[ -n "$IPV4" ] || die "No IPv4 address was obtained on $WIFI_IF."

echo "Wi-Fi: COMPLETED"
echo "IPv4:  $IPV4"

getent ahostsv4 www.google.com >/dev/null 2>&1 || die "DNS test failed for www.google.com."
curl -I --connect-timeout 5 --max-time 15 https://www.google.com >/dev/null 2>&1 || die "HTTPS Internet test failed."

echo "DNS:      PASS"
echo "Internet: PASS"

echo
echo "=== 7. INSTALL ONE-TIME ROOT FILESYSTEM GROW SERVICE ==="

cat >/usr/local/sbin/frdm-expand-rootfs-once.sh <<'EOF'
#!/bin/sh
set -eu

MARKER="/var/lib/frdm-provision/rootfs-grow.pending"
DEV="/dev/mmcblk0p2"

[ -e "$MARKER" ] || exit 0

echo "[rootfs-grow] Growing ext4 filesystem on $DEV..."
resize2fs "$DEV"

rm -f "$MARKER"
systemctl disable frdm-expand-rootfs.service >/dev/null 2>&1 || true
echo "[rootfs-grow] Complete."
EOF

chmod 700 /usr/local/sbin/frdm-expand-rootfs-once.sh

cat >/etc/systemd/system/frdm-expand-rootfs.service <<'EOF'
[Unit]
Description=FRDM-i.MX95 one-time root filesystem expansion
After=local-fs.target
ConditionPathExists=/var/lib/frdm-provision/rootfs-grow.pending

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/frdm-expand-rootfs-once.sh

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable frdm-expand-rootfs.service >/dev/null

echo
echo "=== 8. EXPAND ROOT PARTITION IF NEEDED ==="

P2_SIZE_NOW="$(cat /sys/class/block/mmcblk0p2/size)"
P2_END_NOW=$((P2_START + P2_SIZE_NOW - 1))
FREE_AFTER=$((DISK_SECTORS - P2_END_NOW - 1))

echo "Current p2 sectors: $P2_SIZE_NOW"
echo "Free sectors after p2: $FREE_AFTER"

if [ "$FREE_AFTER" -gt 1048576 ]; then
    echo
    echo "About to enlarge partition 2 to consume the free space."
    echo "Its START sector will remain unchanged at $P2_START."
    echo
    printf "Type EXPAND to continue: "
    IFS= read -r CONFIRM
    [ "$CONFIRM" = "EXPAND" ] || die "Partition expansion cancelled."

    sync

    printf ',+\n' | sfdisk --lock=yes --no-reread --no-tell-kernel -N 2 "$DISK"

    sync
    touch /var/lib/frdm-provision/rootfs-grow.pending

    echo
    echo "Partition table updated on disk."
    echo "A reboot is REQUIRED before resize2fs can use the new partition size."
else
    echo "Partition 2 already occupies essentially the full disk."
    echo "No partition-table modification is needed."
    echo "Checking/growing ext4 online (safe if already at full size)..."
    resize2fs "$ROOTPART"
    rm -f /var/lib/frdm-provision/rootfs-grow.pending
    systemctl disable frdm-expand-rootfs.service >/dev/null 2>&1 || true
fi

echo
echo "=== 9. FINAL PRE-REBOOT STATUS ==="
echo "Wi-Fi service: $(systemctl is-enabled frdm-wifi.service)"
if systemctl cat autowifi.service >/dev/null 2>&1; then
    echo "Legacy autowifi service: $(systemctl is-enabled autowifi.service 2>/dev/null || true)"
fi
echo "Root-grow service: $(systemctl is-enabled frdm-expand-rootfs.service 2>/dev/null || true)"
echo "Backup: $BACKUP"

echo
echo "============================================================"
echo " PROVISIONING PHASE 1 COMPLETE"
echo "============================================================"
echo
echo "Reboot the board now with:"
echo "  reboot"
echo
echo "After it comes back, run frdm_imx95_verify.sh."
