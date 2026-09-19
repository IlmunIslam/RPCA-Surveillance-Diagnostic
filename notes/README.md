# notes/ — thinking, not record

This folder is the layer the research record does not have: reading notes, drafts,
planning, open questions. It is opened in Obsidian along with the rest of the repo
(the repo root is the vault; nothing is mirrored or exported).

**Nothing in here is authoritative.** If a note and one of the record documents
disagree, the record document is right and the note is stale.

## What belongs here

- Reading notes on Shen et al. 2022 and related work — your interpretation, questions,
  things to check. (Verbatim facts about the source paper go in `paper/SOURCE.md`.)
- Manuscript drafts, section by section, in your own voice.
- Reviewer-response planning: how each reviewer point will be answered, what
  evidence each answer needs.
- Open questions and half-formed ideas, before they are decided.

New material only. Do not copy sections of the record into here to annotate them —
link to them instead (`RESEARCH_LOG.md` §7.4, for example). A copy goes stale the day
the original changes, which is how the old `CLAUDE.md` and the recovered `S:` notes
went wrong.

## What belongs in the record instead

| It is… | It goes in |
|---|---|
| The current state and the next step | `START_HERE.md` |
| A decision, a measured result, a verification, a retraction | `RESEARCH_LOG.md` |
| What the manuscript will say and cite | `PAPER_NOTES.md` |
| How a component is built and verified | `IMPLEMENTATION_PLAN.md` |
| The research questions and design | `RESEARCH_PLAN.md` |
| Anything about the frozen baseline results | `ARCHIVE_BASELINE.md` |
| Operational lessons for long runs | `PHASE3_NOTES.md` |
| What the source paper says, verbatim with page refs | `paper/SOURCE.md` |

When a note turns into one of those — a question gets answered, a draft paragraph
becomes a claim the paper makes — the fact moves to the record and the note links
to where it went. The record is the one source of truth; this folder is where the
thinking happens before it gets there.

## Conventions

- Plain Markdown links (`[text](../RESEARCH_LOG.md)`), not `[[wikilinks]]`, so every
  note reads correctly on GitHub as well as in Obsidian.
- Attachments (pasted figures, PDF excerpts) in `notes/attachments/`.
- Committed like everything else; the drafts are part of the project's history.
