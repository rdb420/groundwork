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


class FakeMinerU:
    """mineru-api's async task flow: POST /tasks (202), GET /tasks/{id}/result (202 while
    pending, then 200 with md_content, content_list as a JSON string, and images as data URIs)."""

    def __init__(self, pending_polls: int = 1, fail: bool = False):
        self.pending_polls = pending_polls
        self.fail = fail
        self.tasks: dict[str, dict] = {}
        self.received: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/tasks":
            body = request.read()
            form = {}
            for part in body.split(b"\r\n--"):
                head, _, value = part.partition(b"\r\n\r\n")
                if b'name="' in head and b"filename=" not in head:
                    name = head.split(b'name="', 1)[1].split(b'"', 1)[0].decode()
                    form[name] = value.rstrip(b"\r\n-").decode(errors="replace")
            self.received.append({"form": form, "file_bytes": body})
            tid = f"t{len(self.tasks) + 1}"
            self.tasks[tid] = {"polls": 0, "form": form}
            return json_response({"task_id": tid, "status": "pending"}, 202)
        if request.method == "GET" and path.startswith("/tasks/") and path.endswith("/result"):
            task = self.tasks.get(path.split("/")[2])
            if task is None:
                return json_response({"detail": "Task not found"}, 404)
            if self.fail:
                return json_response({"status": "failed"}, 409)
            task["polls"] += 1
            if task["polls"] <= self.pending_polls:
                return json_response({"status": "processing"}, 202)
            start = int(task["form"].get("start_page_id", 0) or 0)
            content = [
                {"type": "text", "text": "Residential tenancy agreement", "text_level": 1, "page_idx": 0},
                {"type": "text", "text": f"Rent is due every Monday. Window starting {start}.", "page_idx": 0},
                {"type": "header", "text": "Page header to skip", "page_idx": 0},
                {"type": "table", "table_body": "<table><tr><th>Room</th><th>Rent</th></tr><tr><td>3</td><td>$220</td></tr></table>",
                 "table_caption": ["Rooms and rent"], "page_idx": 1},
                {"type": "image", "img_path": "images/a.jpg", "image_caption": ["Floor plan"], "page_idx": 1},
            ]
            png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            return json_response({"results": {"doc": {
                "md_content": "# Residential tenancy agreement\n\nRent is due every Monday.\n",
                "content_list": json.dumps(content), "images": {"a.jpg": f"data:image/png;base64,{png}"}}}})
        if path == "/health":
            return json_response({"status": "healthy"})
        return httpx.Response(404)


class FakeGotenberg:
    def __init__(self):
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/forms/libreoffice/convert":
            self.calls += 1
            return httpx.Response(200, content=b"%PDF-1.4 fake converted document")
        return httpx.Response(404)
