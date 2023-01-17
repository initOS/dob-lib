# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os

ODOO_CONFIG = os.path.abspath(
    os.path.join("etc", os.environ.get("ODOO_CONFIG", "odoo.cfg"))
)
ADDON_PATH = "/tmp/addons"

SECTION = "bootstrap"
# Mapping of environment variables to configurations
ENVIRONMENT = {
    "ODOO_VERSION": ("odoo", "version"),
    "BOOTSTRAP_MODE": (SECTION, "mode"),
    "BOOTSTRAP_DEBUGGER": (SECTION, "debugger"),
}
