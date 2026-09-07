# Self-drive over tmux — running your own `/commands`

_How an agent whose TUI is running inside a tmux pane issues slash commands to
itself, reads its own screen, and compacts without asking the user._
**Last updated:** 2026-09-07

---

## 0) Why this file exists

Everywhere else in this repo you are told that `/compact` and `/context` are the
**user's** commands: no tool exposes your context size and no tool clears it.
That is still true of the tool surface — but it stops being true of the
*session* when the TUI runs inside tmux, because a Bash tool call can then type
into the very pane that is running you.

So the rule is conditional, and the condition is checkable in one line. Check it
before you assume either half.

---

## 1) Detect it — never assume

Every Bash tool call is a child of the shell in the pane that runs the TUI, so
it inherits that pane's tmux variables:

```bash
[ -n "$TMUX" ] && echo "self-drive: yes — pane $TMUX_PANE on socket ${TMUX%%,*}" \
               || echo "self-drive: no — slash commands are the user's to run"
```

- `$TMUX` is `<socket-path>,<server-pid>,<session-id>`; `${TMUX%%,*}` is the
  socket path. Address the server with `-S "${TMUX%%,*}"`, **not** `-L wave` —
  the socket name is the user's choice and hardcoding it breaks silently.
- `$TMUX_PANE` (e.g. `%0`) is your own pane. Target that id, never a
  guessed-by-name `session:window` — another agent or a helper shell may share
  the server.
- Add `-u` to every invocation; the launch procedure forces UTF-8 for a reason.

If `$TMUX` is empty you are not self-drivable: fall back to the documented
behaviour of telling the user that now is a cheap moment to run `/compact`.

---

## 2) Send a command to yourself

**Two payloads, two mechanisms.** A short slash command or a bare key press
has no metacharacters and is safe as a `send-keys` literal. Prompt text is
arbitrary text and is not — it goes through a tmux buffer, never a shell
command line. Use each only for what it is good for.

### Slash commands and keys: `send-keys`

```bash
tmux -u -S "${TMUX%%,*}" send-keys -t "$TMUX_PANE" -l '/compact'
tmux -u -S "${TMUX%%,*}" send-keys -t "$TMUX_PANE" Enter
```

`-l` sends the text literally, so payloads containing tmux key names (`Space`,
`Enter`, `C-c`) cannot be reinterpreted as keystrokes. Send `Enter` as its own
call. This is correct for a short slash command with no metacharacters, and for
sending the bare `Enter` key — nothing beyond that.

**It is deferred, not immediate.** The keystrokes land in the TUI's input box.
While a turn is running the input queues and submits only when that turn ends.
Anything you do after the `send-keys` is still the old turn; the command has not
run yet, so end the turn right after queuing.

**A slash command alone stops the session.** A local slash command produces
`<local-command-stdout>`, but that output does **not** re-invoke the model: it is
buffered and control returns to the human, who must type something before you
run again. A bare self-issued `/compact` therefore parks the session exactly
where you meant it to keep going.

**And you cannot simply queue the prompt behind the command**, because the two
input kinds take different paths:

| You send | When it is delivered |
|:---|:---|
| a slash command | queued; fires **after** the current turn ends |
| plain text | injected **into the running turn**, immediately |

Send both in one turn and the prompt arrives first, then the command fires into
silence — the failure you were trying to avoid, with an extra step.

### Prompt text: `load-buffer` + `paste-buffer`

Detach a typist that pastes the prompt from a tmux buffer some seconds after
the turn ends. The prompt text never appears on a shell command line — only a
buffer name and a pane id do, and neither can contain a metacharacter:

```bash
S="${TMUX%%,*}"; P="$TMUX_PANE"
PROMPT=/tmp/restore-prompt.txt

# Heredoc delimiter QUOTED -> zero interpolation, zero escaping. Arbitrary markup is safe.
cat > "$PROMPT" <<'PROMPT_EOF'
Continue: read READ_AFTER_COMPACT.md first, before any source file, and resume
from its Next action. Do not start new work.
PROMPT_EOF

tmux -u -S "$S" load-buffer -b restore "$PROMPT"
setsid bash -c "sleep 5; \
  tmux -u -S '$S' paste-buffer -b restore -t '$P' -p -d; \
  tmux -u -S '$S' send-keys -t '$P' Enter" </dev/null >/dev/null 2>&1 &
disown
tmux -u -S "$S" send-keys -t "$P" -l '/clear'
tmux -u -S "$S" send-keys -t "$P" Enter
```

