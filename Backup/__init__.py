from . import controllers
from . import models
from . import wizard


def post_init_hook(env):
    """Recompute domain_match_name for all HHA providers after install/upgrade.

    This ensures existing records pick up the correct value whenever the
    matching logic changes (e.g. DBA-first priority).
    """
    providers = env['hha.provider'].search([])
    if providers:
        # Invalidate the stored field so Odoo recomputes it fresh
        providers.invalidate_recordset(['domain_match_name'])
        providers._compute_domain_match_name()