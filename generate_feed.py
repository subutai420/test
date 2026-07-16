#!/usr/bin/env python3
"""Generate an automatically refreshed Mergado enrichment CSV for Louie.pet."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SOURCE = "https://storage.feedyio.com/louie-live.myshopify.com/680a098212d6dc71048c87d7.xml"
NS = {"g": "http://base.google.com/ns/1.0"}
MIN_EXPECTED_PRODUCTS = 50


def download(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Louie-Mergado-Feed/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def value(item: ET.Element, name: str) -> str:
    node = item.find(f"g:{name}", NS) if name != "description" else item.find("description")
    return (node.text or "").strip() if node is not None else ""


def normalize_title(title: str) -> str:
    title = re.sub(r"\s*\|\s*", " | ", title.strip())
    title = re.sub(r"(?<=\d)\s*ks\b", " ks", title, flags=re.I)
    title = re.sub(r"(?<=\d)\s*(kg|g|ml)\b", r" \1", title, flags=re.I)
    return re.sub(r"\s+", " ", title).replace(" + ", " a ")


def classify(title: str, product_type: str, link: str) -> tuple[str, str, bool]:
    text = title.lower()
    service = bool(re.search(r"bezpečné doručení|přednostní vychystání", text))
    species = "cat" if "cat" in product_type.lower() or "koči" in text or "kocici" in link.lower() else "dog"
    multipack = bool(re.search(r"balíček|mix|\b\d+\s*ks\b", text, re.I))
    if service:
        kind = "service"
    elif "víčko" in text:
        species, kind = "universal", "accessory"
    elif "šampon" in text:
        kind = "grooming"
    elif multipack:
        kind = "bundle"
    elif re.search(r"sušen|pamlsk|dršťk|pařát|kůž", text):
        kind = "treat"
    elif "kapsič" in text:
        kind = "pouch"
    elif "vývar" in text:
        kind = "broth"
    else:
        kind = "can"
    return species, kind, service


def taxonomy(species: str, kind: str) -> tuple[str, str]:
    if kind == "accessory":
        return "pet accessory", "Animals & Pet Supplies > Pet Supplies"
    if kind == "grooming":
        animal = "Cat" if species == "cat" else "Dog"
        return f"{species} grooming", f"Animals & Pet Supplies > Pet Supplies > {animal} Supplies"
    if kind == "treat":
        return "dog treats", "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Food"
    animal = "Cat" if species == "cat" else "Dog"
    return f"{species} food", f"Animals & Pet Supplies > Pet Supplies > {animal} Supplies > {animal} Food"


def optimized_title(title: str, species: str, kind: str) -> str:
    title = normalize_title(title)
    if kind in {"accessory", "grooming"}:
        return title
    animal = "kočky" if species == "cat" else "psy"
    label = {
        "treat": f"pamlsek pro {animal}",
        "bundle": f"balíček pro {animal}",
        "pouch": f"vlhké krmivo pro {animal}",
        "broth": f"vývar pro {animal}",
        "can": f"vlhké krmivo pro {animal}",
    }[kind]
    if label.lower() not in title.lower() and f"pro {animal}" not in title.lower():
        title = f"{title} | {label}"
    return title[:200].rstrip()


def optimized_description(title: str, description: str, species: str, kind: str) -> str:
    description = re.sub(r"\s+", " ", description).strip()
    description = re.sub(r"(?<=\d)%(?=\D|$)", " %", description)
    animal = "kočky" if species == "cat" else "psy"
    core = re.sub(r"\s*\|.*$", "", normalize_title(title))
    core = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:kg|g|ml)\s*$", "", core, flags=re.I).strip(" -")
    prefix = {
        "accessory": f"Praktické příslušenství ke krmivu: {core}.",
        "grooming": f"Péče pro {animal}: {core}.",
        "treat": f"Pamlsek pro {animal}: {core}.",
        "bundle": f"Balíček pro {animal}: {core}.",
        "pouch": f"Vlhké krmivo pro {animal}: {core}.",
        "broth": f"Vývar pro {animal}: {core}.",
        "can": f"Vlhké krmivo pro {animal}: {core}.",
    }[kind]
    if not description:
        return prefix
    return description if description.lower().startswith(prefix.lower()) else f"{prefix} {description}"[:9999]


def price_number(text: str) -> float:
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(match.group(0).replace(",", ".")) if match else 0.0


def transform(xml_bytes: bytes) -> tuple[list[dict[str, str]], dict[str, object]]:
    root = ET.fromstring(xml_bytes)
    items = root.findall("./channel/item")
    if len(items) < MIN_EXPECTED_PRODUCTS:
        raise ValueError(f"Safety check failed: source contains only {len(items)} products")

    rows: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in items:
        item_id = value(item, "id")
        title = value(item, "title")
        if not item_id or not title:
            raise ValueError("Source item is missing ID or title")
        if item_id in seen_ids:
            raise ValueError(f"Duplicate product ID: {item_id}")
        seen_ids.add(item_id)

        product_type = value(item, "product_type")
        link = value(item, "link")
        species, kind, service = classify(title, product_type, link)
        if service:
            excluded.append({"id": item_id, "title": title})
            continue

        price = price_number(value(item, "price"))
        sale_text = value(item, "sale_price")
        sale_price = price_number(sale_text)
        discount = 0 if not price or not sale_text else round((price - sale_price) / price * 100)
        normalized_type, category = taxonomy(species, kind)
        rows.append({
            "ID": item_id,
            "TITLE": optimized_title(title, species, kind),
            "DESCRIPTION": optimized_description(title, value(item, "description"), species, kind),
            "PRODUCT_TYPE": normalized_type,
            "GOOGLE_PRODUCT_CATEGORY": category,
            "BRAND": "Louie",
            "CUSTOM_LABEL_0": species,
            "CUSTOM_LABEL_1": kind,
            "CUSTOM_LABEL_2": "multipack" if kind == "bundle" else "single",
            "CUSTOM_LABEL_3": "under_100" if price < 100 else ("100_499" if price < 500 else "500_plus"),
            "CUSTOM_LABEL_4": "no_discount" if discount <= 0 else ("discount_50_plus" if discount >= 50 else "discount_1_49"),
        })

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_items": len(items),
        "output_items": len(rows),
        "excluded_items": excluded,
        "source_sha256": hashlib.sha256(xml_bytes).hexdigest(),
    }
    return rows, status


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output", default="docs/mergado-import.csv")
    parser.add_argument("--status", default="docs/status.json")
    parser.add_argument("--source-file", help="Use a local XML file instead of downloading")
    args = parser.parse_args()

    xml_bytes = Path(args.source_file).read_bytes() if args.source_file else download(args.source)
    rows, status = transform(xml_bytes)
    write_csv(Path(args.output), rows)
    status_path = Path(args.status)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
