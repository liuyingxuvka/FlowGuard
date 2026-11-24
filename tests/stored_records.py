"""Owner records as an older `req add` stored them, for the readers that must keep reading them."""
import hashlib
import json

from flowguard.map.records import prepare_directory, write_once
from flowguard.map.requests import REQUEST_DIR, offer_path


def stored_as_given(root, identifier, raw, *, offer=None, picked=(), selected=False):
    """A record whose bytes an older `req add` stored as it got them, before 5.1 refused bytes that are no UTF-8 or
    UTF-16 text (5.0.1 stored a Latin-1 request so, and the choice records of 5.1's development code a Latin-1 reply):
    its body, a choice's offer and the sidecar as the archive's writer lays them out, each written once with its
    receipt."""
    item = dict(id=identifier, kind='request' if offer is None else 'choice', sha256=hashlib.sha256(raw).hexdigest(),
                received='2026-11-20T09:00:00+00:00', bytes=len(raw))
    if offer is not None:
        item.update(offer=dict(sha256=hashlib.sha256(offer).hexdigest(), bytes=len(offer)), picked=list(picked),
                    reply='selected' if selected else 'typed')
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))
    write_once(root, REQUEST_DIR / (identifier + '.md'), raw)
    if offer is not None:
        write_once(root, offer_path(identifier), offer)
    write_once(root, REQUEST_DIR / (identifier + '.json'),
               (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8'))
