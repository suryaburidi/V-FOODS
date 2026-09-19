from app import app, init_db
import tempfile, os

# Uses the app's current DB. This is a simple endpoint smoke test.
init_db()
c = app.test_client()
with c.session_transaction() as s:
    s["admin"] = True
r = c.post("/api/admin/menu", json={
    "name":"__TEST_ADMIN_SAVE__",
    "price":50,
    "category":"meals",
    "stock":20,
    "description":"Test item",
    "available":True
})
print("STATUS:", r.status_code)
print("RESPONSE:", r.get_json())
if r.status_code == 200 and r.get_json().get("id"):
    item_id=r.get_json()["id"]
    c.delete(f"/api/admin/menu/{item_id}")
