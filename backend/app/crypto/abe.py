"""Ciphertext-Policy Attribute-Based Encryption (CP-ABE) over BN254 pairings.

REAL pairing-based construction (no pseudocode), built on py_ecc's BN254
curve (the same curve used in production ZK systems). Groups:

    G1 = affine FQ points,  G2 = affine FQ2 points,  GT = FQ12
    pairing(Q in G2, P in G1) -> GT, bilinear: e(aQ, bP) = e(Q,P)^{ab}

Construction (small-universe Waters/GPSW-style CP-ABE, LSSS policies):

    Setup:  alpha, a, {t_j} <- Zr
            PK  = (g1, g1^a, Y = e(g2,g1)^alpha, {g1^{t_j}})
            MSK = (alpha, a, {t_j})
    KeyGen(S): r, {r_j} <- Zr
            D   = g2^{(alpha + r)/a}
            K_j = g2^{r + t_j r_j},  K'_j = g2^{r_j}        (per j in S)
    Encrypt(m, policy tree, secret s):
            shares lambda_l via Shamir thresholds top-down (AND = 2-of-2,
            OR = 1-of-2 over child positions x = 1..n)
            C0 = m * Y^s           (m random in GT; DEM key = KDF(m))
            C1 = g1^{a s}
            row_l = (c_l = g1^{lambda_l}, c'_l = g1^{t_j lambda_l})
    Decrypt (key attributes satisfy policy -> Lagrange coeffs omega_l,
             sum omega_l lambda_l = s):
            e(C1, D)                         = Y^s * e^{rs}
            V_l = e(c_l, K_j) / e(c'_l,K'_j) = e^{lambda_l r}
            =>  Y^s = e(C1,D) / prod V_l^{omega_l};   m = C0 / Y^s

Security rests on the Decisional Bilinear Diffie-Hellman assumption.
NOTE: educational-grade implementation for the PS02 capstone - parameter
choices and side channels have NOT received a production audit.

py_ecc pairings are pure Python (~tens of ms each): policies here stay
small (<= 8 leaves) which keeps encryption ~0.5 s and decryption ~2 s.
"""
from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from py_ecc.bn128 import G1, G2, FQ, FQ2, FQ12, curve_order, field_modulus, pairing

from app.core.logging import get_logger
from app.crypto.aes_gcm import decrypt_bytes, encrypt_bytes
from app.crypto.integrity import sha256_bytes
from app.crypto.key_manager import get_key_manager

log = get_logger(__name__)

Zr = curve_order  # order of all exponent groups we use

# Fixed small attribute universe (small-universe ABE). Roles/departments/
# record categories map to secret per-attribute exponents t_j at setup.
ATTRIBUTE_UNIVERSE: list[str] = [
    "role:admin", "role:doctor", "role:patient", "role:auditor",
    "org:nitsurat-hospital", "org:partner-clinic",
    "dept:cardiology", "dept:neurology", "dept:nephrology", "dept:general",
    "cat:cardiac", "cat:labs", "cat:mental", "cat:general", "cat:imaging",
    "relation:self", "relation:primary-physician",
]


class ABEError(Exception):
    """Generic ABE failure (bad parameters, malformed ciphertext...)."""


class PolicyNotSatisfied(ABEError):
    """The user's attributes do not satisfy the ciphertext policy."""


# --------------------------------------------------------------------------
# Field / group arithmetic helpers (ints <-> py_ecc objects)
# --------------------------------------------------------------------------
def _rand_zr() -> int:
    return secrets.randbelow(Zr)


def _g1_mul(p: tuple, k: int) -> tuple:
    from py_ecc.bn128 import multiply as _m

    return _m(p, k % Zr)


def _g2_mul(q: tuple, k: int) -> tuple:
    from py_ecc.bn128 import multiply as _m

    return _m(q, k % Zr)


def _g1_add(p: tuple, q: tuple) -> tuple:
    from py_ecc.bn128 import add as _a

    return _a(p, q)


def _pair(q2: tuple, p1: tuple) -> FQ12:
    return pairing(q2, p1)


def gt_pow(base: FQ12, exponent: int) -> FQ12:
    """Square-and-multiply in GT (pairing outputs live in the order-Zr
    subgroup of FQ12*, so exponents are reduced mod Zr)."""
    e = exponent % Zr
    result = FQ12.one()
    if e == 0:
        return result
    b = base
    while True:
        if e & 1:
            result = result * b
        e >>= 1
        if e == 0:
            break
        b = b * b
    return result


