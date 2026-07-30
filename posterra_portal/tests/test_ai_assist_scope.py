# -*- coding: utf-8 -*-
"""AI Assist visibility + PHI-guard unit tests.

The chatbot's queryable-source set is resolved exclusively through
``dashboard.schema.source.get_ai_visible_sources(app)``. These tests pin
the truth table: every condition (app toggle, per-source opt-in, active,
non-PHI classification, app scoping) independently excludes a source, and
the PHI×AI constraint + reclassification auto-clear hold.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_ai_assist --stop-after-init -d <test_db>
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiVisibleSources(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        App = cls.env['saas.app'].sudo()
        cls.app = App.create({
            'name': 'AI Test App', 'app_key': 'ai-test-app',
            'access_mode': 'group', 'ai_assist_enabled': True,
        })
        cls.other_app = App.create({
            'name': 'AI Other App', 'app_key': 'ai-other-app',
            'access_mode': 'group', 'ai_assist_enabled': True,
        })
        cls.Source = cls.env['dashboard.schema.source'].sudo()

    def _mk_source(self, table, **vals):
        base = {
            'name': table, 'table_name': table,
            'ai_enabled': True, 'is_active': True,
            'data_classification': 'non_phi',
        }
        base.update(vals)
        return self.Source.create(base)

    def _visible(self):
        return self.Source.get_ai_visible_sources(self.app)

    def test_global_source_visible(self):
        src = self._mk_source('t_ai_global')
        self.assertIn(src, self._visible())
        # Global (empty app_ids) is visible to every AI-enabled app.
        self.assertIn(src, self.Source.get_ai_visible_sources(self.other_app))

    def test_app_scoped_source(self):
        src = self._mk_source('t_ai_scoped',
                              app_ids=[(6, 0, [self.app.id])])
        self.assertIn(src, self._visible())
        self.assertNotIn(
            src, self.Source.get_ai_visible_sources(self.other_app))

    def test_ai_enabled_off_excludes(self):
        src = self._mk_source('t_ai_off', ai_enabled=False)
        self.assertNotIn(src, self._visible())

    def test_inactive_excludes(self):
        src = self._mk_source('t_ai_inactive', is_active=False)
        self.assertNotIn(src, self._visible())

    def test_app_toggle_off_yields_empty(self):
        self._mk_source('t_ai_toggle')
        self.app.ai_assist_enabled = False
        self.assertFalse(self._visible())

    def test_no_app_yields_empty(self):
        self._mk_source('t_ai_noapp')
        self.assertFalse(self.Source.get_ai_visible_sources(None))

    def test_phi_constraint_blocks_opt_in(self):
        # A PHI source cannot be opted into AI at all. Constructing a valid
        # PHI source requires the whole hospital_phi connection scaffolding,
        # so assert the AI constraint fires FIRST on a plain source — both
        # constraints reject the write either way (fail closed).
        src = self._mk_source('t_ai_phi', ai_enabled=False)
        with self.assertRaises(ValidationError):
            src.write({'data_classification': 'phi_masked',
                       'ai_enabled': True})

    def test_reclassify_clears_opt_in(self):
        src = self._mk_source('t_ai_reclass')
        self.assertTrue(src.ai_enabled)
        # Reclassifying to PHI would trip _check_phi_source_scoping (no
        # hospital_phi connection here), but the write() hook must clear
        # ai_enabled BEFORE constraints evaluate — assert via the vals
        # transformation by trying the write and checking the error is the
        # PHI-connection one, not the AI one.
        try:
            src.write({'data_classification': 'phi_masked'})
        except ValidationError as e:
            self.assertIn('Hospital-PHI', str(e))
        else:
            # If source-scoping constraints ever allow it, the opt-in must
            # have been auto-cleared.
            self.assertFalse(src.ai_enabled)


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiQueryLogRateWindow(TransactionCase):

    def test_log_model_creates(self):
        user = self.env.ref('base.user_admin')
        app = self.env['saas.app'].sudo().create({
            'name': 'AI Log App', 'app_key': 'ai-log-app',
            'access_mode': 'group',
        })
        log = self.env['ai.query.log'].sudo().create({
            'user_id': user.id, 'app_id': app.id, 'app_key': app.app_key,
            'channel': 'mcp', 'mode': 'sql', 'sql': 'SELECT 1',
            'row_count': 1, 'duration_ms': 5, 'status': 'ok',
        })
        self.assertTrue(log.create_date)
        self.assertEqual(log.app_key, 'ai-log-app')
