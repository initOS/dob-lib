# -*- coding: utf-8 -*-
# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import re
import shutil
import sys
from contextlib import (
    closing,
    contextmanager,
)

import configparser
import yaml

from . import (
    base,
    utils,
)

SubstituteRegex = re.compile(r"\$\{(?P<var>(\w|:)+)\}")


def load_config_arguments(args):
    parser = utils.default_parser("config")
    parser.add_argument("option", nargs="?", help="Show only specific information")
    return parser.parse_known_args(args)


# pylint: disable=too-many-public-methods
class Environment:
    """Bootstrap environment"""

    def __init__(self, cfg):
        utils.info("Loading configuration file")
        self._config = {}
        self._load_config(cfg)
        self._load_config("odoo.versions.yaml", False)
        self._post_process_config()

    def _substitute(self, match, sub=True):
        """Replaces the matched parts with the variable"""
        var = match.groupdict().get("var", "").split(":")
        if not all(var):
            raise SyntaxError()

        result = self.get(var)
        return str(result) if sub else result

    def _substitute_string(self, line):
        """Substitute variables in strings"""
        match = SubstituteRegex.match(r"^{}$".format(line))
        if match:
            return self._substitute(match, False)
        return SubstituteRegex.sub(self._substitute, line)

    def _substitute_dict(self, data):
        """Substitute variables in dictionaries"""
        tmp = {}
        for sec, section in data.items():
            if isinstance(section, str):
                tmp[sec] = self._substitute_string(section)
            elif isinstance(section, list):
                tmp[sec] = self._substitute_list(section)
            elif isinstance(section, dict):
                tmp[sec] = self._substitute_dict(section)
            else:
                tmp[sec] = section
        return tmp

    def _substitute_list(self, ls):
        """Substitute variables in lists"""
        tmp = []
        for x in ls:
            if isinstance(x, dict):
                tmp.append(self._substitute_dict(x))
            elif isinstance(x, str):
                tmp.append(self._substitute_string(x))
            elif isinstance(x, list):
                tmp.append(self._substitute_list(x))
            else:
                tmp.append(x)
        return tmp

    def _post_process_config(self):
        """Post process the configuration by replacing variables"""

        # Include environment variables first for later substitutions
        for env, keys in base.ENVIRONMENT.items():
            if os.environ.get(env):
                self.set(keys, value=os.environ[env])

        options = self.get(["odoo", "options"], default={})
        for key, value in options.items():
            options[key] = os.environ.get("ODOO_{}".format(key.upper())) or value

        # Run the substitution on the configuration
        self._config = self._substitute_dict(self._config)

        # Combine the addon paths
        current = set(self.get(["odoo", "addons_path"], default=[]))
        current.add(base.ADDON_PATH)

        # Generate the addon paths
        current = set(map(os.path.abspath, current))
        self.set(["odoo", "options", "addons_path"], value=current)

    def get(self, key, default=None):
        """Get a specific value of the configuration"""
        data = self._config
        try:
            for k in key:
                data = data[k]
            if data is None:
                return default
            return utils.yaml_bool(data)
        except KeyError:
            return default

    def opt(self, key, default=None):
        """Short cut to directly access odoo options"""
        return self.get(["odoo", "options"] + list(key), default=default)

    def set(self, key, value=None):
        """Set a specific value of the configuration"""
        data = self._config
        for k in key[:-1]:
            data = data[k]

        data[key[-1]] = value

    def _load_config(self, cfg, raise_if_missing=True):
        """Load and process a configuration file"""
        if not os.path.isfile(cfg) and not raise_if_missing:
            utils.warn(" * {}".format(cfg))
            return

        utils.info(" * {}".format(cfg))
        with open(cfg) as fp:
            options = yaml.load(fp, Loader=yaml.FullLoader)

        # Load all base configuration files first
        extend = options.get(base.SECTION, {}).get("extend")
        if isinstance(extend, str):
            self._load_config(extend)
        elif isinstance(extend, list):
            for e in extend:
                self._load_config(e)
        elif extend is not None:
            raise TypeError("{}:extend must be str or list".format(base.SECTION))

        # Merge the configurations
        self._config = utils.merge(self._config, options, replace=["merges"])

    def _link_modules(self):
        """Create symlinks to the modules to allow black-/whitelisting"""
        shutil.rmtree(base.ADDON_PATH, True)
        if not os.path.isdir(base.ADDON_PATH):
            os.makedirs(base.ADDON_PATH)
        utils.info("Linking Odoo modules")

        for repo_src, repo in self.get(["repos"], default={}).items():
            target = os.path.abspath(repo.get("addon_path", repo_src))
            modules = repo.get("modules", [])
            whitelist = {m for m in modules if not m.startswith("!")}
            blacklist = {m[1:] for m in modules if m.startswith("!")}

            for module in os.listdir(target):
                path = os.path.join(target, module)
                # Check if module
                if not any(
                    os.path.isfile(os.path.join(path, manifest))
                    for manifest in ("__manifest__.py", "__openerp__.py")
                ):
                    continue

                if utils.check_filters(module, whitelist, blacklist):
                    os.symlink(path, os.path.join(base.ADDON_PATH, module))

    def _init_odoo(self):
        """Initialize Odoo to enable the module import"""
        path = self.get([base.SECTION, "odoo"])
        if not path:
            utils.error("No {}:odoo defined".format(base.SECTION))
            return False

        path = os.path.abspath(path)
        if not os.path.isdir(path):
            utils.error("Missing odoo folder")
            return False

        if path not in sys.path:
            sys.path.append(path)

        self._link_modules()
        return path

    @contextmanager
    def env(self, db_name, rollback=False):
        """Create an environment from a registry"""
        # pylint: disable=C0415,E0401
        try:
            from odoo import SUPERUSER_ID, api, registry
        except ImportError:
            from openerp import SUPERUSER_ID, api, registry

        # Get all installed modules
        reg = registry(db_name)
        with closing(reg.cursor()) as cr:
            yield api.Environment(cr, SUPERUSER_ID, {})

            if rollback:
                cr.rollback()
            else:
                cr.commit()

    @contextmanager
    def _manage(self):
        """Wrap the manage to resolve version differrences"""
        # pylint: disable=import-outside-toplevel
        try:
            from odoo import api, release
        except ImportError:
            from openerp import api, release

        if release.version_info >= (15,):
            yield
        else:
            with api.Environment.manage():
                yield

    def generate_config(self):
        """Generate the Odoo configuration file"""
        utils.info("Generating configuration file")
        cp = configparser.ConfigParser()

        # Generate the configuration with the sections
        options = self.get(["odoo", "options"], default={})
        for key, value in sorted(options.items()):
            if key == "load_language":
                continue

            if "." in key:
                sec, key = key.split(".", 1)
            else:
                sec = "options"

            if not cp.has_section(sec):
                cp.add_section(sec)

            if isinstance(value, (set, list)):
                cp.set(sec, key, ",".join(map(str, value)))
            elif value is None:
                cp.set(sec, key, "")
            else:
                cp.set(sec, key, str(value))

        directory = os.path.dirname(base.ODOO_CONFIG)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        # Write the configuration
        with open(base.ODOO_CONFIG, "w+") as fp:
            cp.write(fp)

    def config(self, args=None):
        """Simply output the rendered configuration file"""
        args, _ = load_config_arguments(args or [])

        if args.option:
            return yaml.dump(self.get(args.option.split(":")))

        return yaml.dump(self._config)