- `-p` = bracketed paste, so newlines in the prompt insert as text instead of
  submitting mid-paste.
- `-d` = delete the buffer after pasting, so a later paste cannot resurrect a
  stale prompt.
- `Enter` is a **separate** `send-keys` call — `paste-buffer` never submits,
  bracketed or not.
- The 5s delay is unchanged from the `send-keys` version and still correct for
  the same reason: input arriving while the session is busy is queued, not
  dropped.
- `setsid` + `</dev/null` + `disown` are what let the typist outlive the tool
  call.
- **Fire the typist as the last thing you do, then end the turn.** The delay is
  wall-clock from *send* time, not from turn end; if the turn runs longer than
  the delay the typist fires mid-turn and is wasted as an injected message.
- **~5s is enough, even for `/compact` or `/clear`.** The delay does not have
  to outlast the compaction: text that arrives while the session is busy is
  *queued*, not dropped, and lands as soon as the session is free. The only
  thing the delay must outlast is the remainder of *your own turn* after you
  detach the typist — and since the typist is the last thing you fire, that is
  a `load-buffer`, two `send-keys` calls, and a closing message. Too short is
  still the real hazard: a typist that fires before the turn ends is injected
  into the running turn and wasted, leaving the queued command to fire into
  silence.
- Write the prompt **self-contained**, as if a stranger sent it. After a
  `/compact` or `/clear` it and the ledger are the entire brief.

**Say what you queued** in your closing message. From the user's side an
unannounced self-issued `/compact` or `/clear` looks like the session lost its
mind.

You do **not** need `capture-pane` for a slash command's own output — it comes
back in the transcript.

### Why not send-keys for prompt text

Measured directly, in this sandbox, today:

- **`send-keys -l` drops bytes.** A 424-byte payload delivered 423 bytes via
  `send-keys -l` — it dropped the trailing newline. `paste-buffer` delivered
  all 424.
- **THE DECISIVE ONE.** A payload of two shell lines separated by `\n`, pasted
  into an interactive `bash --norc -i`: via `paste-buffer -p` both lines sat in
  the input buffer unexecuted, no marker files created — the embedded newline
  was inserted as text. Via `send-keys -l` the newline acted as Enter: line one
  *executed* (marker file created), line two landed on the next prompt as a
  separate command. For a TUI this means a multi-line prompt sent with
  `send-keys` is submitted at the first newline, and its remaining lines arrive
  as separate, unintended prompts.
