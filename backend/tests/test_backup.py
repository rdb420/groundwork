from app import backup
from tests.conftest import sign_in


def test_backup_round_trip(client):
    sign_in(client, "staff@example.com.au")
    path = backup.run()
    info = backup.restore_check(path)
    assert path.exists() and info["users"] >= 1
