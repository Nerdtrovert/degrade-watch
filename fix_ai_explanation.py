import re

with open("frontend/src/pages/merchant/MerchantIncidentDetail.tsx", "r") as f:
    content = f.read()

# Replace Explanation block
old_explanation_block = """<div>
                    <span className="font-semibold text-slate-900">Explanation:</span> {llm_report.incident_summary?.what_happened || "No detailed explanation available."}
                  </div>"""

new_explanation_block = """{llm_report.incident_summary?.what_happened ? (
                    <div>
                      <span className="font-semibold text-slate-900 block mb-1">Detailed Explanation:</span>
                      <p className="text-slate-600">{llm_report.incident_summary.what_happened}</p>
                    </div>
                  ) : null}"""

content = content.replace(old_explanation_block, new_explanation_block)

with open("frontend/src/pages/merchant/MerchantIncidentDetail.tsx", "w") as f:
    f.write(content)
