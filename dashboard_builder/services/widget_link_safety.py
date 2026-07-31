# -*- coding: utf-8 -*-
"""Safe link construction for attribute_grid (and future SQL-driven links).

Pure — no ORM, no I/O.

Policy (v5, user-decided): URL contents are administrator-controlled — there is
NO hardcoded identifier denylist here. What this module DOES enforce, always:
  • scheme allow-listing per link type, re-checked AFTER substitution
    (an SQL value could be ``javascript:...``);
  • per-part percent-encoding (path segment vs query value vs tel vs mailto);
  • http only for localhost/127.0.0.1/*.localhost hosts, https elsewhere;
  • ``internal`` = root-relative, no scheme, no protocol-relative ``//``;
  • missing/None placeholder value → link disabled (returns None);
  • substituted values never appear in raised errors or logs.

Server-side authorization on internal routes is the real security boundary —
a link is a pointer, never an access grant.
"""

import re
from urllib.parse import quote

_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')
_FORBIDDEN_SCHEME_RE = re.compile(
    r'(?i)^\s*(javascript|data|vbscript|file|about|blob):')
_TEL_ALLOWED_RE = re.compile(r'^[0-9+\-() .#*]{1,40}$')
_MAILTO_RE = re.compile(r'^[^@\s]+@[^@\s]+$')
_CTRL_RE = re.compile(r'[\x00-\x1f\x7f]')

_LOCAL_HOSTS_RE = re.compile(
    r'(?i)^(localhost|127\.0\.0\.1|[a-z0-9-]+\.localhost)(:\d+)?$')


def _is_http_url_ok(url):
    """https anywhere; http only for the localhost family."""
    m = re.match(r'(?i)^(https?)://([^/?#]+)', url)
    if not m:
        return False
    scheme, host = m.group(1).lower(), m.group(2)
    if scheme == 'https':
        return True
    return bool(_LOCAL_HOSTS_RE.match(host))


def _encode_for(link_type, part, value):
    """Percent-encode a substituted value for its position.

    Encoding is per link type AND per URL part — a path segment, a query
    value, a tel number, and a mailto address all encode differently.
    """
    s = str(value)
    if link_type == 'tel':
        return s  # validated against _TEL_ALLOWED_RE afterwards, not encoded
    if link_type == 'mailto':
        return s  # validated afterwards; encoding an address breaks it
    if part == 'query':
        return quote(s, safe='')
    # path segment (also the default for internal links)
    return quote(s, safe='')


def substitute(template, values, link_type):
    """Fill ``{alias}`` placeholders. Returns None when any referenced value
    is missing/None (link disabled), else the substituted string."""
    out = []
    last = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        name = m.group(1)
        if name not in values or values[name] is None:
            return None
        prefix = template[last:m.start()]
        out.append(prefix)
        # Decide part by looking left of the placeholder: after '?' or '&' or
        # '=' we are in the query; before that, path.
        seen = ''.join(out)
        part = 'query' if ('?' in seen or '=' in prefix or '&' in prefix) else 'path'
        out.append(_encode_for(link_type, part, values[name]))
        last = m.end()
    out.append(template[last:])
    return ''.join(out)


def validate_final(link_type, url):
    """Post-substitution validation. True = safe to emit."""
    if not url or _CTRL_RE.search(url) or _FORBIDDEN_SCHEME_RE.match(url):
        return False
    if link_type == 'url':
        return _is_http_url_ok(url)
    if link_type == 'internal':
        # Root-relative only. '//host' is protocol-relative and '/\' is its
        # browser-tolerated twin — both escape the origin, both rejected.
        return url.startswith('/') and not url.startswith('//') \
            and not url.startswith('/\\')
    if link_type == 'tel':
        return bool(_TEL_ALLOWED_RE.match(url))
    if link_type == 'mailto':
        return bool(_MAILTO_RE.match(url))
    return False


def build_link(link_type, template, values, new_tab=False):
    """Return a render-ready link dict or None (no link).

    None is the universal disable path: unknown type, empty template, missing
    placeholder value, or a post-substitution validation failure.
    """
    if link_type in (None, '', 'none') or not template:
        return None
    if link_type not in ('url', 'tel', 'mailto', 'internal'):
        return None
    substituted = substitute(template, values or {}, link_type)
    if substituted is None:
        return None
    substituted = substituted.strip()
    if not validate_final(link_type, substituted):
        return None
    if link_type == 'tel':
        # RFC 3966 visual separators (space, dot, parens, hyphen) are display
        # sugar — strip them all for a uniformly dialable href.
        href = 'tel:' + re.sub(r'[ ().\-]', '', substituted)
    elif link_type == 'mailto':
        href = 'mailto:' + substituted
    else:
        href = substituted
    link = {'href': href, 'new_tab': bool(new_tab)}
    if link['new_tab']:
        link['rel'] = 'noopener noreferrer'
    return link


def template_statically_unsafe(link_type, template):
    """Save-time template lint (validators call this). Light by design —
    placeholders make full validation impossible until render. Rejects only
    what is PROVABLY wrong in the literal text."""
    if not template:
        return False
    if _FORBIDDEN_SCHEME_RE.match(template) or _CTRL_RE.search(template):
        return True
    if link_type == 'url':
        # Literal scheme required up front so a template can't smuggle one in
        # via substitution position.
        if not re.match(r'(?i)^https?://', template):
            return True
        if not _is_http_url_ok(template.replace('{', 'x').replace('}', 'x')):
            # http on a non-local host is statically knowable from the literal
            # host part when the host contains no placeholder.
            host = re.match(r'(?i)^https?://([^/?#]*)', template)
            if host and '{' not in host.group(1):
                return True
    if link_type == 'internal':
        if not template.startswith('/') or template.startswith('//'):
            return True
    return False