def gt_inv(a: FQ12) -> FQ12:
    """a^{-1} = a^{Zr-1} for elements of the order-Zr subgroup."""
    return gt_pow(a, Zr - 1)


def gt_div(a: FQ12, b: FQ12) -> FQ12:
    return a * gt_inv(b)


# ---- serialization --------------------------------------------------------
def _fq_ints(v: Any) -> list[int]:
    """Recursively flatten an FQ/FQ2/FQ12 into a list of ints."""
    if hasattr(v, "n"):  # plain FQ
        return [v.n]
    if hasattr(v, "coeffs"):  # FQ2 / FQ12
        out: list[int] = []
        for c in v.coeffs:
            out.extend(_fq_ints(c))
        return out
    raise ABEError(f"cannot serialize field element {type(v)}")


def p1_to_json(p: tuple) -> list[int]:
    return _fq_ints(p[0]) + _fq_ints(p[1])


def p1_from_json(vals: list[int]) -> tuple:
    return (FQ(vals[0]), FQ(vals[1]))


def p2_to_json(q: tuple) -> list[int]:
    return _fq_ints(q[0]) + _fq_ints(q[1])


def p2_from_json(vals: list[int]) -> tuple:
    return (FQ2((vals[0], vals[1])), FQ2((vals[2], vals[3])))


def gt_to_json(g: FQ12) -> list[int]:
    return _fq_ints(g)


def gt_from_json(vals: list[int]) -> FQ12:
    return FQ12(tuple(FQ(v) for v in vals))


def gt_kdf(g: FQ12) -> bytes:
    """Deterministic 32-byte DEM key derived from a GT element."""
    return bytes.fromhex(sha256_bytes(",".join(str(v) for v in gt_to_json(g)).encode()))


# --------------------------------------------------------------------------
# Policy parsing:  "(role:doctor AND dept:cardiology) OR role:admin"
# --------------------------------------------------------------------------
@dataclass
class PolicyNode:
    """Attribute leaf or threshold gate (AND = thresh(2,2), OR = thresh(1,2))."""

    kind: str  # "attr" | "thresh"
    name: Optional[str] = None
    t: int = 1  # threshold (for "thresh")
    children: list["PolicyNode"] = field(default_factory=list)
    leaf_id: int = -1  # unique per leaf, assigned in parse order

    def __str__(self) -> str:
        if self.kind == "attr":
            return str(self.name)
        joiner = " AND " if self.t == len(self.children) and self.t > 1 else (
            " OR " if self.t == 1 and len(self.children) > 1 else f"{self.t}-of-"
        )
        inner = joiner.join(str(c) for c in self.children)
        return f"({inner})"


class _PolicyParser:
    """Recursive-descent parser: or_expr := and_expr (OR and_expr)* etc."""

    def __init__(self, text: str) -> None:
        self.tokens = self._tokenize(text)
        self.pos = 0
        self.leaf_counter = 0

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        out: list[str] = []
        for raw in text.replace("(", " ( ").replace(")", " ) ").split():
            low = raw.lower()
            if low in ("and", "or"):
                out.append(low)
            else:
                out.append(raw)
        return out

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> str:
        tok = self._peek()
        if tok is None:
            raise ABEError("policy ended unexpectedly")
        self.pos += 1
        return tok

    def parse(self) -> PolicyNode:
        node = self._or_expr()
        if self._peek() is not None:
            raise ABEError(f"unexpected token {self._peek()!r} in policy")
        return node

    def _or_expr(self) -> PolicyNode:
        node = self._and_expr()
        children = [node]
        while self._peek() == "or":
            self._next()
            children.append(self._and_expr())
        if len(children) == 1:
            return node
        return PolicyNode(kind="thresh", t=1, children=children)

    def _and_expr(self) -> PolicyNode:
        node = self._atom()
        children = [node]
        while self._peek() == "and":
            self._next()
            children.append(self._atom())
        if len(children) == 1:
            return node
        return PolicyNode(kind="thresh", t=len(children), children=children)

    def _atom(self) -> PolicyNode:
        tok = self._next()
        if tok == "(":
            node = self._or_expr()
            if self._next() != ")":
                raise ABEError("missing closing parenthesis in policy")
            return node
        if tok in ("and", "or", ")"):
            raise ABEError(f"unexpected keyword {tok!r} in policy")
        if ":" not in tok:
            raise ABEError(
                f"attribute {tok!r} must look like 'namespace:value' "
                f"(e.g. role:doctor)"
            )
        if tok not in ATTRIBUTE_UNIVERSE:
            raise ABEError(
                f"attribute {tok!r} not in the universe {ATTRIBUTE_UNIVERSE}"
            )
        node = PolicyNode(kind="attr", name=tok, leaf_id=self.leaf_counter)
        self.leaf_counter += 1
        return node


