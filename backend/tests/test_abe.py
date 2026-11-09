"""Tests for the CP-ABE construction over BN254 pairings.

These exercise real pairings and therefore take a few seconds each -
that is the price of pure-Python py_ecc (documented in CRYPTOGRAPHY.md).
"""
from __future__ import annotations

import pytest

from app.crypto.abe import (
    ABEError,
    PolicyNotSatisfied,
    get_abe_authority,
    parse_policy,
)


@pytest.fixture()
def authority(isolated_env):
    return get_abe_authority()


POLICY = "(role:doctor AND dept:cardiology) OR role:admin"


def test_policy_parser_shapes():
    tree = parse_policy(POLICY)
    assert tree.kind == "thresh" and tree.t == 1  # top-level OR
    assert len(tree.children) == 2
    and_gate = tree.children[0]
    assert and_gate.t == 2 and len(and_gate.children) == 2


def test_bad_policies_rejected():
    with pytest.raises(ABEError):
        parse_policy("role:doctor AND")  # dangling
    with pytest.raises(ABEError):
        parse_policy("(role:doctor OR role:admin")  # unbalanced
    with pytest.raises(ABEError):
        parse_policy("role:doctor OR hacker:elite")  # outside universe


def test_authorized_key_decrypts(authority):
    ct = authority.encrypt(b"cardiac-notes: patient stable", POLICY)
    key = authority.keygen(["role:doctor", "dept:cardiology"])
    assert authority.decrypt(ct, key) == b"cardiac-notes: patient stable"


def test_admin_key_decrypts(authority):
    ct = authority.encrypt(b"lab-results", POLICY)
    key = authority.keygen(["role:admin"])
    assert authority.decrypt(ct, key) == b"lab-results"


def test_insufficient_attributes_rejected(authority):
    ct = authority.encrypt(b"secret", POLICY)
    key = authority.keygen(["role:doctor"])  # doctor but not cardiology
    with pytest.raises(PolicyNotSatisfied):
        authority.decrypt(ct, key)


def test_wrong_attribute_same_role_rejected(authority):
    """A neurologist's doctor key must NOT open cardiology-only records."""
    ct = authority.encrypt(b"secret", "role:doctor AND dept:cardiology")
    key = authority.keygen(["role:doctor", "dept:neurology"])
    with pytest.raises(PolicyNotSatisfied):
        authority.decrypt(ct, key)


def test_ciphertext_blob_not_plaintext_recoverable(authority):
    import base64

    ct = authority.encrypt(b"very-private", "role:admin")
    blob = base64.b64decode(ct["blob"])
    assert b"very-private" not in blob
    assert b"very-private" not in str(ct).encode()


def test_user_key_persistence_roundtrip(authority, isolated_env):
    authority.ensure_ready()
    issued = authority.issue_user_key("u-123", ["role:patient", "relation:self"])
    loaded = authority.load_user_key("u-123")
    ct = authority.encrypt(b"self-view", "role:patient OR role:admin")
    assert authority.decrypt(ct, loaded) == b"self-view"
    assert issued.attributes == loaded.attributes
