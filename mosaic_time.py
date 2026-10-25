# Prints the newest time of a WMS layer from GetCapabilities on stdin (ISO 8601, UTC), e.g. 2026-10-25T16:00:00Z.
# Usage: curl ...GetCapabilities... | python mosaic_time.py <layer name>
import sys, re
import xml.etree.ElementTree as ET

name = sys.argv[1]
root = ET.parse(sys.stdin).getroot()
ns = {'w': 'http://www.opengis.net/wms'}
for layer in root.iter('{http://www.opengis.net/wms}Layer'):
    if layer.findtext('w:Name', namespaces=ns) != name:
        continue
    dim = layer.find("w:Dimension[@name='time']", ns)
    if dim is None:
        break
    iso = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z'
    default = (dim.get('default') or '').strip()
    if re.fullmatch(iso, default):
        print(default); sys.exit(0)
    # "current" or nothing: the latest listed time (a list, or start/end/period intervals)
    times = re.findall(iso, dim.text or '')
    if times:
        print(max(times)); sys.exit(0)
    break
sys.exit('no time found for ' + name)