def parse_policy(text: str) -> PolicyNode:
    """Parse a policy string into a threshold tree (leaves get stable ids)."""
    if not text or not text.strip():
        raise ABEError("empty policy")
    return _PolicyParser(text).parse()


# --------------------------------------------------------------------------
# Share assignment / reconstruction coefficients (LSSS via tree-Shamir)
# --------------------------------------------------------------------------
def _assign_shares(
    node: PolicyNode, secret: int
) -> list[tuple[int, str, int]]:  # (leaf_id, attr, lambda)
    """Top-down Shamir sharing: threshold(t,n) uses a degree-(t-1) polynomial
    with p(0)=secret; child i receives lambda_i = p(i) for x = 1..n."""
    if node.kind == "attr":
        return [(node.leaf_id, str(node.name), secret)]
    n = len(node.children)
    if node.t < 1 or node.t > n:
        raise ABEError("invalid threshold gate")
    coeffs = [secret] + [_rand_zr() for _ in range(node.t - 1)]
    leaves: list[tuple[int, str, int]] = []
    for i, child in enumerate(node.children, start=1):
        lam = sum(c * pow(i, power, Zr) for power, c in enumerate(coeffs)) % Zr
        leaves.extend(_assign_shares(child, lam))
    return leaves


def _lagrange_at_zero(xs: list[int]) -> list[int]:
    """L_i(0) = prod_{j != i} x_j / (x_j - x_i)  (mod Zr)."""
    out = []
    for i, xi in enumerate(xs):
        num, den = 1, 1
        for j, xj in enumerate(xs):
            if i == j:
                continue
            num = num * xj % Zr
            den = den * ((xj - xi) % Zr) % Zr
        out.append(num * pow(den, -1, Zr) % Zr)
    return out


def _reconstruction_coeffs(
    node: PolicyNode, attrs: set[str]
) -> dict[int, int]:  # leaf_id -> omega (0-pruned when unsatisfied)
    if node.kind == "attr":
        return {node.leaf_id: 1} if node.name in attrs else {}
    child_results = [_reconstruction_coeffs(c, attrs) for c in node.children]
    satisfied = [(i + 1, res) for i, res in enumerate(child_results) if res]
    if len(satisfied) < node.t:
        return {}
    chosen = satisfied[: node.t]  # deterministic: first t satisfied children
    weights = _lagrange_at_zero([x for x, _ in chosen])
    merged: dict[int, int] = {}
    for (_x, res), w in zip(chosen, weights):
        for leaf_id, coeff in res.items():
            merged[leaf_id] = merged.get(leaf_id, 0) + coeff * w % Zr
    return merged


