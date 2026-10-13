import json
import sys

plan = json.load(sys.stdin)
print("## Terraform change summary\n")
print("Resource addresses and actions only; values and state are omitted.\n")
print("| Resource | Action |\n|---|---|")
for resource in plan.get("resource_changes", []):
    actions = resource["change"]["actions"]
    if actions != ["no-op"]:
        print(f"| `{resource['address']}` | {', '.join(actions)} |")
