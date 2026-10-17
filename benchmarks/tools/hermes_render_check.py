import sys, re
sys.path.insert(0, '/tmp/heads/hermes-agent')
from agent import prompt_builder as pb
lean = {"memory", "web_search", "get_current_time", "lookup_customer", "update_ticket"}   # a lean 5-tool profile like in #106506
blocks = {
  "execution_guidance (lean toolset)": pb.execution_guidance_text(lean),
  "google_operational_guidance": pb.GOOGLE_MODEL_OPERATIONAL_GUIDANCE,
  "execution_guidance (terminal only)": pb.execution_guidance_text({"terminal"}),
}
KNOWN = {"terminal","execute_code","read_file","search_files","write_file","patch","delegate_task","browser_navigate","web_extract"}
for name, text in blocks.items():
    tools = lean if 'lean' in name or 'google' in name else {"terminal"}
    hits = sorted({t for t in KNOWN if re.search(r'\b'+t+r'\b', text)} - tools)
    print(f"{name}: names tools absent from the session -> {hits}")
