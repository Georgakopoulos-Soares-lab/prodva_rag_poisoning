# Plain-language glossary for this project

Every term explained in ordinary words, tied to what we are actually doing here.

---

## First, what ProDVa actually does

Someone types a request in English:
*"I want a protein that binds zinc and stays stable when heated."*

1. The system searches a **library of 712,248 known proteins**, each stored with
   an English description of what it does.
2. It picks the **16 descriptions closest in meaning** to the request.
3. From those 16 proteins it collects their useful **parts** — chunks of
   sequence known to do something, like a zinc-gripping chunk. Typically about
   **42 parts** in total.
4. It then writes a brand-new protein one letter at a time — but at each step it
   may instead **paste in one of those 42 ready-made parts**.

Our attack: sneak fake entries into that library of 712,248, so our parts get
pasted into what people design.

---

## The terms

**Library / corpus / supporting documents** — the 712,248 entries. Three names,
one thing.

**Embedding, or "vector"** — to compare English by *meaning* rather than exact
words, each description is turned into a list of 768 numbers. Think of it as a
**position on a map**, where similar meanings sit near each other. The request
gets a position too, and the system grabs the 16 nearest entries.

**Index (FAISS)** — the map itself: all 712,248 positions in one 2.2 GB file.

**"Exact / flat" search** — it compares the request against every single entry,
no shortcuts. Slower, but **perfectly repeatable**: the same request always
returns the same 16. That repeatability is a gift to us (see *replay*).

**"Normalized" / "length exactly 1.0" / "angle"** — all positions are pushed
onto the surface of a ball, so every point is the same distance from the centre.
Only the *direction* matters.
Why it matters: a known trick is to make your entry "louder" — inflate its
numbers so it wins on every request. Pushing everything onto the ball **erases
loudness**. We checked the stored numbers: all exactly 1.0. So that trick is
impossible here, which is why we drop that attack arm.

**Fragments / "dynamic vocabulary"** — the ready-made parts. Called a vocabulary
because the model normally writes one letter at a time from a fixed alphabet;
these are bonus "words" it can paste whole. **Dynamic** because they change with
every request, coming from whatever was retrieved.

**"ids >= 50257"** — the fixed alphabet has 50,257 entries. Any number above
that is a pasted-in part. So just by reading numbers ProDVa already saves, we can
see exactly when it pasted a part instead of writing letters. **Free evidence,
no code changes.**

**Provenance / hooks / instrumentation** — provenance means *a record of where
each thing came from*. We had planned to insert logging code into ProDVa to
record which 16 were retrieved, which parts were offered, and which were used.
Those insertion points are "hooks".

**"Replay offline"** — instead of logging during the run, we redo the search
ourselves afterwards on our own machine. Because the search is exactly
repeatable, we get the identical answer, so everything can be reconstructed
after the fact.
Why it matters: a reviewer could object *"you edited their software, maybe
that's why it misbehaved."* Now we can say we edited nothing.

**Mechanism control / masking** — to prove the damage came *through* our pasted
parts and not something else, we rerun with the model forbidden from using our
parts. If the damage disappears, we have proven the cause. This is the one place
we do change code.

**Payload** — the harmless marker protein attached to our fake entry, so we can
see whether it got smuggled into the output. Deliberately inert (e.g. a
fluorescent marker), never anything harmful.

**Attack T vs Attack U** — **T** is *targeted*: we know the exact request in
advance and tailor a fake entry to it. **U** is *universal*: we do not know what
people will ask, so we plant a few entries that get picked for many different
requests. A **hub** is such an entry — one that keeps showing up no matter what
you ask.

**Seeds / pairing** — the model makes random choices while writing, so the same
request twice gives different proteins. A **seed** locks the randomness so a run
can be repeated. We use several seeds so a result is not a fluke. **Pairing**
means comparing a clean run with a poisoned run that started from the same
randomness, so a difference is the poison rather than luck.

**DEV / EVAL** — we split our target requests into a small practice set we may
tinker with, and a larger final set we touch exactly once. Stops us fooling
ourselves.

**"Budget", 0.007%** — how much we had to add. 50 fake entries out of 712,248 is
**1 in 14,244**. The smaller that number, the more alarming the finding.

**Stealth** — making a fake entry not look obviously fake: sensible wording, and
not offering a suspicious number of parts.

**Pre-registration / freeze** — writing down exactly what we will measure
*before* the final experiment, then locking it, so we cannot quietly pick
whichever result looks best afterwards.

---

## The scoring tools

These judge a designed protein. **None of them exist in the repo — we build them.**

- **ESMFold / pLDDT** — predicts the 3D shape and reports how confident it is.
  High confidence = looks like a real, foldable protein. Checks that the poison
  did not simply produce garbage.
- **ProTrek** — scores whether the protein actually matches the English request.
- **InterProScan** — reads a protein sequence and reports which known functional
  pieces it contains. **This is our main measurement**: did the payload's
  signature end up in the final design?
- **TOAR** — the plan's name for how often that happens.
- **Perplexity, repetitiveness, EvoLlama, diversity** — other quality scores from
  the paper. Useful context, but they test none of our claims, which is why they
  are proposed as optional.

---

## The one trap worth remembering

The library lives in `training.json`; the parts list lives in `phrases.json`.
**A poison must be added to both.** Add it only to the first and our entry gets
found but supplies zero parts — the attack does nothing, and nothing warns you.
That is now an automatic check.

See also [plan_revisions.md](plan_revisions.md) for what these findings change,
and [verified_facts.md](verified_facts.md) for the evidence behind each number.
