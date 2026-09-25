from __future__ import annotations

import http.server
import logging
import threading
from pathlib import Path

import typing_extensions as T

from idanb import utils

from ._config import CONFIG

if T.TYPE_CHECKING:
    import io


_logger = logging.getLogger(__name__)


ALLOWED_FILE_EXTENSIONS = {
    ".css",
    ".js",
}


class AssetRequestHandler(http.server.SimpleHTTPRequestHandler):
    _directory: T.ClassVar[str | None] = None

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs, directory=self._directory)

    def __init_subclass__(cls, *, directory: str | None = None) -> None:
        cls._directory = directory
        return super().__init_subclass__()

    # Allow cross-origin requests.

    @T.override
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        return super().end_headers()

    # Restrict what files are being served.

    @T.override
    def send_head(self) -> io.BytesIO | T.BinaryIO | None:
        path = Path(self.translate_path(self.path))
        if path.is_dir() or path.suffix not in ALLOWED_FILE_EXTENSIONS:
            self.send_error(http.HTTPStatus.NOT_FOUND, "File not found")
            return None

        return super().send_head()

    # Don't log to stdout.

    @T.override
    def log_message(self, format: str, *args: object) -> None:
        _logger.info(format, *args)


@utils.cache
def asset_server(rootdir: Path) -> str:
    """Serve static assets on localhost (if not already).

    When first called, starts an HTTP server in a background thread.
    This server will keep running until the program is terminated,
    serving assets from this project's directory on a radom localhost port.

    Returns:
        URL the server is listening on.
    """
    if CONFIG.get("developer") is not True:
        errmsg = "asset server is not allowed in production"
        e = RuntimeError(errmsg)
        e.add_note(
            "Add 'developer: true' to 'config.yaml' to enable asset server."
        )
        raise e

    class RequestHandler(AssetRequestHandler, directory=str(rootdir)):
        pass

    server = http.server.ThreadingHTTPServer(("localhost", 0), RequestHandler)
    address, port, *_ = server.server_address

    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    url = f"http://{address}:{port}"
    _logger.info("Serving assets on: %s", url)
    return url
