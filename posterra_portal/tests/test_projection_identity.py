# -*- coding: utf-8 -*-
"""Identity encoding (spec §3.1): Python and the rendered Postgres expression
must agree on every fixture; the ClickHouse expression must render the
documented functions.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_projections --stop-after-init -d <test_db>
"""

import hashlib

from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils import projection_identity as pid


FIXTURES = [
    ('H000123', 'BCS', 2026),
    (' H000123 ', 'BCS\t', '2026'),           # trimming → same as above
    ('Hélène', 'COL-ü', 2026),   # unicode
    ('a|b', 'c', 1),                            # delimiter-like characters
    ('a', 'b|c', 1),                            # must not collide with the above
    ('x:y', 'z', 0),                            # zero is a value, not missing
    ('0007', 'LEAD', -5),                       # leading zeros kept, negatives
    ('with\x01ctrl', 'm', 2026),
]


@tagged('post_install', '-at_install', 'posterra_projections')
class TestProjectionIdentity(TransactionCase):

    def test_encoding_is_length_prefixed_md5(self):
        h = pid.identity_hash(['H000123', 'BCS', 2026])
        expected = hashlib.md5('7:H0001233:BCS4:2026'.encode('utf-8')).hexdigest()
        self.assertEqual(h, expected)
        self.assertEqual(len(h), 32)

    def test_trimming_and_types(self):
        self.assertEqual(pid.identity_hash(['H000123', 'BCS', 2026]),
                         pid.identity_hash([' H000123 ', 'BCS\t', '2026']))
        self.assertEqual(pid.normalize_component(None), '')
        self.assertEqual(pid.normalize_component(True), '1')
        self.assertEqual(pid.normalize_component(' \t7\r\n'), '7')

    def test_delimiters_do_not_collide(self):
        self.assertNotEqual(pid.identity_hash(['a|b', 'c', 1]),
                            pid.identity_hash(['a', 'b|c', 1]))
        self.assertNotEqual(pid.identity_hash(['x:y', 'z', 0]),
                            pid.identity_hash(['x', ':y', 'z0']))

    def test_incomplete_identity(self):
        with self.assertRaises(pid.IdentityIncomplete):
            pid.identity_hash(['H1', '', 2026])
        with self.assertRaises(pid.IdentityIncomplete):
            pid.identity_hash(['H1', None, 2026])
        with self.assertRaises(pid.IdentityIncomplete):
            pid.identity_hash(['H1', '  \t ', 2026])
        self.assertIsNone(pid.identity_hash_or_none(['H1', '', 2026]))

    def test_postgres_expression_matches_python(self):
        expr = pid.render_identity_expr(['c1', 'c2', 'c3'], 'postgres_local')
        for c1, c2, c3 in FIXTURES:
            self.env.cr.execute(
                'SELECT %s FROM (VALUES (%%s::text, %%s::text, %%s::int)) AS t(c1, c2, c3)'
                % expr, [str(c1), str(c2), int(c3)])
            (db_hash,) = self.env.cr.fetchone()
            self.assertEqual(db_hash, pid.identity_hash([str(c1), str(c2), int(c3)]),
                             'fixture %r' % ((c1, c2, c3),))

    def test_postgres_expression_null_when_incomplete(self):
        expr = pid.render_identity_expr(['c1', 'c2'], 'postgres_local')
        for c1, c2 in (('H1', ''), (None, 'x'), ('  ', 'x')):
            self.env.cr.execute(
                'SELECT %s FROM (VALUES (%%s::text, %%s::text)) AS t(c1, c2)' % expr, [c1, c2])
            (db_hash,) = self.env.cr.fetchone()
            self.assertIsNone(db_hash)

    def test_clickhouse_expression_shape(self):
        expr = pid.render_identity_expr(['HUM_ID', 'MEASURE_CAT'], 'clickhouse')
        self.assertIn('lower(hex(MD5(concat(', expr)
        self.assertIn("trim(BOTH ' \\t\\r\\n' FROM ifNull(toString(\"HUM_ID\"), ''))", expr)
        self.assertIn("toString(length(", expr)
        self.assertTrue(expr.startswith('if('))
        self.assertTrue(expr.endswith(", '')"))

    def test_invalid_identifier_rejected(self):
        with self.assertRaises(ValueError):
            pid.render_identity_expr(['bad name'], 'clickhouse')
        with self.assertRaises(ValueError):
            pid.render_identity_expr(['x; DROP'], 'postgres_local')
        with self.assertRaises(ValueError):
            pid.render_identity_expr([], 'postgres_local')

    def test_in_list_and_value_lists(self):
        self.assertEqual(pid.parse_value_list(' 1, Y ,'), ['1', 'Y'])
        self.assertEqual(pid.parse_value_list('', '1'), ['1'])
        expr = pid.render_in_list_expr('c', ["1", "O'K"], 'postgres_local')
        self.assertIn("IN ('1', 'O''K')", expr)
        self.env.cr.execute("SELECT %s FROM (VALUES (' 1 '::text)) AS t(c)" % expr)
        self.assertTrue(self.env.cr.fetchone()[0])