# --------------------------------------------------------------------------
# Authority: setup / keygen / encrypt / decrypt
# --------------------------------------------------------------------------
@dataclass
class ABEPublicKey:
    g1: tuple
    g1a: tuple                 # g1^a
    Y: FQ12                    # e(g2, g1)^alpha
    attr_pubs: dict[str, tuple]  # attr -> g1^{t_attr}

    def to_json(self) -> dict[str, Any]:
        return {
            "g1": p1_to_json(self.g1),
            "g1a": p1_to_json(self.g1a),
            "Y": gt_to_json(self.Y),
            "attr_pubs": {a: p1_to_json(p) for a, p in self.attr_pubs.items()},
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ABEPublicKey":
        return ABEPublicKey(
            g1=p1_from_json(data["g1"]),
            g1a=p1_from_json(data["g1a"]),
            Y=gt_from_json(data["Y"]),
            attr_pubs={a: p1_from_json(p) for a, p in data["attr_pubs"].items()},
        )


@dataclass
class ABEPrivateKey:
    D: tuple                                  # g2^{(alpha+r)/a}
    K: dict[str, tuple]                       # attr -> g2^{r + t_j r_j}
    Kp: dict[str, tuple]                      # attr -> g2^{r_j}
    attributes: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "D": p2_to_json(self.D),
            "K": {a: p2_to_json(v) for a, v in self.K.items()},
            "Kp": {a: p2_to_json(v) for a, v in self.Kp.items()},
            "attributes": self.attributes,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ABEPrivateKey":
        return ABEPrivateKey(
            D=p2_from_json(data["D"]),
            K={a: p2_from_json(v) for a, v in data["K"].items()},
            Kp={a: p2_from_json(v) for a, v in data["Kp"].items()},
            attributes=list(data["attributes"]),
        )


class ABEAuthority:
    """Trusted attribute authority. The MSK never leaves this process
    unencrypted: it is persisted as an AES-256-GCM blob under the HKDF
    ``abe:wrap`` key derived from the system master key."""

    def __init__(self) -> None:
        from app.core.config import get_settings

        self.secrets_dir = Path(get_settings().SECRETS_DIR)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir = self.secrets_dir / "abe_keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self._msk: Optional[dict[str, Any]] = None
        self._pk: Optional[ABEPublicKey] = None

    # ---- persistence ----
    @property
    def msk_path(self) -> Path:
        return self.secrets_dir / "abe_msk.json.enc"

    @property
    def pk_path(self) -> Path:
        return self.secrets_dir / "abe_pk.json"

    def _det_zr(self, label: str) -> int:
        wrap = get_key_manager().abe_wrap_key
        digest = sha256_bytes(wrap + b":" + label.encode("utf-8"))
        val = int(digest, 16) % (Zr - 1)
        return val + 1

    def _setup(self) -> None:
        alpha, a = self._det_zr("alpha"), self._det_zr("a")
        t_attrs = {attr: self._det_zr(f"attr:{attr}") for attr in ATTRIBUTE_UNIVERSE}
        self._msk = {"alpha": alpha, "a": a, "t": t_attrs}
        g1a = _g1_mul(G1, a)
        Y = _pair(G2, G1)  # e(g2, g1)
        Y_alpha = gt_pow(Y, alpha)
        self._pk = ABEPublicKey(
            g1=G1,
            g1a=g1a,
            Y=Y_alpha,
            attr_pubs={attr: _g1_mul(G1, t) for attr, t in t_attrs.items()},
        )
        wrap = get_key_manager().abe_wrap_key
        msk_blob = encrypt_bytes(
            wrap,
            json.dumps(
                {"alpha": alpha, "a": a, "t": t_attrs}, sort_keys=True
            ).encode(),
        )
        self.msk_path.write_bytes(msk_blob)
        self.pk_path.write_text(json.dumps(self._pk.to_json()))
        log.info("ABE authority bootstrapped (%d attributes)", len(t_attrs))

    def ensure_ready(self) -> None:
        if self._msk is not None:
            return
        if self.msk_path.exists() and self.pk_path.exists():
            wrap = get_key_manager().abe_wrap_key
            raw = json.loads(decrypt_bytes(wrap, self.msk_path.read_bytes()))
            self._msk = {
                "alpha": int(raw["alpha"]),
                "a": int(raw["a"]),
                "t": {k: int(v) for k, v in raw["t"].items()},
            }
            self._pk = ABEPublicKey.from_json(json.loads(self.pk_path.read_text()))
        else:
            self._setup()

    @property
    def pk(self) -> ABEPublicKey:
        self.ensure_ready()
        return self._pk  # type: ignore[return-value]

    # ---- key generation ----
    def keygen(self, attributes: list[str]) -> ABEPrivateKey:
        """Issue a private key bound to ``attributes``."""
        self.ensure_ready()
        msk = self._msk
        unknown = [a for a in attributes if a not in ATTRIBUTE_UNIVERSE]
        if unknown:
            raise ABEError(f"attributes outside universe: {unknown}")
        r = _rand_zr()
        a_inv = pow(msk["a"], -1, Zr)
        D = _g2_mul(G2, (msk["alpha"] + r) % Zr * a_inv % Zr)
        K: dict[str, tuple] = {}
        Kp: dict[str, tuple] = {}
        for attr in attributes:
            rj = _rand_zr()
            exp_K = (r + msk["t"][attr] * rj) % Zr
            K[attr] = _g2_mul(G2, exp_K)
            Kp[attr] = _g2_mul(G2, rj)
        return ABEPrivateKey(D=D, K=K, Kp=Kp, attributes=list(attributes))

    def issue_user_key(self, user_id: str, attributes: list[str]) -> ABEPrivateKey:
        """Generate AND persist (encrypted at rest) a user's ABE key."""
        key = self.keygen(attributes)
        wrap = get_key_manager().abe_wrap_key
        blob = encrypt_bytes(wrap, json.dumps(key.to_json()).encode())
        (self.keys_dir / f"{user_id}.json.enc").write_bytes(blob)
        return key

    def load_user_key(self, user_id: str) -> ABEPrivateKey:
        path = self.keys_dir / f"{user_id}.json.enc"
        if not path.exists():
            raise ABEError(f"no ABE key issued for user {user_id}")
        wrap = get_key_manager().abe_wrap_key
        data = json.loads(decrypt_bytes(wrap, path.read_bytes()))
        return ABEPrivateKey.from_json(data)

    # ---- encryption ----
    def encrypt(self, plaintext: bytes, policy: str) -> dict[str, Any]:
        """Encrypt ``plaintext`` under ``policy``; returns a JSON-able ct."""
        self.ensure_ready()
        pk = self._pk
        tree = parse_policy(policy)
        # Random GT element m; DEM key derived from it. Attacker without a
        # satisfying key cannot reconstruct m, hence cannot get the DEM key.
        z = _rand_zr()
        m = gt_pow(_pair(G2, pk.g1), z)
        dem_key = gt_kdf(m)

        s = _rand_zr()
        Ys = gt_pow(pk.Y, s)
        C0 = m * Ys
        C1 = _g1_mul(pk.g1a, s)  # g1^{a*s}
        rows = []
        for leaf_id, attr, lam in _assign_shares(tree, s):
            rows.append(
                {
                    "leaf_id": leaf_id,
                    "attr": attr,
                    "c": p1_to_json(_g1_mul(pk.g1, lam)),
                    "cp": p1_to_json(_g1_mul(pk.attr_pubs[attr], lam)),
                }
            )
        blob = encrypt_bytes(dem_key, plaintext)
        return {
            "scheme": "cp-abe-bn254-v1",
            "policy": policy,
            "C0": gt_to_json(C0),
            "C1": p1_to_json(C1),
            "rows": rows,
            "blob": base64.b64encode(blob).decode(),
        }

    # ---- decryption ----
    def decrypt(self, ct: dict[str, Any], key: ABEPrivateKey) -> bytes:
        """Recover the plaintext iff ``key`` satisfies the embedded policy."""
        self.ensure_ready()
        if ct.get("scheme") != "cp-abe-bn254-v1":
            raise ABEError("unsupported ciphertext scheme")
        tree = parse_policy(ct["policy"])
        coeffs = _reconstruction_coeffs(tree, set(key.attributes))
        if not coeffs:
            raise PolicyNotSatisfied(
                f"attributes {key.attributes} do not satisfy policy "
                f"'{ct['policy']}'"
            )
        C1 = p1_from_json(ct["C1"])
        # e(C1, D) = Y^s * e^{rs}
        e_CD = _pair(key.D, C1)
        rows_by_leaf = {r["leaf_id"]: r for r in ct["rows"]}
        prod = FQ12.one()
        for leaf_id, omega in coeffs.items():
            row = rows_by_leaf[leaf_id]
            attr = row["attr"]
            c = p1_from_json(row["c"])
            cp = p1_from_json(row["cp"])
            # V = e(c, K_attr) / e(c', K'_attr) = e^{lambda_l r}
            num = _pair(key.K[attr], c)
            den = _pair(key.Kp[attr], cp)
            V = gt_div(num, den)
            prod = prod * gt_pow(V, omega)
        Ys = gt_div(e_CD, prod)          # Y^s = e(C1,D) / prod V^omega
        m = gt_div(gt_from_json(ct["C0"]), Ys)
        dem_key = gt_kdf(m)
        blob = base64.b64decode(ct["blob"])
        return decrypt_bytes(dem_key, blob)


_AUTHORITY: Optional[ABEAuthority] = None


def get_abe_authority() -> ABEAuthority:
    global _AUTHORITY
    if _AUTHORITY is None:
        _AUTHORITY = ABEAuthority()
    return _AUTHORITY


def self_test() -> None:
    """Fast sanity check used by the test-suite (small policy)."""
    auth = get_abe_authority()
    policy = "(role:doctor AND dept:cardiology) OR role:admin"
    ct = auth.encrypt(b"kodek-test", policy)
    good = auth.keygen(["role:doctor", "dept:cardiology"])
    assert auth.decrypt(ct, good) == b"kodek-test"
    try:
        auth.decrypt(ct, auth.keygen(["role:doctor"]))
        raise AssertionError("policy enforcement failed")
    except PolicyNotSatisfied:
        pass


# keep unused-import linters honest
_ = field_modulus
