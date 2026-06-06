"""
MODULE 4 — Secure Merkle Proof Generator
Builds a SHA-256 Merkle tree over all ACCEPTED events,
generates per-event proof bundles, and verifies them.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple


# ── Hashing helpers ───────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _hash_event(event: Dict) -> str:
    """Deterministic hash of an EPCIS event (excludes _meta)."""
    clean = {k: v for k, v in event.items() if k != "_meta"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def _hash_pair(left: str, right: str) -> str:
    return _sha256(left + right)


# ── Merkle tree builder ───────────────────────────────────────────────────────

class MerkleTree:
    """Simple binary Merkle tree over a list of leaf hashes."""

    def __init__(self, leaves: List[str]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf.")
        # Pad to even count
        padded = leaves[:] if len(leaves) % 2 == 0 else leaves + [leaves[-1]]
        self.leaves  = leaves           # original (may be odd-length)
        self._layers = self._build(padded)

    def _build(self, layer: List[str]) -> List[List[str]]:
        layers = [layer]
        while len(layer) > 1:
            if len(layer) % 2 != 0:
                layer = layer + [layer[-1]]
            parent = [_hash_pair(layer[i], layer[i + 1])
                      for i in range(0, len(layer), 2)]
            layers.append(parent)
            layer = parent
        return layers

    @property
    def root(self) -> str:
        return self._layers[-1][0]

    def proof(self, index: int) -> List[Dict[str, str]]:
        """Return the Merkle proof path for leaf at `index`."""
        path = []
        idx = index
        for layer in self._layers[:-1]:
            # The stored layer is always even-padded (built that way in _build)
            if idx % 2 == 0:
                sibling_idx = idx + 1
                direction   = "right"
            else:
                sibling_idx = idx - 1
                direction   = "left"
            # guard: sibling may be the duplicate-padding entry
            sibling = layer[sibling_idx] if sibling_idx < len(layer) else layer[idx]
            path.append({"hash": sibling, "direction": direction})
            idx //= 2
        return path


def _verify_proof(leaf_hash: str, proof_path: List[Dict[str, str]], root: str) -> bool:
    """Walk the proof path and confirm it reaches `root`."""
    current = leaf_hash
    for step in proof_path:
        sibling = step["hash"]
        if step["direction"] == "right":
            current = _hash_pair(current, sibling)
        else:
            current = _hash_pair(sibling, current)
    return current == root


# ── Gateway signing (simulated) ───────────────────────────────────────────────

GATEWAY_KEY = "GATEWAY-SECRET-KEY-2026"     # would be an ECDSA key in production


def _sign(data: str) -> str:
    """Simulate an HMAC-SHA256 signature with the gateway key."""
    import hmac
    return hmac.new(GATEWAY_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()


# ── Public API ────────────────────────────────────────────────────────────────

def build_merkle_tree(accepted_events: List[Dict]) -> Tuple[MerkleTree, List[str]]:
    """
    Hash each event and build the Merkle tree.
    Returns (MerkleTree, [leaf_hashes]).
    """
    leaf_hashes = [_hash_event(ev["raw_event"]) for ev in accepted_events]
    tree = MerkleTree(leaf_hashes)
    return tree, leaf_hashes


def generate_proof_bundle(
    event_record: Dict,
    leaf_hash: str,
    tree: MerkleTree,
    leaf_index: int,
) -> Dict:
    """Build and sign a proof bundle for a single accepted event."""
    proof_path = tree.proof(leaf_index)
    payload = leaf_hash + tree.root
    return {
        "eventID":    event_record["eventID"],
        "eventHash":  leaf_hash,
        "merkleRoot": tree.root,
        "proofPath":  proof_path,
        "leafIndex":  leaf_index,
        "signature":  _sign(payload),
        "timestamp":  event_record["eventTime"],
    }


def verify_proof_bundle(bundle: Dict) -> bool:
    """Return True if the bundle's proof is valid and the signature matches."""
    leaf_hash   = bundle["eventHash"]
    root        = bundle["merkleRoot"]
    proof_path  = bundle["proofPath"]
    expected_sig = _sign(leaf_hash + root)
    proof_valid  = _verify_proof(leaf_hash, proof_path, root)
    sig_valid    = bundle["signature"] == expected_sig
    return proof_valid and sig_valid


def build_all_proof_bundles(accepted_events: List[Dict]) -> Tuple[MerkleTree, List[Dict]]:
    """Convenience: build tree + all proof bundles in one call."""
    tree, leaf_hashes = build_merkle_tree(accepted_events)
    bundles = []
    for i, (ev, lh) in enumerate(zip(accepted_events, leaf_hashes)):
        bundles.append(generate_proof_bundle(ev, lh, tree, i))
    return tree, bundles


def run_verification_demo(bundles: List[Dict]) -> List[Dict]:
    """
    Verify all valid bundles and a set of tampered clones.
    Returns a list of verification result rows.
    """
    results = []
    # Valid bundles
    for b in bundles[:5]:
        ok = verify_proof_bundle(b)
        results.append({"eventID": b["eventID"], "tampered": False, "verified": ok})

    # Tampered: flip one byte in eventHash
    for b in bundles[:3]:
        import copy
        bad = copy.deepcopy(b)
        bad["eventHash"] = bad["eventHash"][:-1] + ("0" if bad["eventHash"][-1] != "0" else "1")
        ok = verify_proof_bundle(bad)
        results.append({"eventID": b["eventID"] + "_TAMPERED", "tampered": True, "verified": ok})

    return results


if __name__ == "__main__":
    # Quick smoke test
    fake_events = [
        {"eventID": f"EVT-{i:03d}", "eventTime": "2026-06-04T10:00:00Z",
         "raw_event": {"eventID": f"EVT-{i:03d}", "data": f"payload_{i}"}}
        for i in range(8)
    ]
    tree, bundles = build_all_proof_bundles(fake_events)
    print(f"Merkle root: {tree.root}")
    for b in bundles:
        ok = verify_proof_bundle(b)
        print(f"  {b['eventID']} → {'PASS' if ok else 'FAIL'}")
