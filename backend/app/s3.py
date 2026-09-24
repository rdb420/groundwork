"""A small S3 client for Supabase Storage's S3 endpoint (or MinIO): put, get, head, delete and list,
signed with AWS Signature Version 4. Path-style URLs, so any on-prem endpoint works. No vendor SDK,
in keeping with the rest of Groundwork's HTTP clients."""
import hashlib
import hmac
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree

from . import httpclient

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
UNRESERVED = "-_.~"


class S3Error(RuntimeError):
    def __init__(self, status: int, what: str):
        super().__init__(f"Storage returned {status} for {what}.")
        self.status = status


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sign(method: str, url: str, headers: dict[str, str], payload_sha256: str, *, access_key: str,
         secret_key: str, region: str, now: datetime | None = None, service: str = "s3") -> dict[str, str]:
    """Return the headers to send, including x-amz-date, x-amz-content-sha256 and Authorization."""
    now = now or datetime.now(UTC)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    parts = urlsplit(url)
    out = {k.lower(): str(v).strip() for k, v in headers.items()}
    out["host"] = parts.netloc
    out["x-amz-date"] = amz_date
    out["x-amz-content-sha256"] = payload_sha256
    canonical_uri = quote(parts.path or "/", safe="/" + UNRESERVED)
    query = []
    for pair in filter(None, parts.query.split("&")):
        k, _, v = pair.partition("=")
        # The URL already contains AWS-encoded parameters; decode once before
        # constructing the canonical form so they are not double-escaped.
        query.append((quote(unquote(k), safe=UNRESERVED), quote(unquote(v), safe=UNRESERVED)))
    canonical_query = "&".join(f"{k}={v}" for k, v in sorted(query))
    signed = sorted(out)
    canonical_headers = "".join(f"{k}:{' '.join(out[k].split())}\n" for k in signed)
    signed_headers = ";".join(signed)
    canonical_request = "\n".join([method, canonical_uri, canonical_query, canonical_headers, signed_headers,
                                   payload_sha256])
    scope = f"{day}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope,
                                hashlib.sha256(canonical_request.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_key}".encode(), day), region), service), "aws4_request")
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    out["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed_headers}, "
                            f"Signature={signature}")
    out.pop("host")  # httpx sets it from the URL
    return out


def _encode_query(params: dict[str, str]) -> str:
    return "&".join(f"{quote(k, safe=UNRESERVED)}={quote(v, safe=UNRESERVED)}" for k, v in sorted(params.items()))


class S3:
    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str,
                 ca_file: str = "", timeout: float = 120):
        self.base = endpoint.rstrip("/")
        self.bucket = bucket
        self.access_key, self.secret_key, self.region = access_key, secret_key, region
        self.http = httpclient.client("s3", timeout=timeout, verify=httpclient.verify_option(ca_file))

    def _url(self, key: str = "", params: dict[str, str] | None = None) -> str:
        path = f"{self.base}/{self.bucket}" + (f"/{quote(key, safe='/' + UNRESERVED)}" if key else "")
        return path + (f"?{_encode_query(params)}" if params else "")

    def _headers(self, method: str, url: str, payload_sha256: str = EMPTY_SHA256,
                 extra: dict[str, str] | None = None) -> dict[str, str]:
        return sign(method, url, extra or {}, payload_sha256, access_key=self.access_key,
                    secret_key=self.secret_key, region=self.region)

    def put_file(self, key: str, path: Path, content_type: str = "application/octet-stream",
                 sha256: str | None = None) -> None:
        digest = sha256 or _file_sha256(path)
        url = self._url(key)
        extra = {"content-type": content_type, "content-length": str(path.stat().st_size)}
        with path.open("rb") as f:
            r = self.http.put(url, content=f, headers=self._headers("PUT", url, digest, extra))
        if r.status_code >= 300:
            raise S3Error(r.status_code, f"saving {key}")

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        url = self._url(key)
        r = self.http.put(url, content=data, headers=self._headers(
            "PUT", url, hashlib.sha256(data).hexdigest(), {"content-type": content_type}))
        if r.status_code >= 300:
            raise S3Error(r.status_code, f"saving {key}")

    def stream(self, key: str, chunk: int = 1024 * 1024) -> Iterator[bytes]:
        url = self._url(key)
        with self.http.stream("GET", url, headers=self._headers("GET", url)) as r:
            if r.status_code >= 300:
                raise S3Error(r.status_code, f"reading {key}")
            yield from r.iter_bytes(chunk)

    def exists(self, key: str) -> bool:
        url = self._url(key)
        r = self.http.head(url, headers=self._headers("HEAD", url))
        if r.status_code == 404:
            return False
        if r.status_code >= 300:
            raise S3Error(r.status_code, f"checking {key}")
        return True

    def delete(self, key: str) -> None:
        url = self._url(key)
        r = self.http.delete(url, headers=self._headers("DELETE", url))
        if r.status_code >= 300 and r.status_code != 404:
            raise S3Error(r.status_code, f"deleting {key}")

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = ""
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            url = self._url(params=params)
            r = self.http.get(url, headers=self._headers("GET", url))
            if r.status_code >= 300:
                raise S3Error(r.status_code, f"listing {prefix}")
            root = ElementTree.fromstring(r.content)
            ns = root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""
            keys += [el.text or "" for el in root.iter(f"{ns}Key")]
            truncated = (root.findtext(f"{ns}IsTruncated") or "false").lower() == "true"
            token = root.findtext(f"{ns}NextContinuationToken") or ""
            if not truncated or not token:
                return keys


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()
