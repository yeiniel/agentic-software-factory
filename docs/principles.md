# Principles

1. **Nothing to go down with.** No piece is a black box we depend on: if its
   provider disappeared, we could run the same thing ourselves or elsewhere.
   Every dependency has a stated exit path.
2. **Keep it simple.** Every piece earns its place; deleting comes first.
3. **Learn by small experiments.** Each experiment answers one question. It is
   judged by what actually happened, not by what anyone claims, and recorded
   honestly, failures included.
4. **What must always happen is a tool.** A step that must happen every time is
   built into a tool that does it and fails loudly when it can't; instructions
   are left for judgment. A rule kept only in wording will be broken: every one
   so far has been, at least once.
