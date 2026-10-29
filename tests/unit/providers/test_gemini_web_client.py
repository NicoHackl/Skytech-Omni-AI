"""Brücke mit einer asynchronen Attrappe: Abbruch, Cookie-Ablage und temporäre Dateien."""

import asyncio
import importlib
import sys
import threading
from types import SimpleNamespace

import pytest

from providers import gemini_web_accounts as accounts
from providers import gemini_web_client as module
from providers.base_provider import Attachment


@pytest.fixture
def environment(monkeypatch):
    instances = []

    class FakeClient:
        def __init__(self, *args):
            self.account_status = 1000
            self.cookies = SimpleNamespace(jar=[])
            self.closed = False
            self.paths = []
            instances.append(self)

        async def init(self, **kwargs):
            self.cache_path = module._cache_path(None)

        def list_models(self):
            return [SimpleNamespace(model_name="gemini-pro", is_available=True)]

        def resolve_model(self, model):
            if model != "gemini-pro":
                raise ValueError("unbekannt")
            return model

        async def generate_content(self, prompt, **kwargs):
            self.temporary = kwargs["temporary"]
            self.paths = kwargs["files"] or []
            self.data = [path.read_bytes() for path in self.paths]
            assert all(path.stat().st_mode & 0o777 == 0o600 for path in self.paths)
            return SimpleNamespace(text='{"ok":true}')

        async def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_library", lambda: SimpleNamespace(GeminiClient=FakeClient))
    monkeypatch.setitem(
        sys.modules,
        "gemini_webapi.constants",
        SimpleNamespace(AccountStatus=SimpleNamespace(AVAILABLE=1000)),
    )
    bridge = module.GeminiWebClient()
    account = accounts.prepare_account("Beispiel", "synthetisch-a", "synthetisch-b")
    try:
        yield bridge, account, FakeClient, instances
    finally:
        bridge.shutdown()


def test_files_and_temporary_chat_and_reuse(environment):
    bridge, account, _, instances = environment
    attachment = Attachment("bild.png", "image/png", b"bilddaten")
    result = bridge.call(account, prompt="Test", attachments=[attachment])
    fake = instances[0]
    assert result["text"] == '{"ok":true}'
    assert fake.temporary is True
    assert fake.data == [b"bilddaten"]
    assert fake.cache_path == account.home / "session.json"
    assert all(not path.exists() for path in fake.paths)
    bridge.call(account, prompt="Neue unabhängige Anfrage")
    assert len(instances) == 1
    bridge.call(account, close=True)
    assert fake.closed
    assert not bridge._clients


def test_background_context_and_cookie_cache_are_isolated_per_account(environment):
    bridge, account, fake_type, instances = environment
    # Zwei ungeprüfte Konten brauchen hier nur verschiedene private Ablagen.
    accounts.add_account(account)
    second = accounts.prepare_account("Zweites", "synthetisch-c", "synthetisch-d")
    background_paths = []

    async def init(self, **kwargs):
        async def background():
            background_paths.append(module._cache_path(None))

        await asyncio.create_task(background())

    fake_type.init = init
    bridge.call(account)
    bridge.call(second)
    assert background_paths == [account.home / "session.json", second.home / "session.json"]
    assert len(instances) == 2


def test_timeout_cancels_and_cleans_uploads(environment):
    bridge, account, fake_type, instances = environment
    cancelled = threading.Event()

    async def generate(self, prompt, **kwargs):
        self.paths = kwargs["files"]
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    fake_type.generate_content = generate
    with pytest.raises(module.WebClientError) as error:
        bridge.call(
            account,
            prompt="Test",
            timeout=0.05,
            attachments=[Attachment("test.txt", "text/plain", b"Inhalt")],
        )
    assert error.value.kind == "timeout"
    assert cancelled.is_set()
    assert all(not path.exists() for path in instances[0].paths)
    assert instances[0].closed
    assert not bridge._clients


@pytest.mark.parametrize(
    "error_name,kind",
    [
        ("UsageLimitExceededError", "quota"),
        ("AuthError", "auth"),
        ("TemporarilyBlockedError", "blocked"),
        ("ModelInvalidError", "model"),
        ("TimeoutError", "timeout"),
        ("APIError", "failure"),
    ],
)
def test_library_errors_never_escape_or_leak(environment, error_name, kind, caplog):
    bridge, account, fake_type, instances = environment
    secret_marker = "SYNTHETISCHER-VERTRAULICHER-WERT"

    async def fail(self, *args, **kwargs):
        self.paths = kwargs["files"]
        raise type(error_name, (Exception,), {})(secret_marker)

    fake_type.generate_content = fail
    with pytest.raises(module.WebClientError) as error:
        bridge.call(account, prompt="Test", attachments=[Attachment("x.txt", "text/plain", b"x")])
    assert error.value.kind == kind
    assert secret_marker not in caplog.text + str(error.value)
    assert instances[0].closed
    assert all(not path.exists() for path in instances[0].paths)


def test_successful_guest_session_is_rejected(environment):
    bridge, account, fake_type, _ = environment

    async def init(self, **kwargs):
        self.account_status = 1016

    fake_type.init = init
    with pytest.raises(module.WebClientError) as error:
        bridge.call(account)
    assert error.value.kind == "auth"


def test_loader_patches_both_import_sites_before_any_cookie_use(monkeypatch, tmp_path):
    disabled = []
    package = SimpleNamespace(logger=SimpleNamespace(disable=disabled.append))
    rotation, access = SimpleNamespace(), SimpleNamespace()
    modules = {
        "gemini_webapi": package,
        "gemini_webapi.utils.rotate_1psidts": rotation,
        "gemini_webapi.utils.get_access_token": access,
    }
    real_import = importlib.import_module
    monkeypatch.setattr(module, "version", lambda name: "2.1.1")
    monkeypatch.setattr(module.importlib, "import_module", lambda name: modules[name])
    # Bei einem Versionswechsel wird ausdrücklich nicht mit unsicherem Original weitergemacht.
    loader = module._library
    token = module._CACHE_HOME.set(tmp_path)
    try:
        assert loader() is package
        assert rotation._get_cookies_cache_path(None) == tmp_path / "session.json"
        assert access._get_cookies_cache_path(None) == tmp_path / "session.json"
        assert rotation._get_cookie_cache_dir() == tmp_path
        assert disabled == ["gemini_webapi"]
        monkeypatch.setattr(module, "version", lambda name: "9.9.9")
        with pytest.raises(module.WebClientError):
            loader()
    finally:
        module._CACHE_HOME.reset(token)
        monkeypatch.setattr(module.importlib, "import_module", real_import)
