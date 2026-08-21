# Claude-Specific Instructions

These are Claude-only rules. Read and follow the shared repository workflow in
[`AGENTS.md`](AGENTS.md) before starting work.

## Output format

Assume the human skims; optimize for fast understanding and decisions.

* Open with one plain-English sentence stating the outcome, answer, or most
  important finding.
* Follow with only what is needed to understand the result, in a tight outline
  or bullets when useful.
* Prioritize findings, implications, and required next actions over narration.
* End substantive responses with these sections, in this order:

  **Recommendation:** The single recommended next action or option, and why in
  one sentence. If none, write `None.`

  **Decisions needed from me:** A numbered list of only the decisions, actions,
  or information required from the human, each with enough context to respond
  immediately. If none, write `None.`

Answer simple factual questions in one sentence instead. Follow any different
output format the human requests.

## When human action blocks progress

Use the blocking alert only when work cannot safely continue without a human
decision, approval, credential, external action, or missing information.
Optional suggestions and non-blocking decisions go in **Decisions needed from
me**, never in the alert.

When blocked, complete any work that can safely proceed, distinguish completed
from blocked work, put the required decisions in the normal **Decisions needed
from me** section, do not present the task as complete, and end the response
with the alert below and nothing after it.

> ## ⚠️ HUMAN ACTION REQUIRED
>
> **Status:** BLOCKED
> **Why work cannot continue:** `<one-sentence explanation>`
> **How to resume:** `<the exact reply or action that will unblock the work>`
