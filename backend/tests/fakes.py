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


def _words(text: str) -> list[str]:
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash(word: str, n: int) -> int:
    import hashlib
    return int(hashlib.md5(word.encode()).hexdigest(), 16) % n  # noqa: S324  test hashing, not security


def _unit(v: list[float]) -> list[float]:
    norm = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norm for x in v]


class FakeEmbed:
    """Bag-of-words stand-ins for the three models: similar words give similar vectors."""

    def __init__(self):
        self.calls: dict[str, int] = {}

    def dense(self, text: str) -> list[float]:
        v = [0.0] * 384
        for w in _words(text):
            v[_hash(w, 384)] += 1
        return _unit(v)

    def sparse(self, text: str) -> dict:
        counts: dict[int, float] = {}
        for w in _words(text):
            counts[_hash(w, 30522)] = counts.get(_hash(w, 30522), 0) + 1.0
        return {"indices": list(counts), "values": list(counts.values())}

    def colbert(self, text: str) -> list[list[float]]:
        out = []
        for w in _words(text) or ["empty"]:
            v = [0.0] * 128
            v[_hash(w, 128)] = 1.0
            out.append(v)
        return out

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls[path] = self.calls.get(path, 0) + 1
        texts = json.loads(request.read())["texts"]
        assert 1 <= len(texts) <= 64
        if path == "/embed/dense":
            return json_response({"vectors": [self.dense(t) for t in texts], "dimensions": 384})
        if path in ("/embed/sparse", "/embed/sparse/query"):
            return json_response({"vectors": [self.sparse(t) for t in texts]})
        if path in ("/embed/colbert", "/embed/colbert/query"):
            return json_response({"vectors": [self.colbert(t) for t in texts], "dimensions": 128})
        return httpx.Response(404)


class FakeQdrant:
    """Enough of Qdrant's REST API for the pipeline: collections, payload indexes, aliases, upsert,
    delete by filter, and query with dense and sparse prefetch reranked by ColBERT MaxSim."""

    def __init__(self):
        self.collections: dict[str, dict] = {}
        self.aliases: dict[str, str] = {}
        self.points: dict[str, dict] = {}
        self.indexes: dict[str, list] = {}
        self.upserts = 0
        self.api_keys: set[str] = set()

    def _name(self, name: str) -> str:
        return self.aliases.get(name, name)

    @staticmethod
    def _match(payload: dict, cond: dict) -> bool:
        value = payload.get(cond["key"])
        if "match" in cond:
            want = cond["match"]["value"]
            return want in value if isinstance(value, list) else value == want
        if "range" in cond:
            return value is not None and all(
                {"gte": value >= b, "gt": value > b, "lte": value <= b, "lt": value < b}[op]
                for op, b in cond["range"].items())
        return False

    def _passes(self, payload: dict, flt: dict | None) -> bool:
        if not flt:
            return True
        if not all(self._match(payload, c) for c in flt.get("must", [])):
            return False
        should = flt.get("should", [])
        return not should or any(self._match(payload, c) for c in should)

    @staticmethod
    def _cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))

    @staticmethod
    def _sparse(a: dict, b: dict) -> float:
        bv = dict(zip(b["indices"], b["values"], strict=True))
        return sum(v * bv.get(i, 0.0) for i, v in zip(a["indices"], a["values"], strict=True))

    def _maxsim(self, q: list[list[float]], d: list[list[float]]) -> float:
        return sum(max(self._cos(qv, dv) for dv in d) for qv in q)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.api_keys.add(request.headers.get("api-key", ""))
        parts = request.url.path.strip("/").split("/")
        body = json.loads(request.read() or b"{}")
        if parts == ["collections", "aliases"]:
            for action in body["actions"]:
                a = action["create_alias"]
                self.aliases[a["alias_name"]] = a["collection_name"]
            return json_response({"result": True})
        if len(parts) == 2 and parts[0] == "collections":
            name = self._name(parts[1])
            if request.method == "GET":
                return json_response({"result": self.collections[name]}) if name in self.collections \
                    else json_response({"status": "not found"}, 404)
            if request.method == "PUT":
                self.collections[name] = body
                return json_response({"result": True})
        if len(parts) >= 3 and parts[0] == "collections":
            name = self._name(parts[1])
            if name not in self.collections:
                return json_response({"status": "not found"}, 404)
            tail = parts[2:]
            if tail == ["index"]:
                self.indexes.setdefault(name, []).append(body)
                return json_response({"result": True})
            if tail == ["points"] and request.method == "PUT":
                self.upserts += 1
                for p in body["points"]:
                    self.points[p["id"]] = p
                return json_response({"result": {"status": "completed"}})
            if tail == ["points", "delete"]:
                for pid in [k for k, p in self.points.items() if self._passes(p["payload"], body["filter"])]:
                    del self.points[pid]
                return json_response({"result": {"status": "completed"}})
            if tail == ["points", "query"]:
                candidates: set[str] = set()
                for pf in body["prefetch"]:
                    scored = []
                    for pid, p in self.points.items():
                        if not self._passes(p["payload"], pf.get("filter")):
                            continue
                        vec = p["vector"][pf["using"]]
                        score = self._sparse(pf["query"], vec) if pf["using"] == "splade" else self._cos(pf["query"], vec)
                        scored.append((score, pid))
                    candidates |= {pid for _, pid in sorted(scored, reverse=True)[:pf["limit"]]}
                ranked = sorted(((self._maxsim(body["query"], self.points[pid]["vector"]["colbert"]), pid)
                                 for pid in candidates), reverse=True)[:body["limit"]]
                return json_response({"result": {"points": [
                    {"id": pid, "score": s, "payload": self.points[pid]["payload"]} for s, pid in ranked]}})
        return httpx.Response(400)


class FakeParakeet:
    """The Gradio HTTP API of parakeet-transcription-app: upload, call transcribe_file, then an
    event stream ending in `complete` with the dataframe rows as strings (or `error`)."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.uploads: list[str] = []
        self.calls: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/gradio_api/upload":
            name = f"/tmp/gradio/{len(self.uploads)}/audio.webm"
            self.uploads.append(name)
            return json_response([name])
        if path == "/gradio_api/call/transcribe_file" and request.method == "POST":
            body = json.loads(request.read())
            self.calls.append(body)
            return json_response({"event_id": f"e{len(self.calls)}"})
        if path.startswith("/gradio_api/call/transcribe_file/"):
            if self.fail:
                stream = "event: error\ndata: null\n\n"
            else:
                n = len(self.calls)
                rows = [["N/A", "N/A", "Processing failed"]] if n == 99 else [
                    ["0.00", "4.50", f"Part {n}: I check the bank feed."], ["5.00", "9.00", "Then I send a reminder."]]
                table = {"headers": ["Start (s)", "End (s)", "Segment"], "data": rows, "metadata": None}
                stream = ("event: generating\ndata: null\n\nevent: heartbeat\ndata: null\n\n"
                          f"event: complete\ndata: {json.dumps([table, None, None, None, None])}\n\n")
            return httpx.Response(200, content=stream.encode(), headers={"content-type": "text/event-stream"})
        return httpx.Response(404)
