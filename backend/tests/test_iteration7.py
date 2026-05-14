"""Iteration 7 tests:
1. Refactor regression: CRUD soldiers/transfers/warehouse/backup still work
2. PLATOON_LEADER scope (kv1)
3. PLATOON_LEADER + transfers
4. Audit log (write + read + RBAC + filters)
5. Audit TTL index 90 days
6. PDF export (admin + PLATOON_LEADER scope)
7. Structure CRUD (subunits + squads + RBAC + cascade)
8. Structure CASCADE rename test
"""
import os
import time
import uuid
import asyncio
import pytest
import requests

# Load REACT_APP_BACKEND_URL from frontend/.env if not set
if not os.environ.get("REACT_APP_BACKEND_URL"):
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.strip().startswith("REACT_APP_BACKEND_URL="):
                    os.environ["REACT_APP_BACKEND_URL"] = ln.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

KV1_PLATOON = "1 Взвод радіорозвідки"
KV2_PLATOON = "2 Взвод радіорозвідки"


def _login(username: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin", "rota2026")


@pytest.fixture(scope="module")
def kv1_token():
    return _login("kv1", "platoon1")


@pytest.fixture(scope="module")
def material_token():
    return _login("material", "venom2026")


@pytest.fixture(scope="module")
def viewer_token():
    return _login("viewer", "view2026")


# ============ 1. REFACTOR REGRESSION ============
class TestRefactorRegression:
    def test_soldiers_get(self, admin_token):
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) > 0

    def test_transfers_get(self, admin_token):
        r = requests.get(f"{API}/transfers", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200

    def test_warehouse_get(self, admin_token):
        r = requests.get(f"{API}/warehouse/items", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200

    def test_backup_list(self, admin_token):
        r = requests.get(f"{API}/admin/backup/list", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200

    def test_structure_get(self, admin_token):
        r = requests.get(f"{API}/structure", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "subunits" in d and "order" in d


# ============ 2. PLATOON_LEADER SCOPE (kv1) ============
class TestPlatoonLeaderScope:
    def test_list_only_own_platoon(self, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(kv1_token), timeout=10)
        assert r.status_code == 200
        items = r.json()
        for s in items:
            np = s.get("node_path", "")
            assert np.startswith(KV1_PLATOON), f"kv1 sees foreign soldier: {np}"

    def test_get_foreign_soldier_403(self, admin_token, kv1_token):
        # find a soldier outside kv1 platoon
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=10)
        all_s = r.json()
        foreign = next((s for s in all_s if not s.get("node_path", "").startswith(KV1_PLATOON)), None)
        if not foreign:
            pytest.skip("no foreign soldier")
        r2 = requests.get(f"{API}/soldiers/{foreign['id']}", headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 403, f"expected 403, got {r2.status_code}"

    def test_create_foreign_node_403(self, kv1_token):
        payload = {
            "fio": "TEST_iter7_foreign",
            "node_path": KV2_PLATOON,
            "position": "тест",
        }
        r = requests.post(f"{API}/soldiers", json=payload, headers=_h(kv1_token), timeout=10)
        assert r.status_code == 403

    def test_put_change_node_to_foreign_403(self, admin_token, kv1_token):
        # Find one own soldier
        r = requests.get(f"{API}/soldiers", headers=_h(kv1_token), timeout=10)
        items = r.json()
        if not items:
            pytest.skip("kv1 has no soldiers")
        own = items[0]
        merged = {**own}
        merged.pop("id", None); merged.pop("documents", None)
        merged.pop("created_at", None); merged.pop("updated_at", None)
        merged["node_path"] = "Управління роти"
        r2 = requests.put(f"{API}/soldiers/{own['id']}", json=merged, headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 403

    def test_delete_403_for_platoon_leader(self, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(kv1_token), timeout=10)
        items = r.json()
        if not items:
            pytest.skip("no soldiers")
        r2 = requests.delete(f"{API}/soldiers/{items[0]['id']}", headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 403


# ============ 3. PLATOON_LEADER + TRANSFERS ============
class TestPlatoonLeaderTransfers:
    def test_kv1_can_transfer_own_to_company_node(self, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(kv1_token), timeout=10)
        items = r.json()
        if not items:
            pytest.skip("kv1 has no soldiers")
        own = items[0]
        payload = {
            "soldier_id": own["id"],
            "transfer_type": "in-rota",
            "to_node_path": "Група обробки інформації",
            "reason": "TEST_iter7_kv1_transfer",
        }
        r2 = requests.post(f"{API}/transfers", json=payload, headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 200, f"got {r2.status_code}: {r2.text}"
        tid = r2.json()["id"]
        # cleanup
        requests.delete(f"{API}/transfers/{tid}", headers=_h(kv1_token), timeout=10)

    def test_kv1_cannot_transfer_foreign(self, admin_token, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=10)
        all_s = r.json()
        foreign = next((s for s in all_s if not s.get("node_path", "").startswith(KV1_PLATOON)), None)
        if not foreign:
            pytest.skip("no foreign soldier")
        payload = {
            "soldier_id": foreign["id"],
            "transfer_type": "in-rota",
            "to_node_path": "Управління роти",
            "reason": "TEST_iter7_foreign",
        }
        r2 = requests.post(f"{API}/transfers", json=payload, headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 403

    def test_kv1_transfers_list_scoped(self, kv1_token):
        r = requests.get(f"{API}/transfers", headers=_h(kv1_token), timeout=10)
        assert r.status_code == 200
        # response may be list or {items}
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        # all entries should relate to kv1 platoon (either to or from)
        for t in items:
            fr = t.get("from_node_path", "") or ""
            to = t.get("to_node_path", "") or ""
            assert fr.startswith(KV1_PLATOON) or to.startswith(KV1_PLATOON), \
                f"transfer not scoped: from={fr} to={to}"


# ============ 4. AUDIT LOG ============
class TestAuditLog:
    def test_audit_get_admin_200(self, admin_token):
        r = requests.get(f"{API}/audit-log", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d
        assert isinstance(d["items"], list)

    def test_audit_categories(self, admin_token):
        r = requests.get(f"{API}/audit-log/categories", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "categories" in d
        assert "usernames" in d

    def test_audit_post_writes_entry(self, admin_token):
        # Trigger a POST that succeeds: e.g., create + delete a soldier
        # Use a temp soldier
        payload = {
            "fio": "TEST_iter7_audit",
            "node_path": "Управління роти",
            "position": "тест",
        }
        r = requests.post(f"{API}/soldiers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        sid = r.json()["id"]
        # Give middleware a moment
        time.sleep(0.7)
        try:
            r2 = requests.get(f"{API}/audit-log?category=soldiers&username=admin",
                              headers=_h(admin_token), timeout=10)
            assert r2.status_code == 200
            items = r2.json()["items"]
            # Find entry with method=POST and path contains /soldiers
            match = [i for i in items
                     if i.get("method") == "POST"
                     and "/soldiers" in i.get("path", "")
                     and i.get("username") == "admin"
                     and i.get("user_role") == "COMMANDER"]
            assert match, f"no audit entry found; items[0:3]={items[:3]}"
        finally:
            requests.delete(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)

    @pytest.mark.parametrize("user_token_fx", ["kv1_token", "material_token", "viewer_token"])
    def test_audit_get_non_commander_403(self, request, user_token_fx):
        tok = request.getfixturevalue(user_token_fx)
        r = requests.get(f"{API}/audit-log", headers=_h(tok), timeout=10)
        assert r.status_code == 403, f"{user_token_fx}: expected 403, got {r.status_code}"

    def test_audit_filters(self, admin_token):
        r = requests.get(f"{API}/audit-log?category=soldiers&username=admin&success=true",
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        for i in d["items"]:
            assert i.get("category") == "soldiers"
            assert i.get("username") == "admin"
            assert i.get("success") is True


# ============ 5. AUDIT TTL INDEX ============
class TestAuditTTL:
    def test_ttl_index_exists(self):
        import motor.motor_asyncio
        # Read from backend/.env if not in environment
        mongo_url = os.environ.get("MONGO_URL", "")
        db_name = os.environ.get("DB_NAME", "")
        if not mongo_url or not mongo_url.startswith("mongodb"):
            try:
                with open("/app/backend/.env") as f:
                    for ln in f:
                        ln = ln.strip()
                        if ln.startswith("MONGO_URL="):
                            mongo_url = ln.split("=", 1)[1].strip().strip('"').strip("'")
                        elif ln.startswith("DB_NAME="):
                            db_name = ln.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
        if not mongo_url.startswith("mongodb"):
            mongo_url = "mongodb://localhost:27017"
        if not db_name:
            db_name = "test_database"

        async def check():
            client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            idx = await db.audit_log.index_information()
            return idx
        idx = asyncio.get_event_loop().run_until_complete(check())
        ttl_found = False
        for name, info in idx.items():
            if info.get("expireAfterSeconds") == 90 * 24 * 3600:
                # confirm it's on created_at_ts
                keys = info.get("key", [])
                if any(k[0] == "created_at_ts" for k in keys):
                    ttl_found = True
                    break
        assert ttl_found, f"TTL 7776000s index on created_at_ts not found; indexes={idx}"


# ============ 6. PDF EXPORT ============
class TestPdfExport:
    def test_pdf_admin_200(self, admin_token):
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=10)
        sid = r.json()[0]["id"]
        r2 = requests.get(f"{API}/soldiers/{sid}/export.pdf", headers=_h(admin_token), timeout=20)
        assert r2.status_code == 200
        ct = r2.headers.get("content-type", "")
        assert "application/pdf" in ct, f"bad CT: {ct}"
        body = r2.content
        assert body.startswith(b"%PDF-"), f"not PDF: {body[:20]!r}"
        assert len(body) > 10_000, f"PDF too small: {len(body)}"

    def test_pdf_kv1_own_200(self, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(kv1_token), timeout=10)
        items = r.json()
        if not items:
            pytest.skip("kv1 has no soldiers")
        r2 = requests.get(f"{API}/soldiers/{items[0]['id']}/export.pdf",
                          headers=_h(kv1_token), timeout=20)
        assert r2.status_code == 200
        assert r2.content.startswith(b"%PDF-")

    def test_pdf_kv1_foreign_403(self, admin_token, kv1_token):
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=10)
        all_s = r.json()
        foreign = next((s for s in all_s if not s.get("node_path", "").startswith(KV1_PLATOON)), None)
        if not foreign:
            pytest.skip("no foreign soldier")
        r2 = requests.get(f"{API}/soldiers/{foreign['id']}/export.pdf",
                          headers=_h(kv1_token), timeout=10)
        assert r2.status_code == 403


# ============ 7. STRUCTURE CRUD ============
class TestStructureCRUD:
    TEST_SU_KEY = "test_iter7_su"
    TEST_SQ_KEY = "test_iter7_sq"

    def test_a_create_subunit_admin(self, admin_token):
        payload = {"key": self.TEST_SU_KEY, "name": "ТестПідрозділ7", "type": "other", "count": 3}
        r = requests.post(f"{API}/structure/subunits", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        # Verify in /structure
        r2 = requests.get(f"{API}/structure", headers=_h(admin_token), timeout=10)
        assert self.TEST_SU_KEY in r2.json()["order"]
        assert r2.json()["subunits"][self.TEST_SU_KEY]["name"] == "ТестПідрозділ7"

    def test_b_rbac_non_commander(self, kv1_token, material_token):
        payload = {"key": "x", "name": "x", "type": "other", "count": 0}
        for tok, label in [(kv1_token, "kv1"), (material_token, "material")]:
            r = requests.post(f"{API}/structure/subunits", json=payload, headers=_h(tok), timeout=10)
            assert r.status_code == 403, f"{label}: expected 403, got {r.status_code}"

    def test_c_create_squad(self, admin_token):
        payload = {"parent_key": self.TEST_SU_KEY, "key": self.TEST_SQ_KEY,
                   "name": "ТестВідділення7", "count": 2}
        r = requests.post(f"{API}/structure/squads", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text

    def test_d_rename_squad(self, admin_token):
        r = requests.put(f"{API}/structure/squads/{self.TEST_SU_KEY}/{self.TEST_SQ_KEY}",
                         json={"new_name": "ТестВідділення7Нове"},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 200

    def test_e_delete_squad(self, admin_token):
        r = requests.delete(f"{API}/structure/squads/{self.TEST_SU_KEY}/{self.TEST_SQ_KEY}",
                            headers=_h(admin_token), timeout=10)
        assert r.status_code == 200

    def test_f_rename_subunit_cascade(self, admin_token):
        # Create temporary soldier under ТестПідрозділ7
        payload = {
            "fio": f"TEST_iter7_cascade_{uuid.uuid4().hex[:6]}",
            "node_path": "ТестПідрозділ7",
            "position": "тест",
        }
        r = requests.post(f"{API}/soldiers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        try:
            # Rename subunit
            r2 = requests.put(f"{API}/structure/subunits/{self.TEST_SU_KEY}",
                              json={"new_name": "НовийПідрозділ7"},
                              headers=_h(admin_token), timeout=10)
            assert r2.status_code == 200, r2.text
            d = r2.json()
            assert d.get("updated") is True
            assert d.get("cascade_count", 0) >= 1, f"cascade_count={d.get('cascade_count')}"
            # Verify soldier node_path
            r3 = requests.get(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)
            assert r3.status_code == 200
            assert r3.json()["node_path"] == "НовийПідрозділ7"
        finally:
            requests.delete(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)

    def test_g_delete_subunit_force(self, admin_token):
        # cleanup: delete subunit (no dependencies after cascade soldier deleted)
        r = requests.delete(f"{API}/structure/subunits/{self.TEST_SU_KEY}",
                            headers=_h(admin_token), timeout=10)
        # Either succeeds (200) or 400 if leftover deps - try force=1
        if r.status_code == 400:
            r = requests.delete(f"{API}/structure/subunits/{self.TEST_SU_KEY}?force=1",
                                headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text

    def test_h_delete_with_deps_400(self, admin_token):
        # Recreate subunit + soldier to test 400
        key = "test_iter7_delwithdeps"
        requests.post(f"{API}/structure/subunits",
                      json={"key": key, "name": "ТестДеп7", "type": "other", "count": 0},
                      headers=_h(admin_token), timeout=10)
        sr = requests.post(f"{API}/soldiers",
                           json={"fio": "TEST_iter7_dep", "node_path": "ТестДеп7", "position": "тест"},
                           headers=_h(admin_token), timeout=10)
        sid = sr.json().get("id") if sr.status_code == 200 else None
        try:
            r = requests.delete(f"{API}/structure/subunits/{key}",
                                headers=_h(admin_token), timeout=10)
            assert r.status_code == 400, r.text
            # force=1
            r2 = requests.delete(f"{API}/structure/subunits/{key}?force=1",
                                 headers=_h(admin_token), timeout=10)
            assert r2.status_code == 200
        finally:
            if sid:
                requests.delete(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)
