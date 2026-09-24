"""One place to make HTTP clients for the services Groundwork calls (S3 storage, MinerU, Gotenberg,
Parakeet, the embedding and extraction sidecars, Qdrant, Neo4j). Tests register an
httpx.MockTransport under the service's name, so every client talks to an in-process fake."""
import httpx

# name -> transport; set by tests, empty in production
TRANSPORTS: dict[str, httpx.BaseTransport] = {}


def client(name: str, *, base_url: str = "", timeout: float = 60, verify: str | bool = True,
           headers: dict[str, str] | None = None) -> httpx.Client:
    transport = TRANSPORTS.get(name)
    kwargs: dict = {"base_url": base_url, "timeout": timeout, "headers": headers or {}}
    if transport is not None:
        kwargs["transport"] = transport
    else:
        kwargs["verify"] = verify
    return httpx.Client(**kwargs)


def verify_option(ca_file: str) -> str | bool:
    """A CA bundle path for services with their own certificate (Qdrant's TLS), else the system store."""
    return ca_file or True
