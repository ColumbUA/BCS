"""Comprehensive backend tests for РРР company management app.

Covers:
  - Auth: login, wrong password, brute-force lockout (isolated test user)
  - 2FA: setup + verify with pyotp-generated code
  - Structure: auth-guarded, КОЛУМБ on company commander
  - Soldiers: seed-from-bchs, CRUD, document upload/download/delete
  - Ammo: preset/typical, CRUD, summary
  - Notifications: /notifications/material (material notifications)
  - RBAC: VIEWER / PLATOON_LEADER forbidden on protected writes
"""
import os
import io
import time
import pyotp
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://bcs-roster-control.preview.emergentagent.com").rstrip('/')
API = f"{BASE_URL}/api"


def _login(username: str, password: str, totp: str = None):
    body = {"username": username, "password": password}
    if totp:
        body["totp_code"] = totp
    r = requests.post(f"{API}/auth/login", json=body, timeout=30)
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login("admin", "rota2026")
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def kr_token():
    r = _login("kr", "kolumb2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def material_token():
    r = _login("material", "venom2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def platoon_token():
    r = _login("kv1", "platoon1")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = _login("viewer", "view2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


# ============ AUTH ============

class TestAuth:
    def test_login_success_admin(self, admin_token):
        # token is already obtained via fixture
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_login_returns_user_and_role(self):
        r = _login("admin", "rota2026")
        assert r.status_code == 200
        data = r.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "COMMANDER"
        assert "id" in data["user"]

    def test_login_wrong_password(self):
        r = _login("viewer", "WRONG_PASSWORD_XYZ")
        # may be 401 or 423 if previous runs left counter; accept both
        assert r.status_code in (401, 423), r.text

    def test_auth_me_with_token(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["role"] == "COMMANDER"

    def test_structure_without_token(self):
        r = requests.get(f"{API}/structure", timeout=30)
        assert r.status_code == 401

    def test_structure_with_token(self, admin_token):
        r = requests.get(f"{API}/structure", headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("total_personnel") == 109
        # КОЛУМБ on company commander — scan all subunits for position "командир роти"
        found_kolumb = False
        found_amelkin = False
        for sub in data["subunits"].values():
            for sq in sub.get("squads", {}).values():
                for p in sq.get("positions", []):
                    pos = (p.get("position") or "").lower()
                    if pos.startswith("командир роти") or pos == "командир роти":
                        if (p.get("callsign") or "").upper() == "КОЛУМБ":
                            found_kolumb = True
                        if "АМЕЛЬКІН" in (p.get("fio") or "").upper():
                            found_amelkin = True
        assert found_kolumb, "КОЛУМБ callsign not found on Командир роти"
        assert found_amelkin, "АМЕЛЬКІН not found on Командир роти"


class TestBruteForceLockout:
    """Uses a throwaway username to avoid locking test accounts."""

    def test_lockout_after_5_failed_attempts(self):
        uname = "brute_test_user_xyz"
        # Ensure we know this username doesn't exist (should return 401)
        for i in range(5):
            r = _login(uname, f"wrong_{i}")
            assert r.status_code in (401, 423)
        r = _login(uname, "another_wrong")
        # After 5 failed attempts should be 423 (locked)
        assert r.status_code == 423, f"expected 423 after 5 fails, got {r.status_code} {r.text}"


class Test2FA:
    def test_2fa_setup_and_verify(self, viewer_token):
        # setup
        r = requests.post(f"{API}/auth/2fa/setup", headers=auth_headers(viewer_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "secret" in d
        assert d["qr_data_uri"].startswith("data:image/png;base64,")
        secret = d["secret"]
        # generate valid TOTP
        code = pyotp.TOTP(secret).now()
        r = requests.post(f"{API}/auth/2fa/verify",
                          headers=auth_headers(viewer_token),
                          json={"code": code}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is True
        # disable again to not break next test logins
        r = requests.post(f"{API}/auth/2fa/disable",
                          headers=auth_headers(viewer_token), timeout=30)
        assert r.status_code == 200


# ============ SOLDIERS ============

class TestSoldiers:
    def test_seed_soldiers_from_bchs(self, admin_token):
        r = requests.post(f"{API}/soldiers/seed-from-bchs",
                          headers=auth_headers(admin_token), timeout=60)
        assert r.status_code == 200
        # first run will insert some; second run inserted=0. We only assert request ok.
        assert "inserted" in r.json()

    def test_list_soldiers_not_empty(self, admin_token):
        r = requests.get(f"{API}/soldiers", headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        lst = r.json()
        assert isinstance(lst, list)
        assert len(lst) >= 20, f"expected >=20 soldiers, got {len(lst)}"

    def test_viewer_cannot_seed(self, viewer_token):
        r = requests.post(f"{API}/soldiers/seed-from-bchs",
                          headers=auth_headers(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_update_soldier_fields(self, admin_token):
        r = requests.get(f"{API}/soldiers", headers=auth_headers(admin_token), timeout=30)
        soldiers = r.json()
        assert soldiers
        sid = soldiers[0]["id"]
        payload = dict(soldiers[0])
        payload["mobilized_at"] = "2024-02-01"
        payload["bzvp_passed_at"] = "2024-03-15"
        payload["ktz_passed_at"] = "2024-04-10"
        payload["education"] = [{"degree": "бакалавр", "institution": "ТNU", "year": "2018", "specialty": "радіо"}]
        payload["certificates"] = [{"name": "TEST cert", "issued_at": "2024-01-01", "issuer": "test"}]
        # remove id/created_at
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        payload.pop("documents", None)
        r = requests.put(f"{API}/soldiers/{sid}", json=payload,
                         headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        upd = r.json()
        assert upd["mobilized_at"] == "2024-02-01"
        assert upd["bzvp_passed_at"] == "2024-03-15"
        assert upd["ktz_passed_at"] == "2024-04-10"
        assert len(upd["education"]) == 1
        assert len(upd["certificates"]) == 1

        # GET to confirm persistence
        r = requests.get(f"{API}/soldiers/{sid}", headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["ktz_passed_at"] == "2024-04-10"


# ============ DOCUMENTS ============

class TestDocuments:
    def test_upload_download_delete_document(self, admin_token):
        # pick a soldier
        r = requests.get(f"{API}/soldiers", headers=auth_headers(admin_token), timeout=30)
        sid = r.json()[0]["id"]
        # upload
        content = b"%PDF-1.4\nTEST DOC CONTENT\n"
        files = {"file": ("passport.pdf", io.BytesIO(content), "application/pdf")}
        data = {"doc_type": "passport"}
        r = requests.post(f"{API}/soldiers/{sid}/documents",
                          headers=auth_headers(admin_token), files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        file_id = r.json()["file_id"]
        assert file_id

        # download
        r = requests.get(f"{API}/documents/{file_id}",
                         headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.content == content
        cd = r.headers.get("Content-Disposition", "")
        assert "passport.pdf" in cd or "UTF-8" in cd

        # delete
        r = requests.delete(f"{API}/documents/{file_id}",
                            headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200

        # verify removed from soldier
        r = requests.get(f"{API}/soldiers/{sid}", headers=auth_headers(admin_token), timeout=30)
        docs = r.json().get("documents") or {}
        assert "passport" not in docs

    def test_upload_invalid_doc_type(self, admin_token):
        r = requests.get(f"{API}/soldiers", headers=auth_headers(admin_token), timeout=30)
        sid = r.json()[0]["id"]
        files = {"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")}
        data = {"doc_type": "unknown_garbage"}
        r = requests.post(f"{API}/soldiers/{sid}/documents",
                          headers=auth_headers(admin_token), files=files, data=data, timeout=30)
        assert r.status_code == 400


# ============ AMMO ============

class TestAmmo:
    def test_preset_ammo(self, admin_token):
        r = requests.post(f"{API}/ammo/preset/typical",
                          headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["inserted"] >= 20

    def test_ammo_summary_contains_ak74_and_brennen(self, admin_token):
        r = requests.get(f"{API}/ammo/summary", headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "by_weapon" in data
        bw = data["by_weapon"]
        assert "АК-74" in bw
        # AK-74 ~ (5+8+18+26+24+14+3) * 150 = 98*150 = 14700
        assert bw["АК-74"] == 14700
        # CZ BREN (2+2+3+2+2) * 210 = 11*210 = 2310
        cz_keys = [k for k in bw.keys() if "BREN" in k]
        assert cz_keys, f"CZ BREN not found in {list(bw.keys())}"
        assert bw[cz_keys[0]] == 2310
        assert "РГД-5" in bw

    def test_ammo_crud(self, admin_token):
        payload = {"node_path": "Управління роти", "weapon": "АК-74",
                   "ammo_type": "патрон", "caliber": "5.45×39", "qty": 300}
        r = requests.post(f"{API}/ammo", json=payload,
                          headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        aid = r.json()["id"]
        # update
        payload["qty"] = 500
        r = requests.put(f"{API}/ammo/{aid}", json=payload,
                         headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["qty"] == 500
        # delete
        r = requests.delete(f"{API}/ammo/{aid}",
                            headers=auth_headers(admin_token), timeout=30)
        assert r.status_code == 200


# ============ NOTIFICATIONS ============

class TestNotifications:
    def test_material_notifications(self, material_token):
        r = requests.get(f"{API}/notifications/material",
                         headers=auth_headers(material_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "ОРЛОВ" in d["recipient"] and "ВЕНОМ" in d["recipient"]
        assert "issues" in d
        assert isinstance(d["issues"], list)
        # expect at least 20 incomplete (all seeded lack docs)
        assert d["with_issues"] >= 20
        # missing includes Паспорт / ІПН / Військовий квиток
        for issue in d["issues"][:3]:
            miss_set = set(issue["missing_codes"])
            assert "passport" in miss_set
            assert "ipn" in miss_set
            assert "military_id" in miss_set


# ============ RBAC ============

class TestRBAC:
    def test_viewer_cannot_create_equipment(self, viewer_token):
        r = requests.post(f"{API}/equipment",
                          headers=auth_headers(viewer_token),
                          json={"node_path": "Управління роти", "category": "ОВТ",
                                "name": "TEST_x", "type": "штатний", "qty": 1},
                          timeout=30)
        assert r.status_code == 403

    def test_platoon_leader_cannot_run_preset_typical(self, platoon_token):
        r = requests.post(f"{API}/equipment/preset/typical",
                          headers=auth_headers(platoon_token), timeout=60)
        assert r.status_code == 403

    def test_platoon_leader_cannot_seed_soldiers(self, platoon_token):
        r = requests.post(f"{API}/soldiers/seed-from-bchs",
                          headers=auth_headers(platoon_token), timeout=30)
        assert r.status_code == 403


# ============ EXPORTS (smoke) ============

class TestExportsSmoke:
    def test_export_orgstructure_requires_auth(self):
        r = requests.get(f"{API}/export/orgstructure.xml", timeout=30)
        assert r.status_code == 401

    def test_export_zip_with_auth(self, admin_token):
        r = requests.get(f"{API}/export/full-package.zip",
                         headers=auth_headers(admin_token), timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        assert len(r.content) > 5000
