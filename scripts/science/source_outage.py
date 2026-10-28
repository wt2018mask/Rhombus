"""Record failed source acquisition without converting failure into success."""
import json
import socket
from urllib.error import URLError


def record_timeout(error, target, *, resources):
    reason = error.reason if isinstance(error, URLError) else error
    if not (isinstance(reason, (TimeoutError, socket.timeout)) or
            (isinstance(reason,str) and reason.strip().lower() in ('timed out','timeout'))):
        return False
    target.mkdir(parents=True, exist_ok=False)
    with (target/'source-unavailable.json').open('x') as output:
        json.dump({'schema_version':'rhombus-source-outage-v1',
                   'status':'EXTERNAL_HOST_UNREACHABLE_TIMEOUT',
                   'resources_attempted_or_required':resources,
                   'failed_resource_identity':'UNKNOWN_WITHOUT_CALL_SITE_OBSERVATION',
                   'original_bytes_authenticated':False,'sha256':None,'scientific_GO':False},output,sort_keys=True)
    return True
