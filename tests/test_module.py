# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import os
import sys
from unittest import mock

import pytest

from doblib import base
from doblib.module import ModuleEnvironment, no_flags


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = ModuleEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


def mock_odoo_import():
    odoo = sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = odoo.tools
    sys.modules["odoo.release"] = odoo.release = mock.MagicMock(version_info=(18,))
    sys.modules["odoo.api"] = odoo.api
    sys.modules["odoo.cli"] = odoo.cli
    sys.modules["odoo.cli.server"] = odoo.cli.server
    sys.modules["odoo.tools"] = odoo.tools
    sys.modules["odoo.modules"] = odoo.modules
    sys.modules["odoo.modules.db"] = odoo.modules.db
    sys.modules["odoo.modules.registry"] = odoo.modules.registry
    sys.modules["odoo.release"] = odoo.release
    sys.modules["odoo.sql_db"] = odoo.sql_db
    return odoo


def test_run_migration(env):
    cur = os.getcwd()
    os.chdir("tests/environment/")
    try:
        env.env = mock.MagicMock()
        odoo_env = env.env.return_value.__enter__.return_value = mock.MagicMock()
        odoo_env["ir.config_parameter"].get_param.return_value = "4.2"

        # Non-existing migration
        env._run_migration("odoo", "pre_update")
        odoo_env.check.assert_not_called()

        # Existing migration
        env._run_migration("odoo", "post_update")
        odoo_env.check.assert_called_once_with("4.2")
    finally:
        os.chdir(cur)


def test_run_migration_sql(env):
    cur = os.getcwd()
    os.chdir("tests/environment/")
    try:
        odoo = sys.modules["odoo"] = mock.MagicMock()
        sys.modules["odoo.sql_db"] = odoo.sql_db
        cursor = (
            odoo.sql_db.db_connect.return_value.cursor.return_value
        ) = mock.MagicMock()

        # Non-existing migration
        env._run_migration_sql("odoo", "pre_update.sql")
        cursor.execute.assert_not_called()

        # Existing migration
        env._run_migration_sql("odoo", "post_update.sql")
        cursor.execute.assert_called_once_with("SELECT * FROM res_partner;\n")
    finally:
        os.chdir(cur)


def test_get_modules(env):
    env.set(base.SECTION, "mode", value="prod")
    assert env._get_modules() == {"normal"}

    env.set(base.SECTION, "mode", value="staging")
    assert env._get_modules() == {"normal", "staging", "dev_staging"}

    env.set(base.SECTION, "mode", value="dev")
    assert env._get_modules() == {"normal", "dev", "dev_staging"}

    env.set(base.SECTION, "mode", value="dev,staging")
    assert env._get_modules() == {"normal", "dev", "dev_staging", "staging"}

    env.set("modules", value=[{}])
    with pytest.raises(TypeError):
        env._get_modules()


def test_get_installed_modules(env):
    env.env = mock.MagicMock()
    assert env._get_installed_modules("odoo") == {"base"}


def test_install_all(env):
    odoo = mock_odoo_import()

    env.install_all("odoo", ["module"])
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
        force_demo=False,
    )

    env.set("odoo", "options", "load_language", value=["en_US"])
    env.install_all("odoo", ["module"])


def test_update_all(env):
    odoo = mock_odoo_import()

    env.update_specific("odoo", installed=True)
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
    )


def test_update_listed(env):
    odoo = mock_odoo_import()
    env._get_modules = mock.MagicMock()

    env.update_specific("odoo", listed=True)
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
    )

    env._get_modules.assert_called_once()


def test_update_changed(env):
    odoo_env = env.env = mock.MagicMock()
    env.update_changed("odoo")

    model = odoo_env.return_value.__enter__.return_value["ir.module.module"]
    model.upgrade_changed_checksum.assert_called_once_with(True)

    # Test the fallback if the module isn't installed
    odoo_env.return_value.__enter__.return_value = {"ir.module.module": None}
    env.update_specific = mock.MagicMock()
    env.update_changed("odoo", ["abc"])
    env.update_specific.assert_called_once_with(
        "odoo", blacklist=["abc"], installed=True
    )


def test_update(env):
    # Quite complex and we have to mock plenty of stuff
    odoo = mock_odoo_import()
    tools = odoo.tools

    tools.config.__getitem__.return_value = "odoo"
    odoo.release.version_info = (14, 0)
    env.generate_config = mock.MagicMock()
    env._get_installed_modules = mock.MagicMock()
    env.update_changed = mock.MagicMock()
    env.update_specific = mock.MagicMock()
    env._init_odoo = mock.MagicMock(return_value=False)

    # Init of odoo isn't possible
    env.update()

    # Initialize
    env._init_odoo.return_value = True
    odoo.modules.db.is_initialized.return_value = False
    env.update()
    env._get_installed_modules.assert_not_called()
    env.update_changed.assert_not_called()

    odoo.release.version_info = (15,)
    odoo.modules.db.is_initialized.return_value = True
    env.update()
    env._get_installed_modules.assert_called_once()
    env.update_specific.assert_not_called()

    env.update(["--all"])
    env.update_specific.assert_called_once()

    env.update_specific.reset_mock()
    env.update(["--listed"])
    env.update_specific.assert_called_once()

    env.update_specific.reset_mock()
    env.update(["abc", "def"])
    env.update_specific.assert_called_once_with(
        "odoo",
        whitelist=["abc", "def"],
        blacklist={"abc", "def", "normal"},
        installed=False,
        listed=False,
    )


def test_no_flags():
    with pytest.raises(argparse.ArgumentTypeError):
        no_flags("-invalid")

    assert no_flags("valid") == "valid"
