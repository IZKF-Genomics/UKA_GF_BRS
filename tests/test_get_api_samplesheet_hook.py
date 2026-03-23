from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import http
import sys
import types


def test_hook_prints_api_detail_for_request_404(tmp_path: Path, monkeypatch, capsys):
    brs_root = Path.cwd()
    sys.path.insert(0, str(brs_root))

    from hooks.get_api_samplesheet import main as hook_main  # type: ignore

    out_dir = tmp_path / "adhoc"
    out_dir.mkdir()
    rendered = out_dir / "samplesheet.csv"
    rendered.write_text("rendered\n")

    class Response:
        def __init__(self, status_code: int, payload=None, content: bytes = b""):
            self.status_code = status_code
            self._payload = payload
            self.content = content

        def json(self):
            if self._payload is None:
                raise ValueError("no json")
            return self._payload

    requests_mod = types.ModuleType("requests")
    auth_mod = types.ModuleType("requests.auth")

    responses = [
        Response(http.HTTPStatus.NOT_FOUND, {"detail": "No samples found for flowcell: HHT35DRX7"}),
        Response(http.HTTPStatus.NOT_FOUND, {"detail": "No samples found for request: 5499"}),
    ]

    def fake_get(url, auth=None, timeout=None):
        return responses.pop(0)

    class HTTPBasicAuth:
        def __init__(self, user: str, password: str):
            self.user = user
            self.password = password

    requests_mod.get = fake_get
    auth_mod.HTTPBasicAuth = HTTPBasicAuth
    monkeypatch.setitem(sys.modules, "requests", requests_mod)
    monkeypatch.setitem(sys.modules, "requests.auth", auth_mod)

    ctx = SimpleNamespace(
        params={
            "use_api_samplesheet": True,
            "bcl_dir": "/data/raw/novaseq_A01742/260320_A01742_0619_AHHT35DRX7/",
            "agendo_id": "5499",
            "gf_api_name": "user",
            "gf_api_pass": "pass",
        },
        project=None,
        cwd=str(out_dir),
        project_dir=str(tmp_path),
        template=SimpleNamespace(id="demux_bclconvert"),
    )

    hook_main(ctx)
    captured = capsys.readouterr()

    assert rendered.read_text() == "rendered\n"
    assert "No samples found for request: 5499" in captured.out
    assert ctx.params["flowcell_id"] == "HHT35DRX7"
