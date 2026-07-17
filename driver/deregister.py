#!/usr/bin/env python3
import argparse
import sys
import urllib.error
import urllib.request


def node_id_from_mac(mac):
    # metal-install's node_id convention is the MAC in lowercase hyphen form
    # (${mac:hexhyp}), which is also what netboot-guest boots with.
    return mac.replace(":", "-")


def http_delete(url):
    request = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="deregister",
        description="Deregister the guest from metal-install (DELETE /nodes/<id>).",
    )
    parser.add_argument(
        "--mac", required=True, help="guest MAC (node_id is the MAC with '-' for ':')"
    )
    parser.add_argument(
        "--server", default="http://10.0.10.31:8080", help="metal-install base URL"
    )
    return parser


def main():
    args = build_parser().parse_args()
    node_id = node_id_from_mac(args.mac)
    url = args.server + "/nodes/" + node_id
    print("==> DELETE %s" % url)
    try:
        http_delete(url)
    except urllib.error.HTTPError as err:
        # A node that is already gone is not an error.
        print("(ignored: %s)" % err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
