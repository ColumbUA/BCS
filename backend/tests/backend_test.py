"""Backend API tests for РРР company management app."""
import os
import io
import zipfile
import xml.etree.ElementTree as ET
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://bcs-roster-control.preview.emergentagent.com").rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============== STRUCTURE & CONFIG ==============
def test_structure(session):
    r = session.get(f"{API}/structure", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("total_personnel") == 109
    assert len(d.get("order", [])) == 7


def test_config(session):
    r = session.get(f"{API}/config", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "штатний" in d["equipment_types"] and "позаштатний" in d["equipment_types"]
    assert len(d["equipment_categories"]) > 0
    assert len(d["interaction_channels"]) > 0


# ============== EQUIPMENT CRUD ==============
def test_equipment_crud(session):
    payload = {
        "node_path": "Управління роти", "category": "Засіб зв'язку",
        "name": "TEST_radio_X", "type": "позаштатний", "qty": 3, "state": "справний"
    }
    r = session.post(f"{API}/equipment", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    eq = r.json()
    eid = eq["id"]
    assert eq["name"] == "TEST_radio_X"
    assert eq["type"] == "позаштатний"

    # filter list
    r = session.get(f"{API}/equipment", params={"node_path": "Управління роти"}, timeout=30)
    assert r.status_code == 200
    assert any(e["id"] == eid for e in r.json())

    # update
    r = session.put(f"{API}/equipment/{eid}", json={"qty": 5, "notes": "TEST_updated"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["qty"] == 5
    assert r.json()["notes"] == "TEST_updated"

    # delete
    r = session.delete(f"{API}/equipment/{eid}", timeout=30)
    assert r.status_code == 200
    r = session.delete(f"{API}/equipment/{eid}", timeout=30)
    assert r.status_code == 404


def test_equipment_preset_typical(session):
    r = session.post(f"{API}/equipment/preset/typical", timeout=60)
    assert r.status_code == 200
    assert r.json()["inserted"] == 33


def test_equipment_summary(session):
    r = session.get(f"{API}/equipment/summary", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "by_category" in d and "by_type" in d
    assert d["by_type"].get("штатний", 0) > 100  # ~198 typical units


# ============== INTERACTIONS CRUD ==============
def test_interactions_crud(session):
    payload = {
        "source": "Управління роти", "target": "TEST_target",
        "channel": "радіо УКХ", "freq": "RC-99", "callsign": "TEST_CS", "purpose": "TEST_purpose"
    }
    r = session.post(f"{API}/interactions", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    iid = r.json()["id"]

    r = session.get(f"{API}/interactions", timeout=30)
    assert r.status_code == 200
    assert any(i["id"] == iid for i in r.json())

    # update via PUT
    upd = dict(payload, callsign="TEST_CS2")
    r = session.put(f"{API}/interactions/{iid}", json=upd, timeout=30)
    assert r.status_code == 200
    assert r.json()["callsign"] == "TEST_CS2"

    r = session.delete(f"{API}/interactions/{iid}", timeout=30)
    assert r.status_code == 200
    r = session.delete(f"{API}/interactions/{iid}", timeout=30)
    assert r.status_code == 404


def test_interactions_preset(session):
    r = session.post(f"{API}/interactions/preset/typical", timeout=30)
    assert r.status_code == 200
    assert r.json()["inserted"] == 11
    r = session.get(f"{API}/interactions", timeout=30)
    assert len(r.json()) == 11


# ============== EXPORTS ==============
def _parse_xml(content):
    root = ET.fromstring(content)
    return root


def test_export_orgstructure_xml(session):
    r = session.get(f"{API}/export/orgstructure.xml", timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/xml")
    root = _parse_xml(r.content)
    ns = "{http://schemas.microsoft.com/project}"
    tasks = root.findall(f".//{ns}Task")
    resources = root.findall(f".//{ns}Resource")
    assert len(tasks) > 100  # 109+ positions + units
    # Check pozashtatny group present in resources after preset
    groups = [g.text for g in root.findall(f".//{ns}Resource/{ns}Group")]
    assert "штатний" in groups


def test_export_command_xml(session):
    r = session.get(f"{API}/export/command.xml", timeout=60)
    assert r.status_code == 200
    root = _parse_xml(r.content)
    ns = "{http://schemas.microsoft.com/project}"
    tasks = root.findall(f".//{ns}Task")
    # 1 root + 7 phases + 30 sub-tasks = 38
    assert len(tasks) == 38


def test_export_interactions_xml(session):
    r = session.get(f"{API}/export/interactions.xml", timeout=60)
    assert r.status_code == 200
    root = _parse_xml(r.content)
    ns = "{http://schemas.microsoft.com/project}"
    tasks = root.findall(f".//{ns}Task")
    assert len(tasks) > 11  # root + channels + 11 links


def test_export_zip(session):
    r = session.get(f"{API}/export/full-package.zip", timeout=60)
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert len(names) == 5
    xml_count = sum(1 for n in names if n.endswith(".xml"))
    csv_count = sum(1 for n in names if n.endswith(".csv"))
    assert xml_count == 3 and csv_count == 2


def test_pozashtatny_in_export(session):
    """Add a pozashtatny equipment, ensure it appears in XML with Group=позаштатний."""
    payload = {
        "node_path": "Управління роти", "category": "БпЛА",
        "name": "TEST_pozashtatny_drone", "type": "позаштатний", "qty": 1
    }
    r = session.post(f"{API}/equipment", json=payload, timeout=30)
    assert r.status_code == 200
    eid = r.json()["id"]
    try:
        r = session.get(f"{API}/export/orgstructure.xml", timeout=60)
        root = _parse_xml(r.content)
        ns = "{http://schemas.microsoft.com/project}"
        # Find resources with Group=позаштатний
        found = False
        for res in root.findall(f".//{ns}Resource"):
            grp = res.find(f"{ns}Group")
            name = res.find(f"{ns}Name")
            if grp is not None and grp.text == "позаштатний" and name is not None and "TEST_pozashtatny_drone" in (name.text or ""):
                found = True
                break
        assert found, "позаштатний resource not found in XML export"
    finally:
        session.delete(f"{API}/equipment/{eid}", timeout=30)
