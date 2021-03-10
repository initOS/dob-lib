# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
from unittest.mock import patch

import pytest

from doblib import utils


def test_merge():
    assert utils.merge([1, 2], [3, 4]) == [1, 2, 3, 4]
    assert utils.merge({1, 2}, {3, 4}) == {1, 2, 3, 4}
    assert utils.merge({3, 4}, {1, 2}) == {1, 2, 3, 4}
    assert utils.merge([1, 2], {3, 4}) == {3, 4}
    assert utils.merge({1: 2}, {1: 3}) == {1: 3}
    assert utils.merge({1: 2}, {2: 3}) == {1: 2, 2: 3}
    assert utils.merge({1: {2: 3}}, {1: {3: 4}}) == {1: {2: 3, 3: 4}}

    assert utils.merge({1: {2: 3}}, {1: {3: 4}}, replace={1}) == {1: {3: 4}}


def test_keyboard_interrupt():
    with pytest.raises(KeyboardInterrupt):
        utils.raise_keyboard_interrupt()


def test_version():
    ver = utils.Version("1.2.3")
    assert ver == "1.2.3"
    assert utils.Version(ver) == ver
    assert utils.Version() == ()
    assert utils.Version(1) == (1,)
    assert utils.Version((1, 2, 3)) == (1, 2, 3)
    assert utils.Version(None) == ()

    ver = utils.Version("1.2.3")
    assert str(ver) == "1.2.3"
    assert ver == (1, 2, 3)
    assert ver < 2
    assert ver > "1.2"
    assert ver <= (1, 2, 3)
    assert ver >= (1, 2, 2)


def test_default_parser():
    parser = utils.default_parser("test")
    assert isinstance(parser, argparse.ArgumentParser)


@patch("os.path.isfile")
def test_config_file(mock):
    found = []
    mock.side_effect = lambda file: file in found

    assert utils.get_config_file() is None
    found = ["odoo.local.yaml"]
    assert utils.get_config_file() == "odoo.local.yaml"
    found = ["odoo.project.yaml"]
    assert utils.get_config_file() == "odoo.project.yaml"
    found = ["odoo.project.yaml", "odoo.local.yaml"]
    assert utils.get_config_file() == "odoo.local.yaml"


def test_call():
    output = utils.call("ls")
    assert isinstance(output, str) and output

    output = utils.call("ls", pipe=False)
    assert output == 0
