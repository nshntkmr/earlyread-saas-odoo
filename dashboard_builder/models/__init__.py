# -*- coding: utf-8 -*-

from . import dashboard_schema              # WB-1: schema source, column, relation
from . import dashboard_widget_mixin        # WB-2: abstract action mixin (must load before definition)
from . import dashboard_widget_definition   # WB-2: widget definition (library)
from . import dashboard_widget_template     # WB-6: widget templates
from . import dashboard_page_template      # Page templates (save/reuse page layouts)
