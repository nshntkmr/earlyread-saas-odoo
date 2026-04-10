from odoo import models, fields


class GeoZipCentroid(models.Model):
    _name = 'geo.zip.centroid'
    _description = 'US ZIP Code Centroid (for map widget geo joins)'
    _order = 'zip_code'

    zip_code = fields.Char(
        required=True, index=True, size=5,
        help='5-digit US ZIP code')
    latitude = fields.Float(
        digits=(9, 6), required=True,
        help='Centroid latitude (WGS84)')
    longitude = fields.Float(
        digits=(10, 6), required=True,
        help='Centroid longitude (WGS84)')
    state_code = fields.Char(
        size=2, index=True,
        help='2-letter state abbreviation')

    _sql_constraints = [
        ('zip_code_unique', 'unique(zip_code)', 'ZIP code must be unique'),
    ]
