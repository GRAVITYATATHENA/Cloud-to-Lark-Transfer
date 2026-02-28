import os
import pytest
from transfer.config import Settings

def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "secret123")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "fldcnABC")
    s = Settings()
    assert s.lark_app_id == "cli_test"
    assert s.lark_app_secret == "secret123"
    assert s.lark_root_folder_token == "fldcnABC"
    assert s.temp_dir == "/tmp/transfer-jobs"  # default

def test_settings_custom_temp_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("LARK_APP_ID", "x")
    monkeypatch.setenv("LARK_APP_SECRET", "x")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "x")
    monkeypatch.setenv("TEMP_DIR", str(tmp_path))
    s = Settings()
    assert s.temp_dir == str(tmp_path)
