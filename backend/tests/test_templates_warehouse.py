"""Backend tests for new modules: settings, templates (.docx), warehouse (склад).

Iteration 4 — covers:
  - GET /api/templates  (25 шаблонів, 5 категорій)
  - GET /api/templates/{id}/render → application/vnd.openxmlformats-officedocument.wordprocessingml.document, >5KB
  - GET /api/templates/{id}/render?soldier_id=...  → ПІБ підставляється у документ
  - GET /api/templates без token → 401
  - GET / PUT /api/settings (commander_only on PUT)
  - Warehouse CRUD + txns (IN/OUT/WRITEOFF), баланс, недостатньо на залишку (400),
    summary, RBAC (VIEWER cannot create), DELETE only commander.
"""
import io
import os
import zipfile
import pytest
import requests
from docx import Document

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://bcs-roster-control.preview.emergentagent.com").rstrip('/')
API = f"{BASE_URL}/api"


def _login(username, password):
    return requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    r = _login("admin", "rota2026")
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


# ============== TEMPLATES ==============

class TestTemplates:
    def test_list_unauth_401(self):
        r = requests.get(f"{API}/templates", timeout=30)
        assert r.status_code in (401, 403)

    def test_list_25_templates_5_categories(self, admin_token):
        r = requests.get(f"{API}/templates", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        tpls = data["templates"]
        assert len(tpls) == 25, f"Expected 25 templates, got {len(tpls)}"
        cats = {}
        for t in tpls:
            cats.setdefault(t["category"], 0)
            cats[t["category"]] += 1
        assert cats.get("Рапорти") == 8, cats
        assert cats.get("Накази") == 3, cats
        assert cats.get("Акти") == 5, cats
        assert cats.get("Журнали") == 6, cats
        assert cats.get("Донесення") == 3, cats

    def test_render_docx_size_and_mime(self, admin_token):
        r = requests.get(f"{API}/templates/report_vacation/render", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "wordprocessingml.document" in ct, ct
        assert len(r.content) > 5000, f"docx too small: {len(r.content)} bytes"
        # validate it's a real docx (zip)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        assert "word/document.xml" in z.namelist()

    def test_render_with_soldier_inserts_fio(self, admin_token):
        # Get any soldier
        r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        soldiers = r.json()
        if not soldiers:
            pytest.skip("no soldiers seeded")
        s = soldiers[0]
        sid = s["id"]
        full_name = (s.get("fio") or s.get("full_name") or "").strip()
        if not full_name:
            pytest.skip("soldier has no fio")
        r2 = requests.get(f"{API}/templates/report_vacation/render",
                          params={"soldier_id": sid}, headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200, r2.text
        doc = Document(io.BytesIO(r2.content))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        # Last name should appear (most builders use surname or fio)
        last_name = full_name.split()[0]
        assert last_name in full_text or full_name in full_text, \
            f"soldier name '{full_name}' not found in rendered .docx"

    def test_render_unknown_template_404(self, admin_token):
        r = requests.get(f"{API}/templates/no_such_id/render", headers=_h(admin_token), timeout=30)
        assert r.status_code == 404


# ============== SETTINGS ==============

class TestSettings:
    def test_get_settings(self, admin_token):
        r = requests.get(f"{API}/settings", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "company_name" in d

    def test_put_settings_commander_ok(self, admin_token):
        payload = {"unit_full": "ТЕСТ в/ч А0000", "unit_short": "А0000",
                   "unit_chief": "ТЕСТ КОМАНДИР", "unit_chief_rank": "полковник",
                   "city": "ТЕСТ-МІСТО", "company_name": "Тестова рота",
                   "company_chief": "командиру роти"}
        r = requests.put(f"{API}/settings", json=payload, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        # Verify persistence
        r2 = requests.get(f"{API}/settings", headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        assert d["unit_short"] == "А0000"
        assert d["unit_chief"] == "ТЕСТ КОМАНДИР"

    def test_put_settings_viewer_403(self, viewer_token):
        r = requests.put(f"{API}/settings", json={"unit_short": "X"},
                         headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_put_settings_platoon_403(self, platoon_token):
        r = requests.put(f"{API}/settings", json={"unit_short": "X"},
                         headers=_h(platoon_token), timeout=30)
        assert r.status_code == 403


# ============== WAREHOUSE ==============

class TestWarehouse:
    @pytest.fixture(scope="class")
    def created_item(self, admin_token):
        payload = {"name": "TEST_бронежилет", "category": "Майно (речове)",
                   "unit": "шт", "serial": "TEST-BR-001", "min_balance": 5}
        r = requests.post(f"{API}/warehouse/items", json=payload,
                          headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        item = r.json()
        assert item["name"] == "TEST_бронежилет"
        assert item["min_balance"] == 5
        yield item
        # teardown — delete (cascades txns)
        requests.delete(f"{API}/warehouse/items/{item['id']}",
                        headers=_h(admin_token), timeout=30)

    def test_list_returns_balance_and_below_min(self, admin_token, created_item):
        r = requests.get(f"{API}/warehouse/items", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        items = r.json()
        ours = next((x for x in items if x["id"] == created_item["id"]), None)
        assert ours is not None
        assert ours["balance"] == 0
        # min_balance=5, balance=0 → below_min True
        assert ours["below_min"] is True

    def test_txn_in_increases_balance(self, admin_token, created_item):
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "IN", "qty": 10,
            "counterparty": "TEST_постачальник", "doc_ref": "TN-001"
        }, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["created_by"] == "admin"
        # GET list and verify balance
        r2 = requests.get(f"{API}/warehouse/items", headers=_h(admin_token), timeout=30)
        ours = next(x for x in r2.json() if x["id"] == created_item["id"])
        assert ours["balance"] == 10
        assert ours["below_min"] is False  # 10 >= 5

    def test_txn_out_more_than_balance_400(self, admin_token, created_item):
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "OUT", "qty": 9999,
            "counterparty": "TEST"
        }, headers=_h(admin_token), timeout=30)
        assert r.status_code == 400
        body = r.json()
        msg = body.get("detail") or body.get("message") or str(body)
        assert "Недостатньо" in msg or "залишку" in msg

    def test_txn_out_ok(self, admin_token, created_item):
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "OUT", "qty": 3,
            "counterparty": "TEST_отримувач"
        }, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        # balance now 10 - 3 = 7
        r2 = requests.get(f"{API}/warehouse/items", headers=_h(admin_token), timeout=30)
        ours = next(x for x in r2.json() if x["id"] == created_item["id"])
        assert ours["balance"] == 7

    def test_txn_writeoff(self, admin_token, created_item):
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "WRITEOFF", "qty": 2,
            "reason": "TEST_зношений"
        }, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{API}/warehouse/items", headers=_h(admin_token), timeout=30)
        ours = next(x for x in r2.json() if x["id"] == created_item["id"])
        assert ours["balance"] == 5  # 10 - 3 - 2

    def test_get_item_txns_journal(self, admin_token, created_item):
        r = requests.get(f"{API}/warehouse/items/{created_item['id']}/txns",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        txns = r.json()
        # We made 3 successful txns above
        assert len(txns) >= 3
        types = [t["type"] for t in txns]
        assert "IN" in types and "OUT" in types and "WRITEOFF" in types
        for t in txns:
            assert "created_by" in t
            assert "qty" in t

    def test_summary(self, admin_token, created_item):
        r = requests.get(f"{API}/warehouse/summary", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "total_items" in d and "total_qty" in d and "by_category" in d
        assert d["total_items"] >= 1
        assert "Майно (речове)" in d["by_category"]

    def test_create_item_platoon_leader_ok(self, platoon_token):
        r = requests.post(f"{API}/warehouse/items", json={
            "name": "TEST_платоон_item", "category": "Інше", "unit": "шт"
        }, headers=_h(platoon_token), timeout=30)
        assert r.status_code == 200, r.text
        # cleanup via admin
        admin_r = _login("admin", "rota2026")
        admin_tok = admin_r.json()["access_token"]
        requests.delete(f"{API}/warehouse/items/{r.json()['id']}",
                        headers=_h(admin_tok), timeout=30)

    def test_create_item_material_ok(self, material_token):
        r = requests.post(f"{API}/warehouse/items", json={
            "name": "TEST_material_item", "category": "Інше", "unit": "шт"
        }, headers=_h(material_token), timeout=30)
        assert r.status_code == 200, r.text
        admin_r = _login("admin", "rota2026")
        admin_tok = admin_r.json()["access_token"]
        requests.delete(f"{API}/warehouse/items/{r.json()['id']}",
                        headers=_h(admin_tok), timeout=30)

    def test_create_item_viewer_403(self, viewer_token):
        r = requests.post(f"{API}/warehouse/items", json={
            "name": "TEST_viewer", "category": "Інше"
        }, headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_create_txn_viewer_403(self, viewer_token, created_item):
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "IN", "qty": 1
        }, headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_delete_item_platoon_403(self, platoon_token, created_item):
        r = requests.delete(f"{API}/warehouse/items/{created_item['id']}",
                            headers=_h(platoon_token), timeout=30)
        assert r.status_code == 403

    def test_delete_txn_commander_ok(self, admin_token, created_item):
        # Create extra txn to delete
        r = requests.post(f"{API}/warehouse/txns", json={
            "item_id": created_item["id"], "type": "IN", "qty": 1
        }, headers=_h(admin_token), timeout=30)
        tid = r.json()["id"]
        rd = requests.delete(f"{API}/warehouse/txns/{tid}",
                             headers=_h(admin_token), timeout=30)
        assert rd.status_code == 200

    def test_delete_item_cascades_txns(self, admin_token):
        # Create fresh item with txn, then delete and verify txns gone
        r = requests.post(f"{API}/warehouse/items", json={
            "name": "TEST_cascade", "category": "Інше"
        }, headers=_h(admin_token), timeout=30)
        iid = r.json()["id"]
        requests.post(f"{API}/warehouse/txns", json={
            "item_id": iid, "type": "IN", "qty": 5
        }, headers=_h(admin_token), timeout=30)
        # delete
        rd = requests.delete(f"{API}/warehouse/items/{iid}",
                             headers=_h(admin_token), timeout=30)
        assert rd.status_code == 200
        # txns now empty for this item
        rt = requests.get(f"{API}/warehouse/items/{iid}/txns",
                          headers=_h(admin_token), timeout=30)
        assert rt.status_code == 200
        assert rt.json() == []
