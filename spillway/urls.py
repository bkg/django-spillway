import re

# URL path separator, cannot rely on os.sep as it varies by platform.
sep = r'/'
# Regex for an optional file extension.
format_suffix = r'(?:\.(?P<format>[\w.]+))?'
# Regex groups for a tile URL in {z}/{x}/{y}.{format} order.
tile = ('(?P<z>\d+)',
        '(?P<x>\d+)',
        '(?P<y>\d+)%s/?$' % format_suffix)
tileregex = sep.join(tile)

def tilepath(regex):
    """Appends a tile path regex to a url path."""
    return r''.join((regex, tileregex))

def is_tilepath(path):
    """Returns true for map tile url formatted paths."""
    return bool(re.search(tileregex, path))
