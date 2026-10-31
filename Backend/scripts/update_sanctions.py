"""
Rebuilds data/sanctions_ofac.json from the U.S. Treasury OFAC SDN list.

Usage (from the repository root):
    python scripts/update_sanctions.py              # download the current list
    python scripts/update_sanctions.py --xml sdn.xml # use a local copy instead

The snapshot is rebuilt from scratch every run, so addresses OFAC has delisted
(for example the Tornado Cash addresses removed in March 2025) disappear instead
of lingering. Commit the regenerated JSON and redeploy so the backend picks it up;
the server never downloads the list itself.

Only EVM-style 0x addresses are kept, since those are the only ones BlockTrace can
trace. The same 0x address controls the same account on every EVM chain, so an
address OFAC lists under any EVM currency tag (ETH, USDT, USDC, ARB, BSC, ...) is
treated as sanctioned on all chains BlockTrace supports: Ethereum, BNB Chain and
Polygon. The currency tags OFAC gave it are kept in "currencies".
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

SDN_XML_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
AUTHORITY = "U.S. Treasury OFAC"
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "sanctions_ofac.json")

_ID_TYPE_PREFIX = "Digital Currency Address - "
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _local(tag):
    """Strips the XML namespace, which OFAC has changed between publications."""
    return tag.rsplit("}", 1)[-1]


def _child_text(elem, name):
    for child in elem:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _children(elem, name):
    return [child for child in elem if _local(child.tag) == name]


def _iso_date(us_date):
    """OFAC publishes dates as MM/DD/YYYY."""
    try:
        return datetime.strptime(us_date, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return us_date or None


def parse_sdn_xml(source):
    """Parses SDN.XML (a path or file object) into (list_publication_date, {address: entry})."""
    publication_date = None
    addresses = {}

    for _, elem in ET.iterparse(source, events=("end",)):
        tag = _local(elem.tag)
        if tag == "publshInformation":
            publication_date = _iso_date(_child_text(elem, "Publish_Date"))
            elem.clear()
        elif tag == "sdnEntry":
            name = " ".join(p for p in (_child_text(elem, "firstName"), _child_text(elem, "lastName")) if p)
            uid = _child_text(elem, "uid")
            programs = [p.text.strip() for pl in _children(elem, "programList")
                        for p in _children(pl, "program") if p.text]
            for id_list in _children(elem, "idList"):
                for ident in _children(id_list, "id"):
                    id_type = _child_text(ident, "idType")
                    if not id_type.startswith(_ID_TYPE_PREFIX):
                        continue
                    address = _child_text(ident, "idNumber")
                    if not _EVM_ADDRESS.match(address):
                        continue
                    currency = id_type[len(_ID_TYPE_PREFIX):].strip()
                    entry = addresses.setdefault(address.lower(), {
                        "name": name,
                        "authority": AUTHORITY,
                        "program": "; ".join(programs),
                        "uid": uid,
                        "currencies": [],
                    })
                    if currency and currency not in entry["currencies"]:
                        entry["currencies"].append(currency)
            elem.clear()

    for entry in addresses.values():
        entry["list_published_date"] = publication_date
    return publication_date, addresses


def build_snapshot(publication_date, addresses, source_url, fetched_at=None):
    return {
        "source_url": source_url,
        "fetched_at": fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "list_publication_date": publication_date,
        "count": len(addresses),
        "addresses": dict(sorted(addresses.items())),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xml", help="Parse a local SDN.XML instead of downloading it.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Where to write the JSON snapshot.")
    args = parser.parse_args(argv)

    if args.xml:
        source_url = os.path.abspath(args.xml)
        publication_date, addresses = parse_sdn_xml(args.xml)
    else:
        source_url = SDN_XML_URL
        print(f"Downloading {SDN_XML_URL} ...")
        resp = requests.get(SDN_XML_URL, timeout=300, stream=True)
        resp.raise_for_status()
        resp.raw.decode_content = True
        publication_date, addresses = parse_sdn_xml(resp.raw)

    if not addresses:
        # An empty result almost certainly means the format changed; keep the old snapshot.
        print("No EVM addresses found; the existing snapshot was left unchanged.", file=sys.stderr)
        return 1

    snapshot = build_snapshot(publication_date, addresses, source_url)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")
    print(f"Wrote {snapshot['count']} addresses (list published {publication_date}) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
