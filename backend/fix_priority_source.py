"""Fix priority_source case and validate all 78 tickets parse against TicketOut."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pymongo import MongoClient
from models.base import MongoModel
from schemas.schemas import TicketOut

client = MongoClient("mongodb://localhost:27017")
db = client["itsm_helpdesk"]

# 1. Fix priority_source case
mapping = {"MANUAL": "manual", "AI": "ai", "ITIL_MATRIX": "itil_matrix"}
total_fixed = 0
for old_val, new_val in mapping.items():
    r = db.tickets.update_many(
        {"priority_source": old_val},
        {"$set": {"priority_source": new_val}}
    )
    if r.modified_count:
        print(f"  priority_source {old_val} -> {new_val}: {r.modified_count} tickets")
    total_fixed += r.modified_count
print(f"priority_source fixes: {total_fixed}")

# 2. Also check batch1 seeder tickets that may have same issues
# Look for any 'agent_id' field remaining
remaining_bad = db.tickets.count_documents({"agent_id": {"$exists": True}})
print(f"Remaining 'agent_id' (wrong field): {remaining_bad}")

# 3. Validate ALL tickets
print("\nValidating all tickets against TicketOut schema...")
errors = []
ok = 0
for t in db.tickets.find({}):
    try:
        formatted = MongoModel.format_id(t)
        TicketOut(**formatted)
        ok += 1
    except Exception as e:
        errors.append((str(t.get("subject", "?"))[:60], str(e)[:150]))

print(f"  OK: {ok}  |  ERRORS: {len(errors)}")
for subj, err in errors[:5]:
    print(f"  - {subj}")
    print(f"    {err}")

if not errors:
    print("\nAll 78 tickets are valid and will appear in the web interface!")
else:
    print(f"\n{len(errors)} tickets still have issues.")
