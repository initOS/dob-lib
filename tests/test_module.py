# © 2021 Florian Kantelberg (initOS GmbH)
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


def test_get_modules(env):
    env.set(base.SECTION, "mode", value="prod")
    assert env.get_modules() == {"normal"}

    env.set(base.SECTION, "mode", value="staging")
    assert env.get_modules() == {"normal", "staging", "dev_staging"}

    env.set(base.SECTION, "mode", value="dev")
    assert env.get_modules() == {"normal", "dev", "dev_staging"}

    env.set(base.SECTION, "mode", value="dev,staging")
    assert env.get_modules() == {"normal", "dev", "dev_staging", "staging"}

    env.set("modules", value=[{}])
    with pytest.raises(TypeError):
        env.get_modules()


def test_get_installed_modules(env):
    env.env = mock.MagicMock()
    assert env.get_installed_modules("odoo") == {"base"}


def test_install_all(env):
    odoo = sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = mock.MagicMock()

    env.install_all("odoo", ["module"])
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
        force_demo=False,
    )

    env.set("odoo", "options", "load_language", value=["en_US"])
    env.install_all("odoo", ["module"])


def test_update_all(env):
    odoo = sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = mock.MagicMock()
    env.get_installed_modules = mock.MagicMock()

    env.update_all("odoo")
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
    )

    env.get_installed_modules.assert_called_once()


def test_update_listed(env):
    odoo = sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = mock.MagicMock()
    env.get_modules = mock.MagicMock()

    env.update_listed("odoo")
    odoo.modules.registry.Registry.new.assert_called_once_with(
        "odoo",
        update_module=True,
    )

    env.get_modules.assert_called_once()


def test_update_changed(env):
    odoo_env = env.env = mock.MagicMock()
    env.update_changed("odoo")

    model = odoo_env.return_value.__enter__.return_value["ir.module.module"]
    model.upgrade_changed_checksum.assert_called_once_with(True)

    # Test the fallback if the module isn't installed
    odoo_env.return_value.__enter__.return_value = {"ir.module.module": None}
    env.update_all = mock.MagicMock()
    env.update_changed("odoo", ["abc"])
    env.update_all.assert_called_once_with("odoo", ["abc"])


def test_update(env):
    # Quite complex and we have to mock plenty of stuff
    odoo = sys.modules["odoo"] = mock.MagicMock()
    tools = sys.modules["odoo.tools"] = mock.MagicMock()
    sys.modules["odoo.release"] = odoo.release
    tools.config.__getitem__.return_value = "odoo"
    odoo.release.version_info = (14, 0)
    env.generate_config = mock.MagicMock()
    env.get_installed_modules = mock.MagicMock()
    env.update_all = mock.MagicMock()
    env.update_changed = mock.MagicMock()
    env.update_listed = mock.MagicMock()
    env._init_odoo = mock.MagicMock(return_value=False)

    # Init of odoo isn't possible
    env.update()

    # Initialize
    env._init_odoo.return_value = True
    odoo.modules.db.is_initialized.return_value = False
    env.update()
    env.get_installed_modules.assert_not_called()
    env.update_changed.assert_called_once()

    odoo.release.version_info = (15,)
    odoo.modules.db.is_initialized.return_value = True
    env.update()
    env.get_installed_modules.assert_called()
    env.update_all.assert_not_called()
    env.update_listed.assert_not_called()

    env.update(["--all"])
    env.update_all.assert_called()
    env.update_listed.assert_not_called()

    env.update(["--listed"])
    env.update_listed.assert_called()

    env.update_all.reset_mock()
    env.update(["abc", "def"])
    env.update_all.assert_called_once_with("odoo", ["abc", "def"])


def test_no_flags():
    with pytest.raises(argparse.ArgumentTypeError):
        no_flags("-invalid")

    assert no_flags("valid") == "valid"
