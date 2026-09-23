"""Size checks before opening Office files. They are zip archives, and a small upload can expand
to gigabytes when read; check the declared sizes first."""
import zipfile
from pathlib import Path

LIGHT_ABOVE = 150 * 1024 * 1024  # expanded size above which a workbook gets the lighter read
REFUSE_ABOVE = 1024 * 1024 * 1024  # expanded size nobody's working file needs
MAX_RATIO = 200  # expanded size over compressed size; real Office files sit well below this


def expanded_size(path: Path) -> int:
    with zipfile.ZipFile(path) as z:
        return sum(i.file_size for i in z.infolist())


def too_big(path: Path) -> str | None:
    """A reason to refuse reading the file, or None."""
    try:
        size = expanded_size(path)
    except zipfile.BadZipFile:
        return "It isn't a valid Office file, so it wasn't read."
    compressed = max(path.stat().st_size, 1)
    if size > REFUSE_ABOVE or size / compressed > MAX_RATIO:
        return "It expands to an unusually large size, so it wasn't read. Check it by hand."
    return None
