import sys, json
d = json.loads(sys.stdin.read())
plan = d[0]["Plan"]
print(plan["Node Type"], plan.get("Sort Method", "none"))