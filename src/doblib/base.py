# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os

ODOO_CONFIG = os.path.abspath("etc/odoo.cfg")

SECTION = "bootstrap"
# Mapping of environment variables to configurations
ENVIRONMENT = {
    "ODOO_VERSION": ("odoo", "version"),
    "BOOTSTRAP_MODE": (SECTION, "mode"),
}
