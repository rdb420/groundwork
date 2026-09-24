"""In-process stand-ins for the services the ingestion pipeline calls. Each is an httpx
MockTransport handler registered in app.httpclient.TRANSPORTS under the service's name."""
import json
from urllib.parse import parse_qs, unquote, urlsplit

import httpx


class FakeS3:
    """Path-style S3: PUT, GET, HEAD, DELETE objects; ListObjectsV2 two keys a page, to exercise paging."""

    def __init__(self, bucket: str = "groundwork"):
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not request.headers.get("authorization", "").startswith("AWS4-HMAC-SHA256 Credential="):
            return httpx.Response(403)
        path = unquote(urlsplit(str(request.url)).path)
        _, _, rest = path.partition(f"/{self.bucket}")
        key = rest.lstrip("/")
        if request.method == "PUT":
            self.objects[key] = request.read()
            return httpx.Response(200)
        if request.method in ("GET", "HEAD") and key:
            if key not in self.objects:
                return httpx.Response(404)
            return httpx.Response(200, content=b"" if request.method == "HEAD" else self.objects[key])
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        if request.method == "GET":
            q = parse_qs(urlsplit(str(request.url)).query)
            prefix = q.get("prefix", [""])[0]
            keys = sorted(k for k in self.objects if k.startswith(prefix))
            start = int(q.get("continuation-token", ["0"])[0])
            page, more = keys[start:start + 2], start + 2 < len(keys)
            body = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in page)
            token = f"<NextContinuationToken>{start + 2}</NextContinuationToken>" if more else ""
            xml = (f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{body}'
                   f"<IsTruncated>{'true' if more else 'false'}</IsTruncated>{token}</ListBucketResult>")
            return httpx.Response(200, content=xml.encode())
        return httpx.Response(400)


def json_response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(data).encode(), headers={"content-type": "application/json"})
