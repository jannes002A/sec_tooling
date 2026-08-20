#!/usr/bin/env python3
"""
nmap_diff.py - Compare two nmap scans exported as CSV.

Reports:
  NEW      host only in the newer scan
  MISSING  host only in the older scan
  CHANGED  host in both scans, but its open ports (or FQDN) differ

Each host is keyed on its IP address. Because "nmap CSV" is not a native nmap
format (it is usually produced by converting XML with nmap-parse-output,
xsltproc, ndiff, etc.), column names vary between tools, so the IP, hostname,
port, protocol and state columns are auto-detected from common header names.
Override with the --*-column options if your export is unusual.

Usage:
    python3 nmap_diff.py old_scan.csv new_scan.csv
    python3 nmap_diff.py old.csv new.csv --only changed
    python3 nmap_diff.py old.csv new.csv --format csv > delta.csv
    python3 nmap_diff.py old.csv new.csv --all-states     # not just open ports
"""

import argparse
import csv
import ipaddress
import re
import sys
from collections import OrderedDict

# Candidate header names, matched case-insensitively, ignoring non-alphanumerics.
IP_HEADERS = ["ip", "ipaddress", "ipv4", "ipv4address", "address", "addr",
              "host", "hostaddress", "target"]
FQDN_HEADERS = ["fqdn", "hostname", "hostnames", "dns", "dnsname", "ptr",
                "rdns", "reversedns", "name", "host"]
PORT_HEADERS = ["port", "ports", "portid", "portnumber", "openports", "tcpports"]
PROTO_HEADERS = ["protocol", "proto", "transport", "portprotocol"]
STATE_HEADERS = ["state", "portstate", "status", "portstatus"]

PROTOCOLS = {"tcp", "udp", "sctp", "ip"}
PORT_STATES = {"open", "closed", "filtered", "unfiltered",
               "openfiltered", "closedfiltered"}


def normalise(header):
    return "".join(ch for ch in header.lower() if ch.isalnum())


def find_column(fieldnames, candidates, used=None):
    used = used or set()
    lookup = {}
    for name in fieldnames:
        if name is not None:
            lookup.setdefault(normalise(name), name)
    for candidate in candidates:
        match = lookup.get(candidate)
        if match and match not in used:
            return match
    return None


def is_ip(value):
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


def sniff_ip_column(rows, fieldnames):
    """Fallback: the column whose values look most like IP addresses."""
    best, best_score = None, 0
    for name in fieldnames:
        if name is None:
            continue
        score = sum(1 for r in rows[:200] if is_ip(r.get(name, "") or ""))
        if score > best_score:
            best, best_score = name, score
    return best if best_score else None


def parse_port_field(value, default_proto, default_state):
    """
    Parse a port cell into [(port, proto, state), ...].

    Handles a bare number ("80"), a list ("22,80,443" / "22 80 443"),
    "80/tcp" style tokens, and greppable-ish tokens such as
    "80/open/tcp//http//" in any field order.
    """
    results = []
    for token in re.split(r"[,;\s]+", value.strip()):
        if not token:
            continue
        parts = [p.strip().lower() for p in token.split("/") if p.strip()]
        number = next((p for p in parts if p.isdigit()), None)
        if number is None:
            continue
        proto = next((p for p in parts if p in PROTOCOLS), default_proto)
        state = next((p for p in parts if p in PORT_STATES), default_state)
        results.append((int(number), proto, state))
    return results


