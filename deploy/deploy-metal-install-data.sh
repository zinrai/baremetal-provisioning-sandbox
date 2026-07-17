#!/bin/sh
# Deploy metal-install's data tree (os/machines/templates/compatibility) as a
# timestamped release and flip the `current` symlink the server reads from.
#
# Lifecycle split: Ansible owns the binary, the systemd unit, and the shared
# config (shared/env.yml). This owns the content (releases + current). Runtime
# state (nodes/, configs/) lives in state_dir, outside both.
#
# Atomic: `current` is flipped only after the copy succeeds, so a failed deploy
# leaves the previous release serving. Rollback: point `current` at an older
# release and restart. Run from the repo on the LXC host (uses sudo lxc-attach,
# the same host-to-container path as deb-rootfs and the metal-bootstrap step).
# The metal-install Ansible playbook must have run first (it places
# shared/env.yml).
set -eu

CT=metal-install
BASE=/opt/metal-install
ROOTFS="/var/lib/lxc/$CT/rootfs"
SRC="$(cd "$(dirname "$0")" && pwd)/metal-install-data"
KEEP=5

sudo test -f "$ROOTFS$BASE/shared/env.yml" || {
	echo "error: $BASE/shared/env.yml missing in $CT; run the metal-install Ansible playbook first" >&2
	exit 1
}

ver=$(date +%Y%m%d%H%M%S)
rel="$BASE/releases/$ver"

sudo mkdir -p "$ROOTFS$rel"
sudo rsync -a "$SRC/" "$ROOTFS$rel/"
sudo lxc-attach -n "$CT" -- sh -euc "
	ln -sfn ../../shared/env.yml '$rel/env.yml'
	ln -sfn 'releases/$ver' '$BASE/current'
	systemctl restart metal-install
	ls -1dt '$BASE'/releases/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
"
echo "deployed release $ver (current -> releases/$ver)"