- **The shell-quoting layer is an independent failure.** With a prompt
  containing one apostrophe, the nested form
  `setsid bash -c "... send-keys -l '$PROMPT' ..."` died with
  `bash: -c: line 1: unexpected EOF while looking for matching `'``; a second
  nesting variant silently corrupted `It's done` into `Its`/`done\` split
  across two lines. Silent corruption is the worse half of this — a crash at
  least tells you something broke.

`load-buffer` sidesteps all three: the prompt text is written to a file with a
quoted heredoc delimiter (zero interpolation, zero escaping), and the tmux
commands that follow carry only a buffer name and a pane id — neither can
contain a metacharacter, so there is no quoting layer left to fail.

---

## 3) Read your own screen

`capture-pane` is for what never enters the transcript: TUI chrome, a pending
permission prompt, rendering, spinner state.

```bash
S="${TMUX%%,*}"
tmux -u -S "$S" capture-pane -t "$TMUX_PANE" -p -J             # visible pane
tmux -u -S "$S" capture-pane -t "$TMUX_PANE" -p -J -S -200     # + 200 lines of scrollback
tmux -u -S "$S" capture-pane -t "$TMUX_PANE" -p -J -S -        # entire history
```

- `-J` joins wrapped lines. Without it a pane sized 80x24 (which is what a
  session created **detached** gets, regardless of the user's real terminal)
  hard-wraps every path mid-word.
- Redirect to a file in the scratchpad and `grep` it. A full pane dump pasted
  into your context is exactly the cost this repo's context rules exist to
  avoid.
- `capture-pane -S` reads the scrollback **without** moving the view. Prefer it
  to scrolling.

Scrolling is available when you genuinely need the TUI's own rendering of older
output — the transcript pager responds to `PageUp` / `PageDown`:

```bash
tmux -u -S "${TMUX%%,*}" send-keys -t "$TMUX_PANE" PageUp
```

If you scroll, scroll back down before ending the turn. A pane left scrolled up
is a confusing handoff to the human sitting in front of it.

---

## 4) Rules — this is a control loop pointed at yourself

1. **Only send what you would otherwise have asked the user to type**: slash
   commands, and prompt text. Nothing else.
2. **Never answer your own prompts.** Do not send `y`, `1`, `2`, `Enter` or
   `Escape` into a pending permission or confirmation dialog. That is granting
   yourself the permission the human was asked for, and it is the one use of
   this mechanism that is never acceptable — irrespective of how obvious the
   answer looks.
3. **Never send a kill.** No `C-c`, no `C-d`, no `/exit`, no `/quit`, no
   `kill-server` / `kill-session` / `kill-pane` against the socket in `$TMUX`.
   You are the process in that pane.
4. **Never `respawn-pane`, `send-keys` to a pane you did not verify is yours**,
   or resize the window. `list-panes -a -F '#{pane_id} #{pane_current_command}'`
   if you must look around.
5. **One slash command per turn, plus one detached typist** (§2), and nothing
   else. More than that interleaves in one input box and submits as garbled
   lines.
6. **Do not poll.** `send-keys` → `capture-pane` → `send-keys` on a loop is a
   full-context turn per iteration that buys nothing. The same rule as §8 of
   `AGENTS.md`, and this mechanism makes it easy to violate by accident.
7. **The scratch-session carve-out does not touch rules 1-6.** A worker may
   create and drive its own scratch tmux session on this socket —
   `new-session -d -s <scratch>`, `send-keys` / `capture-pane` / `paste-buffer`
   targeting only that scratch session, `kill-session` on it when done — but
   only when its brief explicitly grants that permission; it is never an
   always-on default, and a brief that wants it must say so. A worker may
   **never** target the manager's pane or the session the TUI runs in. Rules
   1-6 above still govern that pane absolutely, for the manager and for every
   worker: a stray `send-keys` into it is the failure this whole file exists to
   prevent.

---

## 5) The ones that matter: /compact and /clear

With self-drive available, step 9 of the delivery loop changes from *ask* to
*do* — but the preparation does not change at all, because both commands are
lossy and both are unannounced to your future self.

```
1. Commit the plan item and tick its checkbox.        (work is durable)
2. Update READ_AFTER_COMPACT.md.                       (the ledger is the only thing that survives)
3. Detach the typist (long delay), THEN queue /compact or /clear, say so, end the turn.
4. After it lands: read READ_AFTER_COMPACT.md first, before any source file.
```

Step 3 is two mechanisms, not one command. `/compact` or `/clear` on its own
hands control back to the human at the exact moment your context was cleared —
the most expensive place in the session to stall, because the next thing you do
is re-read everything. The typist is what carries the work across.

Never reverse 2 and 3. A `/compact` or `/clear` queued before the ledger is
written erases the state the ledger was supposed to carry, and you will not
notice: the session simply continues on a narrower goal than the user asked
for.

`/context` is the cheap companion — queue it when you actually need the number
(deciding whether a large recon digest is affordable), not as a habit. Its
output costs a turn.

### `/compact` vs `/clear`

`/clear` resets the context; unlike `/compact` it leaves **no summary**. The
ledger plus the pasted restore prompt are the only things that survive.

Therefore: the ledger must be **complete** before `/clear` is queued, and the
restore prompt must be **fully self-contained** — it cannot refer to "the task
above" or anything else in session history.

`/clear` is queued and fires at turn end exactly like `/compact`, so the
typist pattern (§2) is identical for both.

Choose `/clear` over `/compact` when the remaining work does not depend on
session history at all — a clean next milestone. Choose `/compact` when
continuity of reasoning still matters. `/clear` is the bigger saving and the
bigger risk; the ledger is what makes it safe.

---

## 6) What is verified, and what is not

Verified live on tmux 3.6, in a session driving itself:

- socket/pane addressing via `$TMUX` / `$TMUX_PANE`, `send-keys -l`,
  `capture-pane -p -J -S`, `list-panes -a -F`;
- input sent during a running turn queues and submits when that turn ends;
- a self-issued `/context` returns its output as `<local-command-stdout>`;
- **and that output does not start a turn.** The first attempt stalled the
  session: the numbers sat in the transcript, unread, until the human typed;
- **plain text sent to the pane is injected into the running turn**, not queued
  behind the slash command. The second attempt proved it by arriving early;
- **a `setsid` delayed typist does work** — third attempt, `/context` output
  landed first, then the typist's message started the next turn with no human
  in the loop;
- **`load-buffer` → `save-buffer` is byte-exact** — a 424-byte file with single
  quotes, double quotes, backticks, `$(date)`, `${HOME}`, shell metacharacters,
  a ```` ```bash ```` fence, backslashes, unicode and trailing spaces survived
  the round trip with `cmp` reporting no difference;
