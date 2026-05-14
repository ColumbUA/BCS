"""Backend tests for Iteration 5:
  - location_status / location_place on soldiers
  - Transfers CRUD + execute (in-rota / in-bat / etc.)
  - BCHS export csv (BOM, кирилиця) / xlsx (валідний openxlsx)
  - Documents: status PUT (draft/signed/executed), inline preview
  - Templates render with save_to_card=1 → автоматичне збереження як generated/draft
  - Backup: list, run, download, delete + RBAC (commander_only)
"""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://bcs-roster-control.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(u, p):
    return requests.post(f"{API}/auth/login", json={"username": u, "password": p}, timeout=30)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    r = _login("admin", "rota2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = _login("viewer", "view2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def material_token():
    r = _login("material", "venom2026")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def test_soldier(admin_token):
    """Створюємо власного тестового солдата для transfers/documents — щоб не мутувати справжні картки."""
    payload = {
        "fio": "TEST_ІТЕРАЦІЯ5 Тестовий Солдатович",
        "callsign": "TESTI5",
        "node_path": "Рота КОЛУМБ / 1 Взвод радіорозвідки / 1 Відділення",
        "position": "Тестова посада",
        "rank": "солдат",
    }
    r = requests.post(f"{API}/soldiers", json=payload, headers=_h(admin_token), timeout=30)
    assert r.status_code in (200, 201), r.text
    sid = r.json()["id"]
    yield r.json()
    # cleanup
    requests.delete(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=30)


# ============ LOCATION ============

class TestLocation:
    def test_put_soldier_location_fields(self, admin_token, test_soldier):
        sid = test_soldier["id"]
        upd = dict(test_soldier)
        upd["location_status"] = "СЗЧ"
        upd["location_place"] = "м. Київ, вул. Тестова 1"
        r = requests.put(f"{API}/soldiers/{sid}", json=upd, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        # GET to verify persistence
        g = requests.get(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=30)
        assert g.status_code == 200
        d = g.json()
        assert d["location_status"] == "СЗЧ"
        assert d["location_place"] == "м. Київ, вул. Тестова 1"

    def test_all_location_statuses_accepted(self, admin_token, test_soldier):
        sid = test_soldier["id"]
        statuses = ["ППД", "РЗ", "РВ", "СЗЧ", "Відпустка", "Лікарня", "Відрядження", "ВЛК", "Інше"]
        for st in statuses:
            upd = dict(test_soldier)
            upd["location_status"] = st
            upd["location_place"] = f"місце {st}"
            r = requests.put(f"{API}/soldiers/{sid}", json=upd, headers=_h(admin_token), timeout=30)
            assert r.status_code == 200, f"{st}: {r.text}"


# ============ TRANSFERS ============

class TestTransfers:
    def test_create_in_rota_transfer(self, admin_token, test_soldier):
        sid = test_soldier["id"]
        payload = {
            "soldier_id": sid,
            "transfer_type": "in-rota",
            "to_node_path": "Рота КОЛУМБ / 2 Взвод радіорозвідки / 1 Відділення",
            "new_position": "Новий стрілець",
            "order_number": "№123/2026",
            "reason": "Реорганізація",
            "effective_date": "2026-01-15",
            "status": "draft",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["soldier_id"] == sid
        assert t["transfer_type"] == "in-rota"
        assert t["soldier_fio"] == test_soldier["fio"]
        assert t["created_by"] == "admin"
        # store for next test
        TestTransfers.in_rota_id = t["id"]

    def test_execute_in_rota_updates_card(self, admin_token, test_soldier):
        tid = TestTransfers.in_rota_id
        r = requests.post(f"{API}/transfers/{tid}/execute", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        # Перевірка картки: node_path і position змінились
        g = requests.get(f"{API}/soldiers/{test_soldier['id']}", headers=_h(admin_token), timeout=30)
        d = g.json()
        assert "2 Взвод" in d["node_path"]
        assert d["position"] == "Новий стрілець"
        # transfer.status = executed
        lst = requests.get(f"{API}/soldiers/{test_soldier['id']}/transfers", headers=_h(admin_token), timeout=30).json()
        the = next(x for x in lst if x["id"] == tid)
        assert the["status"] == "executed"

    def test_execute_twice_fails(self, admin_token):
        r = requests.post(f"{API}/transfers/{TestTransfers.in_rota_id}/execute", headers=_h(admin_token), timeout=30)
        assert r.status_code == 400

    def test_create_in_bat_adds_note(self, admin_token, test_soldier):
        sid = test_soldier["id"]
        payload = {
            "soldier_id": sid,
            "transfer_type": "in-bat",
            "to_node_path": "Інший батальйон",
            "order_number": "№999",
            "effective_date": "2026-01-20",
            "reason": "Переведення",
            "status": "approved",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        tid = r.json()["id"]
        ex = requests.post(f"{API}/transfers/{tid}/execute", headers=_h(admin_token), timeout=30)
        assert ex.status_code == 200
        # У картку додався запис у notes + location_status = "Інше"
        d = requests.get(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=30).json()
        assert "Інший батальйон" in (d.get("notes") or "")
        assert d.get("location_status") == "Інше"

    def test_list_soldier_transfers(self, admin_token, test_soldier):
        r = requests.get(f"{API}/soldiers/{test_soldier['id']}/transfers",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        lst = r.json()
        assert len(lst) >= 2
        # Усі належать цьому солдату
        assert all(t["soldier_id"] == test_soldier["id"] for t in lst)

    def test_viewer_cannot_create_transfer(self, viewer_token, test_soldier):
        r = requests.post(f"{API}/transfers", json={
            "soldier_id": test_soldier["id"],
            "transfer_type": "in-rota",
            "to_node_path": "X",
        }, headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403


# ============ BCHS EXPORT ============

class TestBchsExport:
    def test_csv_export_bom_and_columns(self, admin_token):
        r = requests.get(f"{API}/export/bchs.csv", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200
        # BOM присутній
        assert r.content.startswith(b"\xef\xbb\xbf"), "Missing UTF-8 BOM"
        text = r.content.decode("utf-8-sig")
        header = text.split("\n", 1)[0]
        assert "Стан" in header
        assert "Місце" in header
        assert "ПІБ" in header
        # content-type
        assert "text/csv" in r.headers.get("content-type", "").lower()

    def test_xlsx_export_valid_workbook(self, admin_token):
        r = requests.get(f"{API}/export/bchs.xlsx", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # Валідний xlsx — це zip з xl/worksheets
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert any(n.startswith("xl/worksheets/") for n in names)
        # Відкриваємо openpyxl та перевіряємо заголовок
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
        ws = wb.active
        row1 = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        assert "Стан" in row1
        assert "Місце" in row1


# ============ DOCUMENTS (status + inline) ============

class TestDocuments:
    @pytest.fixture(scope="class")
    def generated_doc(self, admin_token, test_soldier):
        """Generate a doc via render + save_to_card → returns doc_files meta."""
        # Беремо перший доступний шаблон
        tpls = requests.get(f"{API}/templates", headers=_h(admin_token), timeout=30).json()["templates"]
        tid = tpls[0]["id"]
        r = requests.get(f"{API}/templates/{tid}/render",
                         params={"soldier_id": test_soldier["id"], "save_to_card": 1},
                         headers=_h(admin_token), timeout=60)
        assert r.status_code == 200
        # Чекаємо що файл .docx
        assert r.content[:2] == b"PK"
        # Знаходимо у списку документів
        docs = requests.get(f"{API}/soldiers/{test_soldier['id']}/documents",
                            headers=_h(admin_token), timeout=30).json()
        gen = [d for d in docs if d.get("source") == "generated"]
        assert len(gen) >= 1
        return gen[0]

    def test_generated_doc_has_draft_status(self, generated_doc):
        assert generated_doc["status"] == "draft"
        assert generated_doc["source"] == "generated"
        assert generated_doc.get("template_id")

    def test_update_status_to_signed(self, admin_token, generated_doc):
        fid = generated_doc["id"]
        r = requests.put(f"{API}/documents/{fid}/status",
                         json={"status": "signed", "status_at": "2026-01-10", "doc_notes": "Підписав командир"},
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "signed"
        assert d["status_at"] == "2026-01-10"
        assert d["doc_notes"] == "Підписав командир"

    def test_invalid_status_rejected(self, admin_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc['id']}/status",
                         json={"status": "bogus"}, headers=_h(admin_token), timeout=30)
        assert r.status_code == 400

    def test_viewer_cannot_update_status(self, viewer_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc['id']}/status",
                         json={"status": "executed"}, headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_inline_download(self, admin_token, generated_doc):
        r = requests.get(f"{API}/documents/{generated_doc['id']}",
                         params={"inline": 1}, headers=_h(admin_token), timeout=30, allow_redirects=True)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert cd.lower().startswith("inline"), f"Expected inline, got: {cd}"

    def test_attachment_default(self, admin_token, generated_doc):
        r = requests.get(f"{API}/documents/{generated_doc['id']}",
                         headers=_h(admin_token), timeout=30, allow_redirects=True)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert cd.lower().startswith("attachment")


# ============ BACKUP ============

class TestBackup:
    def test_run_backup_creates_file(self, admin_token):
        r = requests.post(f"{API}/admin/backup/run", headers=_h(admin_token), timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"].startswith("backup-") and d["name"].endswith(".tar.gz")
        assert d["size"] > 100 * 1024, f"Backup too small ({d['size']} bytes) — must be >100KB"
        TestBackup.created_name = d["name"]

    def test_list_includes_backup(self, admin_token):
        r = requests.get(f"{API}/admin/backup/list", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        names = [b["name"] for b in r.json()["backups"]]
        assert TestBackup.created_name in names

    def test_download_backup(self, admin_token):
        r = requests.get(f"{API}/admin/backup/download/{TestBackup.created_name}",
                         headers=_h(admin_token), timeout=60, stream=True)
        assert r.status_code == 200
        # gzip magic
        first2 = r.raw.read(2)
        assert first2 == b"\x1f\x8b", "Not gzip file"

    def test_delete_backup(self, admin_token):
        r = requests.delete(f"{API}/admin/backup/{TestBackup.created_name}",
                            headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        # confirm removed
        lst = requests.get(f"{API}/admin/backup/list", headers=_h(admin_token), timeout=30).json()
        assert TestBackup.created_name not in [b["name"] for b in lst["backups"]]

    def test_viewer_cannot_run_backup(self, viewer_token):
        r = requests.post(f"{API}/admin/backup/run", headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_material_cannot_run_backup(self, material_token):
        r = requests.post(f"{API}/admin/backup/run", headers=_h(material_token), timeout=30)
        assert r.status_code == 403

    def test_viewer_cannot_list_backups(self, viewer_token):
        r = requests.get(f"{API}/admin/backup/list", headers=_h(viewer_token), timeout=30)
        assert r.status_code == 403

    def test_invalid_name_path_traversal(self, admin_token):
        r = requests.get(f"{API}/admin/backup/download/..%2Fetc%2Fpasswd",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code in (400, 404)
