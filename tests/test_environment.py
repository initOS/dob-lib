# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
from configparser import ConfigParser
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import mock

import pytest

from doblib import base
from doblib.env import Environment, load_config_arguments


@pytest.fixture
def env():
    os.environ["ODOO_VERSION"] = "1x.0"

    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = Environment("odoo.local.yaml")
    os.chdir(cur)
    return env


def test_arguments():
    args, left = load_config_arguments(["-c", "abc", "-k"])
    assert args.cfg == "abc"
    assert left == ["-k"]


def test_configuration(env):
    assert env.get("local") is True
    assert env.get("project") is True
    assert env.get("default") is True
    assert env.get("main") is True

    # Test if the environment variable is used
    assert env.get("odoo", "version") == "1x.0"

    # Test some substitutions
    assert env.get("substring") == "0.1.2.3.4"
    assert env.get("dict of lists") == ["1.2.3", {"a": "1.2.3"}, None]
    assert env.get("list of dicts") == [{3: "1.2.3.4"}, {2: "0.1.2.3"}]
    assert env.get("list of lists") == [["1.2.3.1.2.3"]]

    # Test the options
    assert env.opt("testing") == "1.2.3"
    assert env.opt("to_none", default=42) == 42
    assert env.opt("unknown", default="not found") == "not found"


def test_configuration_output(env):
    odoo = len(env.config(["odoo"]))
    assert len(env.config([])) > odoo
    assert odoo > len(env.config(["odoo:options"]))


def test_configuration_generation(env):
    with TemporaryDirectory() as dir_name:
        base.ODOO_CONFIG = f"{dir_name}/odoo.cfg"
        env.generate_config()

        cp = ConfigParser()
        cp.read(base.ODOO_CONFIG)

        assert cp.get("options", "testing") == "1.2.3"
        assert cp.get("options", "to_none") == ""
        assert cp.get("additional", "key") == "value"


def test_invalid_extend():
    with NamedTemporaryFile() as fp:
        fp.write(b"bootstrap:\n  extend: 1")
        fp.seek(0)

        with pytest.raises(TypeError):
            Environment(fp.name)


def test_substitute_syntax(env):
    with pytest.raises(SyntaxError):
        env._substitute_string("${:}")


def test_init_odoo(env):
    # Path not exists
    assert env._init_odoo() is False

    with TemporaryDirectory() as dir_name:
        # Not a dir
        env.set("bootstrap", "odoo", value=f"{dir_name}/unknown")
        assert env._init_odoo() is False

        env.set("bootstrap", "odoo", value=dir_name)
        assert dir_name not in sys.path
        assert env._init_odoo() == dir_name
        assert dir_name in sys.path


def test_env(env):
    sys.modules.pop("odoo", None)

    with pytest.raises(ImportError):
        with env.env("odoo"):
            pass

    odoo = sys.modules["odoo"] = mock.MagicMock()
    reg = odoo.registry.return_value = mock.MagicMock()
    cr = reg.cursor.return_value = mock.MagicMock()

    # Test the normal commit
    with env.env("odoo"):
        odoo.registry.assert_called_once_with("odoo")
        cr.commit.assert_not_called()

    cr.commit.assert_called_once()
    cr.rollback.assert_not_called()

    # Test the rollback
    cr.reset_mock()
    with env.env("odoo", rollback=True):
        cr.rollback.assert_not_called()

    cr.rollback.assert_called_once()
    cr.commit.assert_not_called()
