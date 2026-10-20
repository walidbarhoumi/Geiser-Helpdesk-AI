"""
Fix field name mismatches in seeded tickets so they match TicketOut schema.

Problems found:
  - seeder used 'agent_id'   → schema expects 'assigned_agent_id'
  - seeder used 'sla_due_at' → schema expects 'sla_deadline'
  - seeder added extra fields not in schema (tags, team_id, comments, history,
    first_response_at, ai_*, resolved_at, closed_at)

This script renames the fields and removes extras in-place.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["itsm_helpdesk"]

# Step 1: For every ticket that has 'agent_id' (from seeder),
#         copy it to 'assigned_agent_id' and copy 'sla_due_at' to 'sla_deadline'.
#         Then remove all seeder-only fields.

bad_tickets = list(db.tickets.find({"agent_id": {"$exists": True}}))
print(f"Found {len(bad_tickets)} tickets with wrong field names. Fixing...")

fixed = 0
for t in bad_tickets:
    tid = t["_id"]

    set_ops = {}
    unset_ops = {}

    # Rename agent_id → assigned_agent_id
    if "agent_id" in t:
        set_ops["assigned_agent_id"] = t["agent_id"]
        unset_ops["agent_id"] = ""

    # Rename sla_due_at → sla_deadline
    if "sla_due_at" in t:
        set_ops["sla_deadline"] = t["sla_due_at"]
        unset_ops["sla_due_at"] = ""

    # Remove extra fields not in TicketOut schema
    for extra in ["team_id", "comments", "history", "first_response_at",
                  "ai_category", "ai_subcategory", "ai_priority",
                  "ai_confidence", "ai_summary", "resolved_at", "closed_at", "tags"]:
        if extra in t:
            unset_ops[extra] = ""

    # Build the update
    update = {}
    if set_ops:
        update["$set"] = set_ops
    if unset_ops:
        update["$unset"] = unset_ops

    if update:
        db.tickets.update_one({"_id": tid}, update)
        fixed += 1

print(f"Fixed {fixed} tickets.")

# Step 2: Verify — try to load one ticket via the schema
print("\nVerifying one fixed ticket against TicketOut schema...")
try:
    from models.base import MongoModel
    from schemas.schemas import TicketOut

    sample = db.tickets.find_one({"assigned_agent_id": {"$exists": True}})
    if sample:
        formatted = MongoModel.format_id(sample)
        parsed = TicketOut(**formatted)
        print(f"  OK: ticket '{parsed.subject[:60]}' parsed successfully")
    else:
        print("  No tickets with assigned_agent_id found?")
except Exception as e:
    print(f"  SCHEMA ERROR: {e}")

# Step 3: Final count
total = db.tickets.count_documents({})
bad_remaining = db.tickets.count_documents({"agent_id": {"$exists": True}})
print(f"\nTotal tickets: {total}")
print(f"Remaining tickets with wrong 'agent_id' field: {bad_remaining}")
print("\nDone!")
