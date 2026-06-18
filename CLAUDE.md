# misfireAI — agent notes

## Command Center convention

You are a managed agent in the operator's Command Center. Your registry name is
**`misfireAI`**. Follow these two rules.

### When you are blocked

If you reach a decision **above your caution threshold** (see below), do not
guess. Instead:

1. Copy the template at
   `/home/global_hp/command-center/templates/inbox-item.md` to a new file named
   `misfireAI--<short-slug>.md` in `/home/global_hp/command-center/inbox/`.
2. Fill in the frontmatter (`agent: misfireAI`, `created` = now in ISO8601,
   `status: open`, `needs` = one line) and the sections (what you need, why
   you're blocked, the options). Leave `## Your answer` empty.
3. **Stop.** Wait for the operator instead of proceeding on a guess.

### On startup

Check `/home/global_hp/command-center/inbox/` for any file matching
`misfireAI--*.md` that has a filled-in `## Your answer`. If you find one: act on
the answer, then move that file into
`/home/global_hp/command-center/inbox/done/`.

### Heartbeat — let the dashboard see you working

When you start working on something, overwrite (don't append) the single file
`/home/global_hp/command-center/heartbeats/misfireAI.txt` with the current time
and a short verb describing what you're doing:

```
2026-06-15T10:42:00 researching
```

The verb is one coarse word (`researching`, `writing`, `reviewing`,
`debugging`, …). Update it whenever your activity meaningfully changes. You
don't need to be precise or frequent — refreshing it as you work is enough. If
you go quiet, the dashboard shows you as "standing by" automatically.

### Your caution threshold

Use your **existing approval behavior** — the same Claude Code permission
defaults you already operate under. Do not adopt a new, stricter standard. The
inbox is for decisions you would already have paused on; it just gives those
pauses a durable home that survives the window closing.
