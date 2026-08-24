import re

with open("frontend/src/pages/merchant/MerchantIncidentDetail.tsx", "r") as f:
    content = f.read()

# Fix recovery status
content = content.replace(
    "{recovery.state || 'NOT_EXECUTED'}",
    "{recovery.state || (policy_decision?.decision === 'AUTO_APPROVED' || policy_decision?.decision === 'HUMAN_APPROVAL' ? 'PENDING_EXECUTION' : 'NOT_EXECUTED')}"
)

# And in the getDecisionBadge fallback:
content = content.replace(
    "{decision || 'PENDING'}",
    "{decision || 'NOT_APPLICABLE'}"
)

with open("frontend/src/pages/merchant/MerchantIncidentDetail.tsx", "w") as f:
    f.write(content)

with open("frontend/src/pages/support/SupportIncidentConsole.tsx", "r") as f:
    content = f.read()

content = content.replace(
    "{status || 'PENDING'}",
    "{status || 'NOT_APPLICABLE'}"
)

content = content.replace(
    "{status || 'NONE'}",
    "{status || 'NOT_EXECUTED'}"
)

with open("frontend/src/pages/support/SupportIncidentConsole.tsx", "w") as f:
    f.write(content)

