# -*- coding: utf-8 -*-

from . import dashboard_connection          # CH-1: external database connection (must load before schema_source so the M2O target exists)
from . import dashboard_schema              # WB-1: schema source, column, relation
from . import dashboard_widget_mixin        # WB-2: abstract action mixin (must load before definition)
from . import dashboard_widget_definition   # WB-2: widget definition (library)
from . import dashboard_widget_template     # WB-6: widget templates
