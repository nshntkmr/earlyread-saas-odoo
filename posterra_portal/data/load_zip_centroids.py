"""
Load US Census ZCTA centroid data into geo.zip.centroid table.

Called from __manifest__.py post_init_hook. Uses raw SQL for speed
(~34K rows in seconds vs minutes via ORM).
"""
import csv
import os
import logging

_logger = logging.getLogger(__name__)

CSV_FILE = os.path.join(os.path.dirname(__file__), 'geo_zip_centroids.csv')


def load_zip_centroids(env):
    """Bulk-load ZIP centroids from CSV into geo_zip_centroid table."""
    cr = env.cr

    # Check if already loaded
    cr.execute("SELECT COUNT(*) FROM geo_zip_centroid")
    existing = cr.fetchone()[0]
    if existing > 30000:
        _logger.info("geo_zip_centroid already has %d rows, skipping load.", existing)
        return

    _logger.info("Loading ZIP centroids from %s ...", CSV_FILE)

    rows = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                row['zip_code'],
                float(row['latitude']),
                float(row['longitude']),
            ))

    if not rows:
        _logger.warning("No rows found in %s", CSV_FILE)
        return

    # Bulk insert using execute_values pattern
    cr.execute("DELETE FROM geo_zip_centroid")
    batch_size = 5000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        args = ','.join(
            cr.mogrify("(%s, %s, %s)", r).decode()
            for r in batch
        )
        cr.execute(
            "INSERT INTO geo_zip_centroid (zip_code, latitude, longitude) "
            "VALUES " + args
        )

    _logger.info("Loaded %d ZIP centroids into geo_zip_centroid.", len(rows))
