# nmap_diff

Compare two nmap scans and report what changed between them: hosts that appeared,
hosts that disappeared, and hosts whose open ports (or FQDN) changed.

`nmap_diff.py` works on **CSV**, not on raw nmap output. You first convert each
scan to CSV with the bundled [`nmaptocsv`](./nmaptocsv) tool, then diff the two
CSV files.

## Workflow

```
scan.nmap  ──(nmaptocsv)──▶  scan.csv  ──(nmap_diff)──▶  diff report
```

1. **Parse each scan to CSV** with `nmaptocsv`.
2. **Diff the two CSV files** with `nmap_diff.py`.

## Requirements

- Python 3
- No third-party dependencies for `nmap_diff.py` (standard library only).
- `nmaptocsv` has its own requirements — see [`nmaptocsv/requirements.txt`](./nmaptocsv/requirements.txt).

## Usage

### Step 1 — parse each nmap scan to CSV

Run an nmap scan and save it in a parseable format. `nmaptocsv` accepts nmap's
normal (`-oN`), grepable (`-oG`), or XML (`-oX`) output.

```bash
# example: normal nmap output saved to test2.nmap
python3 nmaptocsv/nmaptocsv.py -i testing/test2.nmap -o testing/test2.csv
```

Do this for both the earlier ("old") and the later ("new") scan so you have two
CSV files to compare.

### Step 2 — diff the two CSV files

```bash
python3 nmap_diff.py testing/test1.csv testing/test2.csv
```

The first argument is the **old** scan, the second is the **new** scan.

## Example

```
$ python3 nmap_diff.py testing/test1.csv testing/test2.csv
old scan: testing/test1.csv
new scan: testing/test2.csv

IP ADDRESS      FQDN         STATUS   DETAILS
--------------  -----------  -------  ---------------------------------------------
104.20.23.154   example.com  NEW      open: 80/tcp, 443/tcp, 8080/tcp, 8443/tcp
172.66.147.243  example.com  MISSING  was open: 80/tcp, 443/tcp, 8080/tcp, 8443/tcp

1 new host(s), 1 host(s) no longer present, 0 host(s) with changed ports/FQDN.
```

## What the statuses mean

Hosts are keyed on their **IP address**.

| Status    | Meaning                                                             |
|-----------|--------------------------------------------------------------------|
| `NEW`     | Host is present only in the new scan.                               |
| `MISSING` | Host is present only in the old scan.                               |
| `CHANGED` | Host is in both scans, but its open ports or FQDN differ.          |

By default only **open** ports are compared. A `CHANGED` row lists which ports
were `opened`, which were `closed`, and whether the FQDN changed.

## Options

```
python3 nmap_diff.py OLD.csv NEW.csv [options]
```

| Option             | Description                                                        |
|--------------------|-------------------------------------------------------------------|
| `--only {new,missing,changed}` | Restrict output to a single status.                   |
| `--format {table,csv}`         | Output as a table (default) or CSV.                   |
| `--all-states`     | Compare all ports, not just those in an open state.               |
| `--ip-column NAME` | Name of the IP address column (auto-detected by default).         |
| `--fqdn-column NAME`  | Name of the hostname/FQDN column.                              |
| `--port-column NAME`  | Name of the port column.                                      |
| `--proto-column NAME` | Name of the protocol column.                                  |
| `--state-column NAME` | Name of the port state column.                                |

Examples:

```bash
# only show hosts whose ports/FQDN changed
python3 nmap_diff.py old.csv new.csv --only changed

# machine-readable diff
python3 nmap_diff.py old.csv new.csv --format csv > delta.csv

# compare all port states, not just open
python3 nmap_diff.py old.csv new.csv --all-states
```

## CSV format

"nmap CSV" is not a native nmap format, so column names vary between converters
(`nmaptocsv`, nmap-parse-output, ndiff, `xsltproc`, etc.). `nmap_diff.py`
auto-detects the IP, FQDN, port, protocol, and state columns from common header
names and sniffs the delimiter (`,` `;` tab `|`) automatically. If your export
uses unusual headers, point it at the right columns with the `--*-column`
options.

The CSV files produced by the bundled `nmaptocsv` (semicolon-separated, with
`IP`, `FQDN`, `PORT`, `PROTOCOL`, `SERVICE`, `VERSION` columns) work out of the
box:

```
"IP";"FQDN";"PORT";"PROTOCOL";"SERVICE";"VERSION"
"172.66.147.243";"example.com";"80";"tcp";"http";""
"172.66.147.243";"example.com";"443";"tcp";"https";""
```

Multi-row-per-host exports (one row per port) are merged into a single host
entry automatically.
```
