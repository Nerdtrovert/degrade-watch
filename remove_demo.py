import re

with open("frontend/src/pages/Login.tsx", "r") as f:
    content = f.read()

# Remove the Demo Environment section
demo_block = """          <div className="mt-6 border-t border-slate-200 pt-6">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Demo Environment</h3>
            <div className="bg-slate-50 rounded p-3 text-xs text-slate-600 border border-slate-200 space-y-2 font-mono">
              <div className="flex justify-between"><span className="text-slate-500">Merchant:</span> <span>merchant_admin</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Support:</span> <span>support_user</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Approver:</span> <span>approver_user</span></div>
              <div className="pt-2 border-t border-slate-200 flex justify-between">
                <span className="text-slate-500">Password:</span> <span>password123</span>
              </div>
            </div>
          </div>"""

content = content.replace(demo_block, "")

with open("frontend/src/pages/Login.tsx", "w") as f:
    f.write(content)
