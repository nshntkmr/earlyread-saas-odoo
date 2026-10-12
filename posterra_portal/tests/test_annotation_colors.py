# -*- coding: utf-8 -*-
"""SQL-driven header-badge colour: the ONLY path where a SQL value becomes CSS
is ``utils.annotation_colors.resolve_badge_colour`` — pure Python, no DB.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_annotations --stop-after-init -d <test_db>
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils.annotation_colors import (
    TONE_HEX, resolve_badge_colour,
)


@tagged('posterra_annotations', 'post_install', '-at_install')
class TestResolveBadgeColour(TransactionCase):

    def test_hex_passes_through(self):
        self.assertEqual(resolve_badge_colour('#1f7a46'), '#1f7a46')
        self.assertEqual(resolve_badge_colour('  #C4321F '), '#C4321F')
        # 3-digit hex is expanded so the renderer's "<hex>1f" tint suffix stays valid
        self.assertEqual(resolve_badge_colour('#abc'), '#aabbcc')

    def test_tone_words_map_to_palette(self):
        for tone, hex_ in TONE_HEX.items():
            self.assertEqual(resolve_badge_colour(tone), hex_)
        self.assertEqual(resolve_badge_colour('SUCCESS'), TONE_HEX['success'])
        self.assertEqual(resolve_badge_colour('neutral'), '')   # classic grey

    def test_everything_else_is_classic_grey(self):
        # unresolved template (column missing from the row), CSS injection
        # attempts, blanks and NULL all fall back to '' — never raw CSS.
        for bad in ('%(RISK_TONE)s', 'red', 'rgb(1,2,3)', 'url(x)', '#12345',
                    '#gggggg', '', None, 0):
            self.assertEqual(resolve_badge_colour(bad), '', bad)
