#!/bin/sh
set -e
# Chown writable mount points so we can run as the unprivileged 'app' user.
# This is idempotent and only does work when ownership is wrong (e.g. upgrading
# from v0.3.4 which ran as root and wrote root-owned files into Docker volumes).
for dir in /app/instance /app/uploads /app/temp; do
    if [ -d "$dir" ] && [ "$(stat -c '%U' "$dir")" != "app" ]; then
        echo "Fixing ownership of $dir (was $(stat -c '%U' "$dir"))"
        chown -R app:app "$dir"
    fi
done
# Drop privileges and exec the original command.
exec gosu app "$@"
