from pathlib import Path

SERVICE = Path(__file__).resolve().parent.parent / "systemd" / "kidage.service"


def test_hardened_service_uses_writable_working_directory():
    unit = SERVICE.read_text()

    assert "ProtectSystem=strict" in unit
    assert "StateDirectory=kidage" in unit
    assert "WorkingDirectory=/var/lib/kidage" in unit
    assert "WorkingDirectory=/opt/kidage" not in unit
