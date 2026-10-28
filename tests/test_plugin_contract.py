"""The real pinned SDK loads the plugin from its independent install layout."""

import shutil
from pathlib import Path

from yuki_plugin_sdk.testing.contract import run_plugin_contract_tests


async def test_plugin_api_nine_lifecycle(tmp_path):
    root = Path(__file__).parents[1]
    installed = tmp_path / "github-monitor"
    shutil.copytree(root / "github_monitor", installed / "github_monitor")
    shutil.copyfile(root / "plugin.toml", installed / "plugin.toml")
    report = await run_plugin_contract_tests(installed)
    assert report.passed, report.model_dump_json()
    assert report.plugin_id == "github-monitor"
    assert "register" in report.checks and "stop" in report.checks