- **`paste-buffer` delivers the full payload; `send-keys -l` does not** — the
  same 424-byte file arrived whole via `paste-buffer`, but `send-keys -l`
  delivered only 423 bytes, dropping the trailing newline;
- **a multi-line payload behaves oppositely under the two mechanisms** — pasted
  via `paste-buffer -p` into an interactive `bash --norc -i`, both lines sat in
  the input buffer unexecuted; sent via `send-keys -l`, the embedded newline
  submitted line one and stranded line two on the next prompt;
- **`paste-buffer -p`'s bracketed-paste wrapper is conditional on the
  receiving application** — it appears against interactive bash and the Claude
  Code TUI (both enable DECSET 2004) and does not against a bare `cat`; always
  pass `-p`.

Every rule in §2 was learned by breaking it. If a session shows something else
again — a command that vanishes, one that fires mid-turn, a typist that never
arrives — stop self-driving, say so, and fix this file.

---

## 7) How the session gets launched

Self-drive is a property of how the session was started, not something the agent
can turn on. The host procedure, condensed from the one that produced it:

```bash
# 1. on the host: start the sandbox, then find the container it created
sbx run claude
sbx ls                                  # read CONTAINER_NAME out of this

# 2. enter the ALREADY-RUNNING container — `exec`, not `run`
sbx exec -it "$CONTAINER_NAME" bash

# 3. once per container: a UTF-8 locale, or the TUI's box drawing turns to mojibake
sudo apt-get update && sudo apt-get install -y locales
sudo locale-gen en_US.UTF-8 && sudo update-locale LANG=en_US.UTF-8
echo 'export LANG=en_US.UTF-8'   >> ~/.bashrc
echo 'export LC_ALL=en_US.UTF-8' >> ~/.bashrc

# 4. a named socket keeps this server clear of any other tmux on the box
tmux -u -L wave new-session -d -s ctrl -n main
tmux -u -L wave attach -t ctrl          # attach *before* running claude
claude                                  # inside the pane
```

Three things about that sequence are load-bearing for the agent:

- **Step 2 is `sbx exec`, not `sbx run`.** `sbx run` starts a *new* sandbox;
  the container is already up from step 1, and entering it is `exec`. Using
  `run` there gets you a second, empty sandbox with none of this session's
  state, and the tmux server you then create is not the one the agent is in.
- **Attach before starting the TUI.** A pane created detached is 80x24 and the
  TUI renders to that size; attaching afterwards does not re-render what has
  already scrolled past.
- **`-L wave` is the *user's* socket name.** Do not hardcode it. The socket path
  is in `$TMUX`, which is what §1 tells you to read.

From a second shell on the same box the human can drive the pane the same way
the agent does — `send-keys` a command, `capture-pane -p` the result. That is
the escape hatch if a self-driven session ever wedges: it needs no cooperation
from the agent.
