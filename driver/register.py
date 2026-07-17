#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request


def node_id_from_mac(mac):
    # metal-install's node_id convention is the MAC in lowercase hyphen form
    # (${mac:hexhyp}), which is also what netboot-guest boots with.
    return mac.replace(":", "-")


def read_pubkey(path):
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        return []
    handle = open(expanded)
    try:
        text = handle.read()
    finally:
        handle.close()
    keys = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped != "":
            keys.append(stripped)
    return keys


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="register",
        description="Register the guest with metal-install (POST /nodes).",
    )
    parser.add_argument(
        "--mac", required=True, help="guest MAC (node_id is the MAC with '-' for ':')"
    )
    parser.add_argument(
        "--server", default="http://10.0.10.31:8080", help="metal-install base URL"
    )
    parser.add_argument("--machine", default="qemu_vm")
    parser.add_argument("--os", default="debian13")
    parser.add_argument(
        "--pubkey",
        default="~/.ssh/id_ed25519.pub",
        help="SSH public key authorized on the guest (empty list if the file is missing)",
    )
    # Precomputed SHA512-crypt of the lab password "netboot" (fixed salt, so it
    # is deterministic and needs no openssl at runtime). A known password is
    # fine for a throwaway non-production guest and lets you log in at the
    # console; override for a different one, or pass a locked marker like '*'.
    parser.add_argument(
        "--password-hash",
        default="$6$netbootlab$bpdA/In3AlNgtpUAgu/7P8uqu70FmVyrBZ14DFZE86DwESNujhYQc1vUw8kEuXCcL0OFBQm82pn39Oux1PztB.",
        help="root password crypt hash (default: SHA512-crypt of 'netboot')",
    )
    parser.add_argument("--ipv4-addr", default="10.0.20.50", dest="ipv4_addr")
    parser.add_argument("--prefix-length", type=int, default=24, dest="prefix_length")
    parser.add_argument("--gateway", default="10.0.20.1")
    parser.add_argument("--dns", default="1.1.1.1")
    return parser


def main():
    args = build_parser().parse_args()
    node_id = node_id_from_mac(args.mac)
    spec = {
        "machine": args.machine,
        "os": args.os,
        "node_id": node_id,
        "ipv4_addr": args.ipv4_addr,
        "prefix_length": args.prefix_length,
        "gateway": args.gateway,
        "dns": args.dns,
        "root_password_hash": args.password_hash,
        "ssh_keys": read_pubkey(args.pubkey),
    }
    url = args.server + "/nodes"
    print("==> POST %s (node_id=%s)" % (url, node_id))
    print(post_json(url, spec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
