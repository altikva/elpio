# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the identity.

import datetime as dt

import jwt
import pytest

from elpio.providers.identity import NullIdentityProvider, OIDCIdentityProvider, Principal

SECRET = "test-signing-secret-padded-to-32-bytes-min"
WRONG_SECRET = "wrong-secret-padded-to-32-bytes-minimum-len"


def _token(claims, secret=SECRET, **over):
    base = {
        "sub": "alice",
        "email": "alice@acme.io",
        "groups": ["devs"],
        "iss": "https://issuer.test",
        "aud": "elpio",
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5),
    }
    base.update(claims)
    base.update(over)
    return jwt.encode(base, secret, algorithm="HS256")


def _provider(**kw):
    kw.setdefault("signing_key", SECRET)
    kw.setdefault("algorithms", ["HS256"])
    kw.setdefault("issuer", "https://issuer.test")
    kw.setdefault("audience", "elpio")
    return OIDCIdentityProvider(**kw)


def test_requires_a_key_source():
    with pytest.raises(ValueError):
        OIDCIdentityProvider()


def test_authenticates_valid_token_to_principal():
    p = _provider().authenticate(_token({}))
    assert isinstance(p, Principal)
    assert p.subject == "alice"
    assert p.email == "alice@acme.io"
    assert p.groups == ["devs"]


def test_rejects_bad_signature():
    assert _provider().authenticate(_token({}, secret=WRONG_SECRET)) is None


def test_rejects_expired_token():
    expired = _token({}, exp=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1))
    assert _provider().authenticate(expired) is None


def test_rejects_wrong_audience():
    assert _provider().authenticate(_token({"aud": "someone-else"})) is None


def test_groups_claim_string_is_normalised():
    p = _provider(groups_claim="role").authenticate(_token({"role": "admin"}))
    assert p.groups == ["admin"]


def test_authorize_delegates_to_sar_reviewer():
    seen = {}

    def reviewer(principal, verb, resource):
        seen.update(subject=principal.subject, verb=verb, resource=resource)
        return verb == "create"

    prov = _provider(sar_reviewer=reviewer)
    principal = Principal(subject="bob", groups=["ops"])
    assert prov.authorize(principal, "create", "elpioservices") is True
    assert prov.authorize(principal, "delete", "elpioservices") is False
    assert seen == {"subject": "bob", "verb": "delete", "resource": "elpioservices"}


def test_resource_group_parsing():
    prov = _provider()
    assert prov._split_resource("elpioservices") == ("elpio.io", "elpioservices")
    assert prov._split_resource("apps/deployments") == ("apps", "deployments")
    assert prov._split_resource("core/secrets") == ("", "secrets")


def test_null_provider_allows_everything():
    np = NullIdentityProvider()
    who = np.authenticate("anything")
    assert who.subject == "dev"
    assert np.authorize(who, "delete", "elpioservices") is True


def test_jwks_uri_without_https_is_rejected():
    with pytest.raises(ValueError):
        OIDCIdentityProvider(
            jwks_uri="http://idp.acme.io/jwks",
            issuer="https://issuer.test",
            audience="elpio",
        )


def test_jwks_uri_allows_http_localhost_for_dev():
    OIDCIdentityProvider(
        jwks_uri="http://localhost:8080/jwks",
        issuer="https://issuer.test",
        audience="elpio",
    )


def test_jwks_uri_requires_issuer_and_audience():
    with pytest.raises(ValueError):
        OIDCIdentityProvider(jwks_uri="https://idp.acme.io/jwks", audience="elpio")
    with pytest.raises(ValueError):
        OIDCIdentityProvider(jwks_uri="https://idp.acme.io/jwks", issuer="https://issuer.test")


def test_signing_key_path_stays_lenient():
    # symmetric path is for tests: issuer/audience remain optional
    prov = OIDCIdentityProvider(signing_key=SECRET, algorithms=["HS256"])
    p = prov.authenticate(_token({}))
    assert p.subject == "alice"
