"""Offline unit tests for mybk_planner.env (filesystem via tmp_path, OS env
via monkeypatch — no network, no real user env leaks)."""

import pytest

from mybk_planner import env

PRIMARY = "MYBK_PLANNER_TEST_PRIMARY"
ALIAS = "MYBK_PLANNER_TEST_ALIAS"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Guarantee the test variable names are not set in the real OS env."""
    monkeypatch.delenv(PRIMARY, raising=False)
    monkeypatch.delenv(ALIAS, raising=False)


class TestLoadEnvFile:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert env.load_env_file(tmp_path / "nope.env") == {}

    def test_none_and_empty_path_return_empty_dict(self):
        assert env.load_env_file(None) == {}
        assert env.load_env_file("") == {}

    def test_parses_key_value_pairs(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("USER=alice\nPASS=s3cret\n", encoding="utf-8")
        assert env.load_env_file(f) == {"USER": "alice", "PASS": "s3cret"}

    def test_skips_blanks_and_comments(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\n\n   \nKEY=1\n#KEY=2\n", encoding="utf-8")
        assert env.load_env_file(f) == {"KEY": "1"}

    def test_strips_quotes_and_whitespace(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text(
            'DOUBLE="quoted value"\n'
            "SINGLE='also quoted'\n"
            "  SPACED  =  padded  \n",
            encoding="utf-8",
        )
        assert env.load_env_file(f) == {
            "DOUBLE": "quoted value",
            "SINGLE": "also quoted",
            "SPACED": "padded",
        }

    def test_value_may_contain_equals_sign(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("TOKEN=abc=def==\nLINE_WITHOUT_EQUALS\n",
                     encoding="utf-8")
        assert env.load_env_file(f) == {"TOKEN": "abc=def=="}

    def test_accepts_str_path(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("K=V\n", encoding="utf-8")
        assert env.load_env_file(str(f)) == {"K": "V"}


class TestResolve:
    def test_cli_beats_env_and_file(self, monkeypatch):
        monkeypatch.setenv(PRIMARY, "from-env")
        file_vars = {PRIMARY: "from-file"}
        assert env.resolve(PRIMARY, file_vars, cli_value="from-cli") == \
            "from-cli"

    def test_env_beats_file(self, monkeypatch):
        monkeypatch.setenv(PRIMARY, "from-env")
        file_vars = {PRIMARY: "from-file"}
        assert env.resolve(PRIMARY, file_vars) == "from-env"

    def test_falls_back_to_file(self):
        assert env.resolve(PRIMARY, {PRIMARY: "from-file"}) == "from-file"

    def test_returns_none_when_unset(self):
        assert env.resolve(PRIMARY, {}) is None

    def test_alias_fallback_in_os_env(self, monkeypatch):
        monkeypatch.setenv(ALIAS, "legacy-env")
        assert env.resolve(PRIMARY, {}, aliases=(ALIAS,)) == "legacy-env"

    def test_alias_fallback_in_file(self):
        file_vars = {ALIAS: "legacy-file"}
        assert env.resolve(PRIMARY, file_vars, aliases=(ALIAS,)) == \
            "legacy-file"

    def test_primary_key_wins_over_alias(self, monkeypatch):
        monkeypatch.setenv(PRIMARY, "primary-env")
        monkeypatch.setenv(ALIAS, "alias-env")
        file_vars = {PRIMARY: "primary-file", ALIAS: "alias-file"}
        assert env.resolve(PRIMARY, file_vars, aliases=(ALIAS,)) == \
            "primary-env"
        assert env.resolve(PRIMARY, file_vars, cli_value="cli",
                           aliases=(ALIAS,)) == "cli"

    def test_alias_in_env_beats_primary_in_file(self, monkeypatch):
        # Layer priority is strict: any OS-env hit outranks the file.
        monkeypatch.setenv(ALIAS, "alias-env")
        file_vars = {PRIMARY: "primary-file"}
        assert env.resolve(PRIMARY, file_vars, aliases=(ALIAS,)) == \
            "alias-env"

    def test_empty_cli_value_falls_through(self, monkeypatch):
        monkeypatch.setenv(PRIMARY, "from-env")
        assert env.resolve(PRIMARY, {}, cli_value="") == "from-env"

    def test_no_aliases_behaves_like_before(self, monkeypatch):
        monkeypatch.setenv(PRIMARY, "from-env")
        assert env.resolve(PRIMARY, {PRIMARY: "from-file"}) == "from-env"
        monkeypatch.delenv(PRIMARY)
        assert env.resolve(PRIMARY, {PRIMARY: "from-file"}) == "from-file"


class TestDefaultEnvPath:
    def test_prefers_dot_env_over_legacy_name(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("K=V\n", encoding="utf-8")
        (tmp_path / ".env.mybk-test").write_text("K=V\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert env.default_env_path() == (tmp_path / ".env").resolve()

    def test_falls_back_to_legacy_name(self, tmp_path, monkeypatch):
        legacy = tmp_path / ".env.mybk-test"
        legacy.write_text("K=V\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert env.default_env_path() == legacy.resolve()

    def test_returns_none_when_no_env_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert env.default_env_path() is None
