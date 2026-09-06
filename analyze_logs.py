import json
import requests
from collections import Counter
import time

LOG_FILE = "var/log/cowrie/cowrie.json"

ip_events = Counter()   
commands = Counter()      

with open(LOG_FILE) as f:
    for line in f:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("eventid") == "cowrie.session.connect":
            ip_events[event.get("src_ip")] += 1

        if event.get("eventid") == "cowrie.command.input":
            cmd = event.get("input", "").strip()
            if cmd:
                commands[cmd] += 1

country_counts = Counter()
ip_list = list(ip_events.keys())

for i in range(0, len(ip_list), 100):
    batch = ip_list[i:i+100]
    payload = [{"query": ip} for ip in batch]
    resp = requests.post("http://ip-api.com/batch", json=payload)
    for entry in resp.json():
        if entry.get("status") == "success":
            country_counts[entry["country"]] += ip_events[entry["query"]]
    time.sleep(1.5)

summary = {
    "total_events": sum(ip_events.values()),
    "unique_ips": len(ip_events),
    "country_counts": dict(country_counts),
    "top_commands": commands.most_common(30),
}

with open("honeypot_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("Done! File saved in: honeypot_summary.json")
