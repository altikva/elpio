# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the service model.

from elpio.models.service import ElpioServiceSpec, ImageRef


def test_defaults_are_scale_to_zero():
    spec = ElpioServiceSpec.from_cr({"image": {"repository": "nginx"}})
    assert spec.scaling.minScale == 0  # Cloud Run semantics by default
    assert spec.scaling.metric == "concurrency"
    assert spec.port == 8080
    assert spec.ingress.enabled is True


def test_image_accepts_string():
    spec = ElpioServiceSpec.from_cr({"image": "ghcr.io/acme/api:1.2.3"})
    assert spec.image.repository == "ghcr.io/acme/api"
    assert spec.image.tag == "1.2.3"
    assert str(spec.image) == "ghcr.io/acme/api:1.2.3"


def test_image_object_without_tag():
    img = ImageRef.coerce({"repository": "nginx"})
    assert str(img) == "nginx"


def test_env_and_resources_parse():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "nginx:1",
            "env": [{"name": "A", "value": "1"}],
            "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}},
        }
    )
    assert spec.env[0].name == "A"
    assert spec.resources.requests.cpu == "100m"
