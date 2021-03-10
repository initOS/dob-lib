# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
from contextlib import closing

from . import base, env, utils

try:
    import pre_install
except ImportError:
    pre_install = None

try:
    import pre_update
except ImportError:
    pre_update = None

try:
    import post_update
except ImportError:
    post_update = None


def no_flags(x):
    if x.startswith("-"):
        raise argparse.ArgumentTypeError("Invalid argument")
    return x


def load_update_arguments(args):
    parser = utils.default_parser("init")
    parser.add_argument(
        "modules",
        nargs=argparse.REMAINDER,
        type=no_flags,
        default=[],
        help="Module to update",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Update all modules instead of only changed ones",
    )
    parser.add_argument(
        "--listed",
        action="store_true",
        default=False,
        help="Update all listed modules instead of only changed ones",
    )
    parser.add_argument(
        "--passwords",
        action="store_true",
        default=False,
        help="Forcefully overwrite passwords",
    )
    return parser.parse_known_args(args)


class ModuleEnvironment(env.Environment):
    """ Class to handle modules """

    def _run_migration(self, db_name, script):
        """ Run a migration script by executing the migrate function """
        if script:
            utils.info(f"Executing {script.__name__.replace('_', ' ')} script")
            with self.env(db_name) as env:
                version = utils.Version(
                    env["ir.config_parameter"].get_param("db_version", False)
                )
                script.migrate(env, version)

    def get_modules(self):
        """ Return the list of modules """
        modes = self.get(base.SECTION, "mode", default=[])
        modes = set(modes.split(",") if isinstance(modes, str) else modes)

        modules = set()
        for module in self.get("modules", default=[]):
            if isinstance(module, str):
                modules.add(module)
            elif isinstance(module, dict) and len(module) == 1:
                mod, mode = list(module.items())[0]
                if isinstance(mode, str) and mode in modes:
                    modules.add(mod)
                elif isinstance(mode, list) and modes.intersection(mode):
                    modules.add(mod)
            else:
                raise TypeError("modules: must be str or dict of length 1")

        return modules

    def get_installed_modules(self, db_name):
        """ Return the list of modules which are installed """
        with self.env(db_name, False) as env:
            domain = [("state", "=", "installed")]
            installed = env["ir.module.module"].search(domain).mapped("name")
            return set(installed).union(["base"])

    def install_all(self, db_name, modules):
        """ Install all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        config["init"] = dict.fromkeys(modules, 1)
        config["update"] = {}
        config["overwrite_existing_translations"] = True
        without_demo = self.opt("without_demo", default=True)
        languages = self.opt("load_language")
        if languages and isinstance(languages, list):
            config["load_language"] = ",".join(languages)
        elif languages:
            config["load_language"] = languages

        odoo.modules.registry.Registry.new(
            db_name,
            update_module=True,
            force_demo=not without_demo,
        )

    def update_all(self, db_name, blacklist=None):
        """ Update all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        if not blacklist:
            blacklist = []

        utils.info("Updating all modules")
        modules = self.get_installed_modules(db_name).difference(blacklist)
        config["init"] = {}
        config["update"] = dict.fromkeys(modules, 1)
        config["overwrite_existing_translations"] = True
        odoo.modules.registry.Registry.new(db_name, update_module=True)

    def update_listed(self, db_name, blacklist=None):
        """ Update all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        utils.info("Updating listed modules")
        modules = self.get_modules().difference(blacklist or [])
        config["init"] = {}
        config["update"] = dict.fromkeys(modules, 1)
        config["overwrite_existing_translations"] = True
        odoo.modules.registry.Registry.new(db_name, update_module=True)

    def update_changed(self, db_name, blacklist=None):
        """ Update only changed modules """
        utils.info("Updating changed modules")
        with self.env(db_name, False) as env:
            model = env["ir.module.module"]
            if hasattr(model, "upgrade_changed_checksum"):
                model.upgrade_changed_checksum(True)
                return

        utils.info("The module module_auto_update is needed. Falling back")
        self.update_all(db_name, blacklist)

    def update(self, args=None):
        """ Install/update Odoo modules """
        args, _ = load_update_arguments(args or [])

        self.generate_config()

        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        config.parse_config(["-c", base.ODOO_CONFIG])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]
        with odoo.api.Environment.manage():
            # Ensure that the database is initialized
            db = odoo.sql_db.db_connect(db_name)
            initialized = False
            with closing(db.cursor()) as cr:
                if not odoo.modules.db.is_initialized(cr):
                    utils.info("Initializing the database")
                    odoo.modules.db.initialize(cr)
                    cr.commit()
                    initialized = True

            # Execute the pre install script
            self._run_migration(db_name, pre_install)

            # Get the modules to install
            if initialized:
                uninstalled = self.get_modules()
            else:
                installed = self.get_installed_modules(db_name)
                modules = self.get_modules()
                uninstalled = modules.difference(installed)

            # Install all modules
            utils.info("Installing all modules")
            if uninstalled:
                self.install_all(db_name, uninstalled)

            # Execute the pre update script
            self._run_migration(db_name, pre_update)

            # Update all modules which aren't installed before
            if args.modules:
                self.update_all(db_name, args.modules)
            elif args.listed:
                self.update_listed(db_name, uninstalled)
            elif args.all:
                self.update_all(db_name, uninstalled)
            else:
                self.update_changed(db_name, uninstalled)

            # Execute the post update script
            self._run_migration(db_name, post_update)

            # Finish everything
            with self.env(db_name) as env:
                # Set the user passwords if previously initialized
                users = self.get("odoo", "users", default={})
                if (initialized or args.passwords) and users:
                    utils.info("Setting user passwords")
                    model = env["res.users"]
                    for user, password in users.items():
                        domain = [("login", "=", user)]
                        model.search(domain).write({"password": password})

                # Write the version into the database
                utils.info("Setting database version")
                version = self.get(base.SECTION, "version", default="0.0")
                env["ir.config_parameter"].set_param("db_version", version)
