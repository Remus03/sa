#!/bin/sh
set -eu

FAIL=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }

echo "============================================================"
echo " FRDM-i.MX95 PROVISIONING VERIFICATION"
echo "============================================================"

echo
echo "=== STORAGE ==="
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
echo
df -hT /

ROOT_BYTES="$(df -B1 --output=size / | tail -n1 | tr -d ' ')"
P2_BYTES="$(blockdev --getsize64 /dev/mmcblk0p2)"

if [ "$P2_BYTES" -ge 30000000000 ]; then
    pass "root partition is expanded ($P2_BYTES bytes)"
else
    fail "root partition is still too small ($P2_BYTES bytes)"
fi

if [ "$ROOT_BYTES" -ge 28000000000 ]; then
    pass "ext4 root filesystem is expanded ($ROOT_BYTES bytes)"
else
    fail "ext4 root filesystem is still too small ($ROOT_BYTES bytes)"
fi

if [ -e /var/lib/frdm-provision/rootfs-grow.pending ]; then
    fail "rootfs-grow pending marker still exists"
else
    pass "one-time rootfs grow completed"
fi

echo
echo "=== WI-FI SERVICE ==="
if systemctl is-enabled frdm-wifi.service >/dev/null 2>&1; then
    pass "frdm-wifi.service is enabled"
else
    fail "frdm-wifi.service is not enabled"
fi

if systemctl is-active frdm-wifi.service >/dev/null 2>&1; then
    pass "frdm-wifi.service is active"
else
    fail "frdm-wifi.service is not active"
fi

echo
echo "=== WI-FI STATUS ==="
wpa_cli -i mlan0 status || true

WPA_STATE="$(wpa_cli -i mlan0 status 2>/dev/null | sed -n 's/^wpa_state=//p')"
if [ "$WPA_STATE" = "COMPLETED" ]; then
    pass "Wi-Fi association is COMPLETED"
else
    fail "Wi-Fi state is '${WPA_STATE:-unknown}'"
fi

IPV4="$(ip -4 -o addr show dev mlan0 scope global 2>/dev/null | awk '{print $4; exit}')"
if [ -n "$IPV4" ]; then
    pass "mlan0 has IPv4 address $IPV4"
else
    fail "mlan0 has no global IPv4 address"
fi

echo
echo "=== ROUTING ==="
ip route
GW="$(ip route | awk '/^default/ && /dev mlan0/{print $3; exit}')"
if [ -n "$GW" ]; then
    pass "default gateway is $GW via mlan0"
else
    fail "no default route via mlan0"
fi

echo
echo "=== DNS ==="
cat /etc/resolv.conf

if grep -q '^nameserver 8\.8\.8\.8$' /etc/resolv.conf; then
    pass "8.8.8.8 is configured"
else
    fail "8.8.8.8 is not configured"
fi

if grep -q '^nameserver 8\.8\.4\.4$' /etc/resolv.conf; then
    pass "8.8.4.4 is configured"
else
    fail "8.8.4.4 is not configured"
fi

if getent ahostsv4 www.google.com >/dev/null 2>&1; then
    pass "DNS resolves www.google.com"
else
    fail "DNS cannot resolve www.google.com"
fi

echo
echo "=== INTERNET ==="
if ping -c 3 8.8.8.8 >/dev/null 2>&1; then
    pass "Internet is reachable by IPv4"
else
    fail "8.8.8.8 is not reachable"
fi

if ping -4 -c 3 www.google.com >/dev/null 2>&1; then
    pass "www.google.com is reachable by name"
else
    fail "www.google.com ping failed"
fi

if curl -I --connect-timeout 5 --max-time 15 https://www.google.com >/dev/null 2>&1; then
    pass "HTTPS Internet access works"
else
    fail "HTTPS Internet test failed"
fi

echo
echo "============================================================"
if [ "$FAIL" -eq 0 ]; then
    echo " ALL CHECKS PASSED"
    echo "============================================================"
    exit 0
else
    echo " ONE OR MORE CHECKS FAILED"
    echo "============================================================"
    exit 1
fi
