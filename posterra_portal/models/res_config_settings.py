# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # RLS Match Field removed — replaced by HHA Scope Groups
    # (Posterra → Configuration → Scope Groups)
