with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "r") as f:
    content = f.read()

bad = "{((incident.success_rate_evidence.statistical_significance.confidence_level * 100).toFixed(1)}%"
good = "{(incident.success_rate_evidence.statistical_significance.confidence_level * 100).toFixed(1)}%"

content = content.replace(bad, good)

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "w") as f:
    f.write(content)
