from pathlib import Path

SERVICE = Path(__file__).resolve().parent.parent / "systemd" / "beanclock.service"


def test_hardened_service_uses_writable_working_directory():
    unit = SERVICE.read_text()

    assert "ProtectSystem=strict" in unit
    assert "StateDirectory=beanclock" in unit
    assert "WorkingDirectory=/var/lib/beanclock" in unit
    assert "WorkingDirectory=/opt/beanclock" not in unit