def load_scan(path, cols):
    """
    Read an nmap CSV export.

    Returns OrderedDict {ip: {"fqdn": str, "ports": set("80/tcp")}}.
    Multi-row-per-host exports (one row per port) are merged into one entry.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            sample = fh.read(8192)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(fh, dialect=dialect)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        sys.exit(f"error: file not found: {path}")
    except OSError as exc:
        sys.exit(f"error: could not read {path}: {exc}")

    if not fieldnames:
        sys.exit(f"error: {path} appears to be empty or has no header row")

    ip_col = cols["ip"] or find_column(fieldnames, IP_HEADERS) \
        or sniff_ip_column(rows, fieldnames)
    if ip_col is None:
        sys.exit(f"error: could not identify an IP column in {path}.\n"
                 f"       headers: {', '.join(str(f) for f in fieldnames)}\n"
                 f"       use --ip-column to specify it explicitly.")

    used = {ip_col}
    fqdn_col = cols["fqdn"] or find_column(fieldnames, FQDN_HEADERS, used)
    if fqdn_col:
        used.add(fqdn_col)
    port_col = cols["port"] or find_column(fieldnames, PORT_HEADERS, used)
    if port_col:
        used.add(port_col)
    proto_col = cols["proto"] or find_column(fieldnames, PROTO_HEADERS, used)
    if proto_col:
        used.add(proto_col)
    state_col = cols["state"] or find_column(fieldnames, STATE_HEADERS, used)

    for label, col in (("ip", ip_col), ("fqdn", fqdn_col), ("port", port_col),
                       ("proto", proto_col), ("state", state_col)):
        if col is not None and col not in fieldnames:
            sys.exit(f"error: {label} column '{col}' not present in {path}")

    hosts = OrderedDict()
    for row in rows:
        ip = (row.get(ip_col) or "").strip()
        if not ip:
            continue
        entry = hosts.setdefault(ip, {"fqdn": "", "ports": set()})

        if fqdn_col and not entry["fqdn"]:
            fqdn = (row.get(fqdn_col) or "").strip()
            # Some exports pack several hostnames into one field.
            entry["fqdn"] = fqdn.replace(";", ",").split(",")[0].strip()

        if not port_col:
            continue
        proto = ((row.get(proto_col) or "").strip().lower()
                 if proto_col else "tcp") or "tcp"
        state = ((row.get(state_col) or "").strip().lower()
                 if state_col else "open") or "open"
        for number, prot, stat in parse_port_field(
                row.get(port_col) or "", proto, state):
            if cols["all_states"] or stat.startswith("open"):
                entry["ports"].add(f"{number}/{prot}")

    return hosts, bool(port_col)


def ip_sort_key(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return (0, addr.version, int(addr))
    except ValueError:
        return (1, 0, ip)


def port_sort_key(port):
    number, _, proto = port.partition("/")
    return (proto, int(number) if number.isdigit() else 0)


def fmt_ports(ports, prefix=""):
    return ", ".join(prefix + p for p in sorted(ports, key=port_sort_key))


def diff(old_hosts, new_hosts):
    """Return list of dicts describing every host that differs between scans."""
    results = []

    for ip in sorted(set(new_hosts) - set(old_hosts), key=ip_sort_key):
        host = new_hosts[ip]
        results.append({"ip": ip, "fqdn": host["fqdn"], "status": "NEW",
                        "opened": set(host["ports"]), "closed": set(),
                        "fqdn_was": None})

    for ip in sorted(set(old_hosts) - set(new_hosts), key=ip_sort_key):
        host = old_hosts[ip]
        results.append({"ip": ip, "fqdn": host["fqdn"], "status": "MISSING",
                        "opened": set(), "closed": set(host["ports"]),
                        "fqdn_was": None})

    for ip in sorted(set(old_hosts) & set(new_hosts), key=ip_sort_key):
        old, new = old_hosts[ip], new_hosts[ip]
        opened = new["ports"] - old["ports"]
        closed = old["ports"] - new["ports"]
        fqdn_changed = old["fqdn"] != new["fqdn"]
        if opened or closed or fqdn_changed:
            results.append({"ip": ip, "fqdn": new["fqdn"], "status": "CHANGED",
                            "opened": opened, "closed": closed,
                            "fqdn_was": old["fqdn"] if fqdn_changed else None})

    return results


def describe(item, ports_available=True):
    """Human-readable summary of what changed for one host."""
    bits = []
    if item["status"] == "NEW":
        if ports_available:
            bits.append("open: " + (fmt_ports(item["opened"]) or "no open ports"))
    elif item["status"] == "MISSING":
        if ports_available:
            bits.append("was open: " + (fmt_ports(item["closed"]) or "no open ports"))
    else:
        if item["opened"]:
            bits.append("opened " + fmt_ports(item["opened"]))
        if item["closed"]:
            bits.append("closed " + fmt_ports(item["closed"]))
        if item["fqdn_was"] is not None:
            bits.append(f"fqdn was {item['fqdn_was'] or '(none)'}")
    return "; ".join(bits)


def print_table(results, old_path, new_path, ports_available):
    print(f"old scan: {old_path}")
    print(f"new scan: {new_path}")
    if not ports_available:
        print("note: no port column detected - comparing hosts only")
    print()

    if not results:
        print("No differences: both scans contain the same hosts and ports.")
        return

    rows = [(r["ip"], r["fqdn"] or "-", r["status"], describe(r, ports_available))
            for r in results]
    headers = ("IP ADDRESS", "FQDN", "STATUS", "DETAILS")
    widths = [max(len(r[i]) for r in ([headers] + rows)) for i in range(3)]

    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)) + "  " + headers[3])
    print("  ".join("-" * w for w in widths) + "  "
          + "-" * max(7, min(60, max(len(r[3]) for r in rows))))
    for ip, fqdn, status, detail in rows:
        print(f"{ip.ljust(widths[0])}  {fqdn.ljust(widths[1])}  "
              f"{status.ljust(widths[2])}  {detail}")

    counts = {s: sum(1 for r in results if r["status"] == s)
              for s in ("NEW", "MISSING", "CHANGED")}
    print()
    print(f"{counts['NEW']} new host(s), {counts['MISSING']} host(s) no longer "
          f"present, {counts['CHANGED']} host(s) with changed ports/FQDN.")


def print_csv(results):
    writer = csv.writer(sys.stdout)
    writer.writerow(["ip", "fqdn", "status", "ports_opened", "ports_closed",
                     "previous_fqdn"])
    for r in results:
        writer.writerow([r["ip"], r["fqdn"], r["status"],
                         fmt_ports(r["opened"]), fmt_ports(r["closed"]),
                         r["fqdn_was"] or ""])


def main():
    parser = argparse.ArgumentParser(
        description="Compare two nmap CSV scans: hosts added, removed, or with "
                    "changed ports.",
        epilog="STATUS is NEW (only in the new scan), MISSING (only in the old "
               "scan), or CHANGED (in both, but ports/FQDN differ).")
    parser.add_argument("old_scan", help="CSV of the earlier scan")
    parser.add_argument("new_scan", help="CSV of the later scan")
    parser.add_argument("--ip-column", help="name of the IP address column")
    parser.add_argument("--fqdn-column", help="name of the hostname/FQDN column")
    parser.add_argument("--port-column", help="name of the port column")
    parser.add_argument("--proto-column", help="name of the protocol column")
    parser.add_argument("--state-column", help="name of the port state column")
    parser.add_argument("--all-states", action="store_true",
                        help="compare all ports, not just those in an open state")
    parser.add_argument("--format", choices=("table", "csv"), default="table",
                        help="output format (default: table)")
    parser.add_argument("--only", choices=("new", "missing", "changed"),
                        help="restrict output to one status")
    args = parser.parse_args()

    cols = {"ip": args.ip_column, "fqdn": args.fqdn_column,
            "port": args.port_column, "proto": args.proto_column,
            "state": args.state_column, "all_states": args.all_states}

    old_hosts, old_ports = load_scan(args.old_scan, cols)
    new_hosts, new_ports = load_scan(args.new_scan, cols)

    results = diff(old_hosts, new_hosts)
    if args.only:
        results = [r for r in results if r["status"] == args.only.upper()]

    if args.format == "csv":
        print_csv(results)
    else:
        print_table(results, args.old_scan, args.new_scan,
                    old_ports and new_ports)


if __name__ == "__main__":
    main()
