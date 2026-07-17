# DESIGN

A bare-metal provisioning system reproduced on LXC containers, so the whole
DHCP to unattended-install path can be exercised on one host. It stands up the
three tools that make up the system and drives a QEMU virtual machine through a
real install as the stand-in for a physical server.

- [metal-install](https://github.com/zinrai/metal-install): renders and serves
  per-node install artifacts (boot.ipxe, preseed, post scripts).
- [metal-bootstrap](https://github.com/zinrai/metal-bootstrap): fetches the
  kernel and initrd the installer needs.
- [fleet-dhcpd](https://github.com/zinrai/fleet-dhcpd): HA DHCP that answers the
  node and points it at the iPXE boot chain, with lease and config state in
  Consul KV.

The substrate follows the netshed to declxc to deb-rootfs to Ansible pattern
used by [hashicorp-nomad-sandbox](https://github.com/zinrai/hashicorp-nomad-sandbox)
and [incus-sandbox](https://github.com/zinrai/incus-sandbox). The Consul roles
are taken from hashicorp-nomad-sandbox.

## Networks

Two bridges, created from [`network.yaml`](network.yaml) with netshed:

| Bridge | Subnet | NAT | Role |
|--------|--------|-----|------|
| `prov0` | 10.0.10.0/24 | yes | provisioning: fleet-dhcpd serves DHCP, the VM PXE-boots here |
| `svc0`  | 10.0.20.0/24 | no  | service: the installed VM is moved here |

The two-bridge split is the point of the lab. A node installs on the
provisioning network and is then moved to an isolated service network, the same
separation a datacenter draws between a provisioning segment and a production
segment.

## Nodes

Eight LXC containers on `prov0`, declared with static IPs in
[`containers.yaml`](containers.yaml):

| Container | IP | Runs |
|-----------|-----|------|
| consul-server-0..2 | 10.0.10.11-.13 | Consul servers (`bootstrap_expect` 3) |
| fleet-dhcpd-0..2   | 10.0.10.21-.23 | Consul client + fleet-dhcpd |
| metal-install      | 10.0.10.31 | `metal-install server` |
| artifact           | 10.0.10.41 | nginx + metal-bootstrap |

DHCP range on `prov0` is 10.0.10.100-.200, offered to the QEMU VM. The host
holds 10.0.10.1 and does outbound NAT.

The QEMU VM is not a container. It is driven by
[netboot-guest](https://github.com/zinrai/netboot-guest), which attaches it to
`prov0` (for the install) or `svc0` (afterward) through a tap. netboot-guest is
generic and knows nothing about metal-install; registering the node with the
install server is a separate step (`driver/register.py`).

## Flow

1. **Artifact prep.** metal-bootstrap fetches the Debian netboot kernel and
   initrd into the artifact node's nginx docroot under `images/debian/13/`.
2. **Register.** `driver/register.py` POSTs an InstallSpec for the VM to
   metal-install.
3. **Boot.** The VM powers on and PXE-boots. fleet-dhcpd answers with an address
   and a `boot_url` of `http://10.0.10.41/bootstrap.ipxe`.
4. **Chain.** iPXE fetches `bootstrap.ipxe`, which chains to
   `http://10.0.10.41/configs/<node_id>/boot.ipxe` rendered by metal-install.
5. **Install.** boot.ipxe loads kernel and initrd from the artifact node and
   preseed from metal-install; the installer partitions, installs the base
   system, and runs the post scripts.
6. **Power off and deregister.** The installer powers the VM off at the end of
   the install. The driver then DELETEs the node from metal-install
   (`deregister.py`); metal-install does not track completion itself.
7. **Commission.** `netboot-guest up` boots the installed disk on `svc0`, the
   service network.

## Design decisions

- **fleet-dhcpd nodes run a co-located Consul client.** fleet-dhcpd talks to
  Consul at `localhost:8500`, matching the standard Consul agent-per-node model,
  so the DHCP config and lease state live in the KV the servers hold. The config
  is written to KV once (`run_once`) and every instance reads it on start.
- **Single HTTP front on the artifact node.** nginx serves `/images` from disk
  and reverse proxies `/configs` and `/nodes` to metal-install, so one base URL
  (`http://10.0.10.41`) resolves both the boot images and the per-node
  artifacts. That is the single `http_base` the templates expect.
- **metal-bootstrap keeps explicit pinned sha256.** The checksums are declared
  in the config, which is the tool's verification contract; the lab does not
  fetch checksums at runtime. If Debian rotates the current netboot image,
  refresh the two sha256 values from the netboot `SHA256SUMS`.
- **Debian only.** The lab wires one machine and one OS (`qemu_vm`, `debian13`)
  to keep the install path short and the artifact fetch light. metal-install and
  metal-bootstrap both carry AlmaLinux and Ubuntu examples upstream to add.
- **qemu_vm has no NICs or bonds.** A VM has no fixed PCI-to-NIC mapping, so the
  machine profile leaves them empty: the udev and network post scripts render to
  no-ops, and the installer uses DHCP on the provisioning bridge.

## Scope

- Not an HA or production deployment. Single host, one VM, small container set.
- Post-install network config for the service segment is out of scope: qemu_vm
  renders no bonds, so the installed system carries no static service address.
  The move to `svc0` demonstrates the network change, not a configured service
  identity.
- Building iPXE ROMs is out of scope; the VM uses the ipxe-qemu option ROM.
