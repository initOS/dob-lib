# © 2021-2022 Ruben Ortlam (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import os
import sys
from unittest import mock

import pytest

from doblib import base, utils
from doblib.migrate import MigrateEnvironment


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = MigrateEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


@mock.patch("doblib.aggregate.get_repos", return_value=[{"cwd": "unknown"}])
def test_migrate(repos, env):
    odoo = sys.modules["odoo"] = mock.MagicMock()
    tools = sys.modules["odoo.tools"] = mock.MagicMock()
    tools.config.__getitem__.return_value = "odoo"
    sys.modules["odoo.release"] = odoo.release
    odoo.release.version_info = (14, 0)
    env.generate_config = mock.MagicMock()
    env._init_odoo = mock.MagicMock(return_value=False)
    env.init = mock.MagicMock(return_value=0)
    env._run_migration = mock.MagicMock(return_value=0)
    env.start = mock.MagicMock(return_value=0)

    args = mock.MagicMock(version=utils.Version(13))

    # Init of odoo isn't possible
    env.migrate(args)
    env.init.assert_not_called()
    env._run_migration.assert_not_called()
    env.start.assert_not_called()

    # Database not initialized
    env._init_odoo.return_value = True
    odoo.modules.db.is_initialized.return_value = False
    env.migrate(args)
    env.init.assert_not_called()
    env._run_migration.assert_not_called()
    env.start.assert_not_called()

    # Initialize and run for Odoo <= 13
    odoo.modules.db.is_initialized.return_value = True
    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_13"),
            mock.call("odoo", "post_migrate_13"),
        ]
    )
    env.start.assert_called_once_with(
        ["--update", "all", "--stop-after-init", "--load=base,web"]
    )

    env.init.reset_mock()
    env.start.reset_mock()
    args.version = utils.Version(15)

    # Run for Odoo > 13
    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15"),
            mock.call("odoo", "post_migrate_15"),
        ]
    )
    env.start.assert_called_once_with(
        [
            "--update",
            "all",
            "--stop-after-init",
            "--load=base,web,openupgrade_framework",
        ]
    )
