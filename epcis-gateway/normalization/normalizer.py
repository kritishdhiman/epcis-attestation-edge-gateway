"""
MODULE 2 — GS1/CBV Normalization Engine
Handles three trading partners using different identifier formats
and normalises everything to GS1 EPCIS standard URNs.
"""

import re
from typing import Dict, List, Tuple


# ── Partner-format profiles ───────────────────────────────────────────────────
PARTNER_PROFILES = {
    "PartnerA": {
        "name": "PharmaSource Ltd",
        "format": "internal_code",
        "sample": "PROD-1234",
        "description": "Uses internal product codes like PROD-XXXX",
    },
    "PartnerB": {
        "name": "MediTrans Delhi",
        "format": "ean13",
        "sample": "5901234123457",
        "description": "Uses EAN-13 barcodes (13-digit numeric)",
    },
    "PartnerC": {
        "name": "CityPharma Mumbai",
        "format": "gs1_urn",
        "sample": "urn:epc:id:sgtin:0614145.107346.2017",
        "description": "Uses proper GS1 URN format (compliant)",
    },
}

# Lookup tables mapping partner-specific codes → canonical GS1 components
INTERNAL_CODE_MAP: Dict[str, Tuple[str, str]] = {
    # internal_code: (company_prefix, item_ref)
    "PROD-1234": ("0614141", "107346"),
    "PROD-2345": ("0614142", "107347"),
    "PROD-3456": ("0614143", "107348"),
    "PROD-0001": ("0614141", "100001"),
}

EAN13_COMPANY_MAP: Dict[str, str] = {
    # first 7 digits of EAN-13 → company GS1 prefix
    "5901234": "0614143",
    "5901235": "0614144",
    "5901236": "0614145",
}

GLN_ALIAS_MAP: Dict[str, str] = {
    # partner internal location codes → canonical GLN URNs
    "WH-CHD-01": "urn:epc:id:sgln:0614141.00729.0",
    "WH-DEL-02": "urn:epc:id:sgln:0614143.00500.0",
    "WH-MUM-03": "urn:epc:id:sgln:0614145.01200.0",
}


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalize_internal_code(code: str, serial: str) -> Tuple[str, bool]:
    """Convert 'PROD-XXXX' → 'urn:epc:id:sgtin:company.item.serial'."""
    if code in INTERNAL_CODE_MAP:
        company, item = INTERNAL_CODE_MAP[code]
        return f"urn:epc:id:sgtin:{company}.{item}.{serial}", True
    return f"urn:epc:id:sgtin:UNKNOWN.UNKNOWN.{serial}", False


def _normalize_ean13(barcode: str, serial: str) -> Tuple[str, bool]:
    """Convert EAN-13 barcode → GS1 SGTIN URN."""
    if not re.fullmatch(r"\d{13}", barcode):
        return f"urn:epc:id:sgtin:INVALID.{barcode}.{serial}", False
    prefix7 = barcode[:7]
    item_ref = barcode[7:12]
    if prefix7 in EAN13_COMPANY_MAP:
        company = EAN13_COMPANY_MAP[prefix7]
        return f"urn:epc:id:sgtin:{company}.{item_ref}.{serial}", True
    return f"urn:epc:id:sgtin:UNKNOWN.{item_ref}.{serial}", False


def _normalize_gs1_urn(urn: str) -> Tuple[str, bool]:
    """Validate an existing GS1 URN; return as-is if well-formed."""
    pattern = r"^urn:epc:id:sgtin:\d+\.\d+\.\d+$"
    if re.match(pattern, urn):
        return urn, True
    return urn, False


def normalize_identifier(
    raw_id: str,
    partner: str,
    serial: str = "0001",
) -> Dict:
    """
    Normalise a raw product identifier from a given partner to GS1 SGTIN URN.
    Returns a dict with before/after/success/partner fields.
    """
    partner_info = PARTNER_PROFILES.get(partner, {})
    fmt = partner_info.get("format", "unknown")

    before = raw_id
    if fmt == "internal_code":
        after, ok = _normalize_internal_code(raw_id, serial)
    elif fmt == "ean13":
        after, ok = _normalize_ean13(raw_id, serial)
    elif fmt == "gs1_urn":
        after, ok = _normalize_gs1_urn(raw_id)
    else:
        after, ok = raw_id, False

    return {
        "partner": partner,
        "format": fmt,
        "before": before,
        "after": after,
        "success": ok,
        "changed": before != after,
    }


def normalize_location(alias: str) -> Tuple[str, bool]:
    """Map an internal warehouse alias → canonical GLN URN."""
    if alias in GLN_ALIAS_MAP:
        return GLN_ALIAS_MAP[alias], True
    if alias.startswith("urn:epc:id:sgln:"):
        return alias, True
    return alias, False


def run_normalization_demo() -> List[Dict]:
    """
    Run a demo over a mixed-format dataset and return results rows.
    """
    test_cases = [
        ("PROD-1234", "PartnerA", "2017"),
        ("PROD-2345", "PartnerA", "2018"),
        ("PROD-9999", "PartnerA", "0001"),   # unmapped → failure
        ("5901234123457", "PartnerB", "3001"),
        ("5901235654321", "PartnerB", "3002"),
        ("1234567890000", "PartnerB", "3003"),  # bad prefix → failure
        ("urn:epc:id:sgtin:0614145.107346.2017", "PartnerC", "4001"),
        ("urn:epc:id:sgtin:0614145.107347.2018", "PartnerC", "4002"),
        ("urn:epc:id:sgtin:BROKEN", "PartnerC", "4003"),  # malformed → failure
    ]
    results = []
    for raw_id, partner, serial in test_cases:
        row = normalize_identifier(raw_id, partner, serial)
        results.append(row)
    return results


if __name__ == "__main__":
    rows = run_normalization_demo()
    for r in rows:
        tag = "✅" if r["success"] else "❌"
        print(f"{tag} [{r['partner']}] {r['before']} → {r['after']}")
