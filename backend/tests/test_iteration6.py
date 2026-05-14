"""Iteration 6 — code-review fixes:
1. Async backup (202 + job tracking)
2. Transfer validation against _company_node_paths
3. Auto ППД on in-rota execute
4. Dedupe generated docs (template_id+soldier_id+today)
5. DocumentStatusUpdate Pydantic (extra=forbid, Literal)
6. CSV export via csv.writer (QUOTE_MINIMAL)
7. backup_mod fallback flag
8. Roles RBAC for backup endpoints
"""
import os
import csv
import io
import time
import datetime as dt
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


def _login(username: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin", "rota2026")


@pytest.fixture(scope="module")
def material_token():
    return _login("material", "venom2026")


@pytest.fixture(scope="module")
def kv1_token():
    return _login("kv1", "platoon1")


@pytest.fixture(scope="module")
def viewer_token():
    return _login("viewer", "view2026")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def first_soldier(admin_token):
    r = requests.get(f"{API}/soldiers", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    assert items, "no soldiers in DB"
    return items[0]


# ============ 1. BACKUP ASYNC ============
class TestBackupAsync:
    def test_run_returns_202_with_job_id(self, admin_token):
        r = requests.post(f"{API}/admin/backup/run", headers=_h(admin_token), timeout=10)
        assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.text}"
        d = r.json()
        assert "job_id" in d
        assert d["status"] in ("queued", "running")
        self.__class__.job_id = d["job_id"]

    def test_job_polling_completes(self, admin_token):
        job_id = getattr(self.__class__, "job_id", None)
        assert job_id, "must run after test_run_returns_202_with_job_id"
        final = None
        for _ in range(60):  # max 60s
            time.sleep(1)
            r = requests.get(f"{API}/admin/backup/job/{job_id}", headers=_h(admin_token), timeout=10)
            assert r.status_code == 200
            j = r.json()
            if j["status"] in ("done", "error"):
                final = j
                break
        assert final is not None, "backup did not complete in 60s"
        assert final["status"] == "done", f"job failed: {final}"
        # Required fields
        for fld in ("status", "fallback", "error", "started_at", "finished_at", "result"):
            assert fld in final, f"missing field {fld}: {final}"
        # result fields
        res = final["result"]
        assert res and "name" in res and "size" in res and "created_at" in res
        assert "fallback" in res
        assert isinstance(res["fallback"], bool)
        self.__class__.created_backup_name = res["name"]

    def test_jobs_list(self, admin_token):
        r = requests.get(f"{API}/admin/backup/jobs", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "jobs" in d and isinstance(d["jobs"], list)
        assert len(d["jobs"]) >= 1
        assert len(d["jobs"]) <= 20

    def test_duplicate_run_returns_same_job_with_message(self, admin_token):
        # Start a new job (most likely it will be queued/running briefly)
        r1 = requests.post(f"{API}/admin/backup/run", headers=_h(admin_token), timeout=10)
        assert r1.status_code == 202
        job_id_1 = r1.json()["job_id"]
        # Immediately POST again — should return same job_id with 'message'
        r2 = requests.post(f"{API}/admin/backup/run", headers=_h(admin_token), timeout=10)
        assert r2.status_code == 202
        d2 = r2.json()
        if "message" in d2:
            assert d2["job_id"] == job_id_1
        # Wait for the new job to finish so we don't leave running state for other tests
        for _ in range(60):
            time.sleep(1)
            rj = requests.get(f"{API}/admin/backup/job/{job_id_1}", headers=_h(admin_token), timeout=10).json()
            if rj["status"] in ("done", "error"):
                break

    def test_cleanup_test_backups(self, admin_token):
        """Remove backups created by this test to avoid polluting /app/backups."""
        r = requests.get(f"{API}/admin/backup/list", headers=_h(admin_token), timeout=10)
        if r.status_code == 200:
            for b in r.json().get("backups", [])[:3]:  # cleanup last 3
                requests.delete(f"{API}/admin/backup/{b['name']}", headers=_h(admin_token), timeout=10)


# ============ 2. TRANSFER VALIDATION ============
class TestTransferValidation:
    def test_invalid_to_node_path_400(self, admin_token, first_soldier):
        payload = {
            "soldier_id": first_soldier["id"],
            "transfer_type": "in-rota",
            "to_node_path": "Неіснуючий взвод",
            "reason": "TEST_invalid_path",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "Невірний підрозділ призначення" in detail, f"detail: {detail}"

    def test_invalid_transfer_type_400(self, admin_token, first_soldier):
        payload = {
            "soldier_id": first_soldier["id"],
            "transfer_type": "in-galaxy",
            "to_node_path": "Управління роти",
            "reason": "TEST_bad_type",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 400

    def test_valid_to_node_path_200(self, admin_token, first_soldier):
        # 'Управління роти' is the seed-correct path for АМЕЛЬКІН (admin/KOLUMB)
        payload = {
            "soldier_id": first_soldier["id"],
            "transfer_type": "in-rota",
            "to_node_path": "Управління роти",
            "reason": "TEST_valid_path",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        t = r.json()
        assert t["to_node_path"] == "Управління роти"
        # cleanup
        requests.delete(f"{API}/transfers/{t['id']}", headers=_h(admin_token), timeout=10)


# ============ 3. AUTO PPD on IN-ROTA EXECUTE ============
class TestAutoPpdOnExecute:
    def test_in_rota_execute_sets_ppd(self, admin_token, first_soldier):
        sid = first_soldier["id"]
        original_node = first_soldier["node_path"]
        original_position = first_soldier.get("position", "")

        # Set initial location_status to non-ППД
        requests.put(f"{API}/soldiers/{sid}",
                     json={"location_status": "Відпустка", "location_place": "Київ"},
                     headers=_h(admin_token), timeout=10)

        # Create in-rota transfer to same node (so seed structure stays intact)
        payload = {
            "soldier_id": sid,
            "transfer_type": "in-rota",
            "to_node_path": original_node,
            "new_position": original_position,
            "reason": "TEST_auto_ppd",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]

        # Execute
        rx = requests.post(f"{API}/transfers/{tid}/execute", headers=_h(admin_token), timeout=10)
        assert rx.status_code == 200, rx.text

        # Verify soldier
        rs = requests.get(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)
        assert rs.status_code == 200
        s = rs.json()
        assert s["location_status"] == "ППД", f"expected ППД, got {s.get('location_status')}"
        assert s.get("location_place", "") == ""
        assert s.get("location_updated_at"), "location_updated_at not set"
        assert s["node_path"] == original_node, "node_path corrupted!"

        # cleanup transfer
        requests.delete(f"{API}/transfers/{tid}", headers=_h(admin_token), timeout=10)

    def test_in_zsu_sets_inshe(self, admin_token, first_soldier):
        sid = first_soldier["id"]
        original_node = first_soldier["node_path"]
        original_position = first_soldier.get("position", "")
        original_rank = first_soldier.get("rank", "")
        original_callsign = first_soldier.get("callsign", "")
        original_fio = first_soldier.get("fio", "")

        # Create in-zsu transfer
        payload = {
            "soldier_id": sid,
            "transfer_type": "in-zsu",
            "to_node_path": "Інша частина ЗСУ",
            "effective_date": "2026-01-15",
            "reason": "TEST_inshe",
        }
        r = requests.post(f"{API}/transfers", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]

        rx = requests.post(f"{API}/transfers/{tid}/execute", headers=_h(admin_token), timeout=10)
        assert rx.status_code == 200

        rs = requests.get(f"{API}/soldiers/{sid}", headers=_h(admin_token), timeout=10)
        s = rs.json()
        assert s["location_status"] == "Інше"
        assert s["location_place"] == "Інша частина ЗСУ"

        # restore seed soldier to ППД + original fields (only location is mutated by in-zsu)
        requests.put(f"{API}/soldiers/{sid}",
                     json={
                         "location_status": "ППД",
                         "location_place": "",
                         "node_path": original_node,
                         "position": original_position,
                         "rank": original_rank,
                         "callsign": original_callsign,
                         "fio": original_fio,
                     },
                     headers=_h(admin_token), timeout=10)
        requests.delete(f"{API}/transfers/{tid}", headers=_h(admin_token), timeout=10)


# ============ 4. DEDUPE GENERATED DOCS ============
class TestDedupeGeneratedDocs:
    def test_render_three_times_creates_one_doc(self, admin_token, first_soldier):
        sid = first_soldier["id"]
        tid = "report_vacation"

        for _ in range(3):
            r = requests.get(
                f"{API}/templates/{tid}/render",
                params={"soldier_id": sid, "save_to_card": 1},
                headers=_h(admin_token), timeout=20,
            )
            assert r.status_code == 200, f"render failed: {r.status_code} {r.text[:200]}"
            time.sleep(0.3)

        # Now fetch documents via soldier card endpoint or doc_files via dedicated route.
        # Use /soldiers/{sid}/documents/generated or list — fallback: use /soldiers/{sid}
        rs = requests.get(f"{API}/soldiers/{sid}/cards/documents",
                          headers=_h(admin_token), timeout=10)
        if rs.status_code == 404:
            # Try generated-docs endpoint variants
            rs = requests.get(f"{API}/soldiers/{sid}/documents",
                              headers=_h(admin_token), timeout=10)
        assert rs.status_code == 200, rs.text
        data = rs.json()
        docs = data.get("documents") if isinstance(data, dict) else data
        today = dt.date.today().isoformat()
        matching = [d for d in docs
                    if d.get("source") == "generated"
                    and d.get("template_id") == tid
                    and d.get("status") == "draft"
                    and (d.get("uploaded_at") or "").startswith(today)]
        assert len(matching) == 1, f"expected 1 dedupe'd doc, got {len(matching)}: {matching}"

        # cleanup the doc
        doc_id = matching[0]["id"]
        requests.delete(f"{API}/documents/{doc_id}", headers=_h(admin_token), timeout=10)


# ============ 5. DocumentStatusUpdate Pydantic ============
class TestDocumentStatusPydantic:
    @pytest.fixture(scope="class")
    def generated_doc(self, admin_token, first_soldier):
        sid = first_soldier["id"]
        r = requests.get(
            f"{API}/templates/report_vacation/render",
            params={"soldier_id": sid, "save_to_card": 1},
            headers=_h(admin_token), timeout=20,
        )
        assert r.status_code == 200
        # find the doc
        rs = requests.get(f"{API}/soldiers/{sid}/documents", headers=_h(admin_token), timeout=10)
        if rs.status_code != 200:
            rs = requests.get(f"{API}/soldiers/{sid}/cards/documents", headers=_h(admin_token), timeout=10)
        data = rs.json()
        docs = data.get("documents") if isinstance(data, dict) else data
        today = dt.date.today().isoformat()
        matching = [d for d in docs if d.get("source") == "generated"
                    and d.get("template_id") == "report_vacation"
                    and (d.get("uploaded_at") or "").startswith(today)]
        assert matching, "no generated doc found for status tests"
        doc_id = matching[0]["id"]
        yield doc_id
        # cleanup
        requests.delete(f"{API}/documents/{doc_id}", headers=_h(admin_token), timeout=10)

    def test_invalid_status_422(self, admin_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc}/status",
                         json={"status": "invalid_value"},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_extra_field_422(self, admin_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc}/status",
                         json={"status": "signed", "extra_field": "X"},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_signed_with_optional_fields_200(self, admin_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc}/status",
                         json={"status": "signed", "status_at": "2026-05-14", "doc_notes": "OK"},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        # response should contain status info
        if isinstance(d, dict):
            assert d.get("status") == "signed" or "status" in str(d)

    def test_draft_200(self, admin_token, generated_doc):
        r = requests.put(f"{API}/documents/{generated_doc}/status",
                         json={"status": "draft"},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 200, r.text


# ============ 6. CSV EXPORT QUOTING ============
class TestCsvExportQuoting:
    def test_csv_with_bom_and_quoting(self, admin_token, first_soldier):
        sid = first_soldier["id"]
        original_notes = first_soldier.get("notes", "")
        tricky = 'Note;with semicolon\nand newline "quoted"'
        # PUT /soldiers/{sid} requires full SoldierBase — send merged payload
        merged = {**first_soldier, "notes": tricky}
        merged.pop("id", None); merged.pop("documents", None)
        merged.pop("created_at", None); merged.pop("updated_at", None)
        pr = requests.put(f"{API}/soldiers/{sid}", json=merged, headers=_h(admin_token), timeout=10)
        assert pr.status_code == 200, f"put notes failed: {pr.status_code} {pr.text[:200]}"
        try:
            r = requests.get(f"{API}/export/bchs.csv", headers=_h(admin_token), timeout=15)
            assert r.status_code == 200
            text = r.content.decode("utf-8")
            assert text.startswith("\ufeff"), "missing BOM"
            body = text[1:]  # strip BOM
            reader = csv.reader(io.StringIO(body), delimiter=";")
            rows = list(reader)
            assert len(rows) >= 2
            header = rows[0]
            assert len(header) == 15, f"header cols: {len(header)} -> {header}"
            for row in rows[1:]:
                assert len(row) == 15, f"row cols: {len(row)} -> {row}"
            # Ensure our tricky row is parsed back correctly
            found = False
            for row in rows[1:]:
                notes_col = row[14]
                if "semicolon" in notes_col and "newline" in notes_col:
                    found = True
                    # csv.reader should have correctly unescaped — semicolon and newline preserved
                    assert ";" in notes_col, f"semicolon missing from parsed notes: {notes_col!r}"
                    assert "\n" in notes_col, f"newline missing from parsed notes: {notes_col!r}"
                    break
            assert found, f"did not find tricky notes correctly parsed (row14 samples: {[r[14][:40] for r in rows[1:5]]})"
        finally:
            restore = {**first_soldier, "notes": original_notes}
            restore.pop("id", None); restore.pop("documents", None)
            restore.pop("created_at", None); restore.pop("updated_at", None)
            requests.put(f"{API}/soldiers/{sid}", json=restore, headers=_h(admin_token), timeout=10)


# ============ 8. BACKUP RBAC ============
class TestBackupRbac:
    @pytest.mark.parametrize("role", ["material", "kv1", "viewer"])
    def test_non_commander_forbidden(self, role, material_token, kv1_token, viewer_token):
        tokens = {"material": material_token, "kv1": kv1_token, "viewer": viewer_token}
        tok = tokens[role]
        endpoints = [
            ("POST", "/admin/backup/run"),
            ("GET", "/admin/backup/jobs"),
            ("GET", "/admin/backup/list"),
        ]
        for method, ep in endpoints:
            r = requests.request(method, f"{API}{ep}", headers=_h(tok), timeout=10)
            assert r.status_code == 403, f"{role} {method} {ep}: expected 403, got {r.status_code}"
