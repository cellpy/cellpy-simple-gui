#!/bin/sh
# Fail early and legibly on the one thing that reliably goes wrong.
#
# The image runs as uid 10001. A bind-mounted host directory keeps its host
# ownership, so `-v /srv/cellpy:/data` from a root-owned directory produces a
# /data nobody in here can write to. Left alone, that surfaces much later as a
# permission error halfway through a save, with the cell data already loaded.
set -e

DATA_DIR="${CSG_DATA_DIR:-/data}"

mkdir -p "$DATA_DIR" 2>/dev/null || true

if [ ! -w "$DATA_DIR" ]; then
    echo "cellpy-simple-gui: $DATA_DIR is not writable by uid $(id -u)." >&2
    echo "  Projects cannot be saved. If this is a bind mount, fix it on the host:" >&2
    echo "      sudo chown -R 10001:10001 <host-dir>" >&2
    echo "  or use a named volume instead (see docker-compose.yml)." >&2
    exit 1
fi

exec "$@"
