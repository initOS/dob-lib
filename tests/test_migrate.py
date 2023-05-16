# -*- coding: utf-8 -*-
# © 2021-2022 Ruben Ortlam (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys

import mock
import pytest
from doblib import utils
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
    utils.module_mock(odoo, ["odoo.cli", "odoo.tools"])
    sys.modules["odoo.release"] = odoo.release

    odoo.tools.config.__getitem__.return_value = "odoo"
    odoo.release.version_info = (14, 0)
    env.generate_config = mock.MagicMock()
    env._init_odoo = mock.MagicMock(return_value=False)
    env.init = mock.MagicMock(return_value=0)
    env._run_migration = mock.MagicMock(return_value=0)
    env._run_migration_sql = mock.MagicMock(return_value=0)
    env.start = mock.MagicMock(return_value=0)

    args = mock.MagicMock(
        version=utils.Version(13),
        skip_premigrate=False,
        skip_migrate=False,
        skip_postmigrate=False,
    )

    # Init of odoo isn't possible
    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_not_called()
    env._run_migration_sql.assert_not_called()
    env.start.assert_not_called()
    env.init.reset_mock()

    # Database not initialized
    env._init_odoo.return_value = True
    odoo.modules.db.is_initialized.return_value = False
    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_not_called()
    env._run_migration_sql.assert_not_called()
    env.start.assert_not_called()
    env.init.reset_mock()

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
    env._run_migration_sql.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_13.sql"),
            mock.call("odoo", "post_migrate_13.sql"),
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
    env._run_migration_sql.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15.sql"),
            mock.call("odoo", "post_migrate_15.sql"),
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

    # Check parameters
    env.init.reset_mock()
    env.start.reset_mock()
    args.skip_premigrate = True
    args.skip_migrate = False
    args.skip_postmigrate = False

    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_has_calls(
        [
            mock.call("odoo", "post_migrate_15"),
        ]
    )
    env._run_migration_sql.assert_has_calls(
        [
            mock.call("odoo", "post_migrate_15.sql"),
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

    env.init.reset_mock()
    env.start.reset_mock()
    args.skip_premigrate = False
    args.skip_migrate = True
    args.skip_postmigrate = False

    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15"),
            mock.call("odoo", "post_migrate_15"),
        ]
    )
    env._run_migration_sql.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15.sql"),
            mock.call("odoo", "post_migrate_15.sql"),
        ]
    )
    env.start.assert_not_called()

    env.init.reset_mock()
    env.start.reset_mock()
    args.skip_premigrate = False
    args.skip_migrate = False
    args.skip_postmigrate = True

    env.migrate(args)
    env.init.assert_called_once()
    env._run_migration.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15"),
        ]
    )
    env._run_migration_sql.assert_has_calls(
        [
            mock.call("odoo", "pre_migrate_15.sql"),
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
