import re

with open("frontend/src/pages/support/SupportIncidentConsole.tsx", "r") as f:
    content = f.read()

# Filter active incidents
content = content.replace(
    "const [incidents, setIncidents] = useState<SupportIncident[]>([]);",
    "const [incidents, setIncidents] = useState<SupportIncident[]>([]);\n  const activeIncidents = incidents.filter(i => i.classification !== 'NORMAL');\n  const normalIncidents = incidents.filter(i => i.classification === 'NORMAL');"
)

# Update the header counts
content = content.replace(
    "{incidents.length} Records",
    "{activeIncidents.length} Records"
)

# Update the map
content = content.replace(
    "incidents.map((incident: SupportIncident)",
    "activeIncidents.map((incident: SupportIncident)"
)

# Update the empty state
content = content.replace(
    "incidents.length === 0",
    "activeIncidents.length === 0"
)

# Now duplicate the entire card for normalIncidents
card_regex = r'(<div className="card overflow-hidden">.*?</div>\n    </div>)'

def add_normal_table(match):
    original_card = match.group(1)
    # create normal card
    normal_card = original_card.replace("Active Incidents", "Rejected Degradations (Normal)")
    normal_card = normal_card.replace("activeIncidents.length", "normalIncidents.length")
    normal_card = normal_card.replace("activeIncidents.map", "normalIncidents.map")
    normal_card = normal_card.replace("No active incidents found", "No rejected degradations found")
    
    return original_card[:-13] + "\n\n      " + normal_card + "\n    </div>" # -13 removes the closing </div>\n    </div> to append

content = re.sub(card_regex, add_normal_table, content, flags=re.DOTALL)

with open("frontend/src/pages/support/SupportIncidentConsole.tsx", "w") as f:
    f.write(content)

