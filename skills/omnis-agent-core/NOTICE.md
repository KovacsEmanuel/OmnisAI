# Omnis agent core — third-party notice

Selected material from usestrix/strix, Copyright 2025 OmniSecure Inc.,
Apache-2.0. The unmodified upstream LICENSE is retained here.
Source revision: `6b7ae2ebe4d47037a927aade23265ff4e4f27e84`.

Modified by Omnis: U02 only. The excerpts in references/ are inert provenance,
not instructions loaded by the composer. Base and Brain instructions are literal
adaptations; worker guidance is first-party. Replaced Strix tool names and runtime
assumptions with owner-admitted assignments and exact references. Removed active
hunting, authorization/refusal overrides, reporting/fix requirements, environment
assumptions and implicit tooling. No Jinja evaluation or global skill loader.
The ordered-dedupe loop is adapted to exact publication-bound references; missing
references fail closed instead of being skipped.

- `strix/agents/prompt.py`, lines [69, 70, 71, 72, 73, 74, 75]:
  full SHA256 `cff5877ade57b23ae9342fe546888a321b02aacc37909821a2a3f06414b98abc`;
  excerpt `references/ordered-dedupe.txt` SHA256 `1793faa533f343bc5da78b9c03498c81384d160ff7063bc9e251049ae8310b63`.

- `strix/agents/prompts/system_prompt.jinja`, lines [4, 5, 6, 7, 8, 9, 10, 27, 28, 29, 30]:
  full SHA256 `f5413d1ea78571cec610069020e49b7227f6c3691867c127ff383b6aa1b2ab17`;
  excerpt `references/system-selections.txt` SHA256 `552ada8fd1c312598b20e42e948752cbf8580a37026d220aa608cda22a091d08`.

- `strix/skills/coordination/root_agent.md`, lines [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 94, 95, 96, 97, 98, 99]:
  full SHA256 `fe5ba2d54a231e563ff925f1f0389238096cc688cef3715df2ab6769f79f26aa`;
  excerpt `references/root-selections.txt` SHA256 `f031900d997b76dda9960f3c05127a01ade4d0143d1820be2ed607f559e9b673`.
