#!/usr/bin/env bash
# set -euo pipefail
set -u
set -x

# TODO move into noxfile?

sudo apt-get install -qy pipx
pipx install uv
"$SHELL" -c 'pipx ensurepath'
"$SHELL" -c "uv tool install 'nox[uv]'"

bash ./sigsum-install.sh
