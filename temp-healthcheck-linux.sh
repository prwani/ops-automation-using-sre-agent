#!/bin/bash
set -o pipefail

df -h
systemctl list-units --failed
journalctl -p err --since '6 hours ago' | head -20