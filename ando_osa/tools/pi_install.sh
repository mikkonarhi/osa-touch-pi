#!/bin/bash
# Replaced by the repository-level installer, which also builds linux-gpib from source:
#   cd <repo> && sudo ./install.sh --help
# Old stage names map to:  debs -> gpib-user   kmod -> gpib-kernel   config -> config   python -> python
REPO=$(cd "$(dirname "$0")/../.." && pwd)
args=()
for a in "$@"; do
    case $a in
        debs) args+=(gpib-user) ;; kmod) args+=(gpib-kernel) ;;
        config|python) args+=("$a") ;;
        *) echo "unknown stage $a"; exit 1 ;;
    esac
done
if [ ${#args[@]} -gt 0 ]; then
    only=$(IFS=,; echo "${args[*]}")
    exec "$REPO/install.sh" --only "$only"
fi
exec "$REPO/install.sh"
