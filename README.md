# ClaudeMaxing

A terminal dashboard for your Claude Code usage. It reads the session
transcripts Claude Code already writes to disk and reports per-day tokens,
equivalent API cost, model mix, and a period-over-period efficiency delta.

No account, no API key, no configuration. Point it at your machine and it works.

```
  Claude Code usage  ·  last 7 active days  ·  all entrypoints
  ──────────────────────────────────────────────────────────────────────────
  68.2M tokens   $84 equiv   131 prompts   730 msgs   726 tools   0 compactions

  DAY        COST           cost per day            MSGS   TOOLS  $/PROMPT     Δ
  Aug 09   $5.90  █████▉                              75      71     $0.42     -
  Aug 10     $14  ██████████████▎                    124     124     $0.65   +141%
  Aug 11   $3.25  ███▎                                55      62     $0.36    -77%
  Aug 12     $17  █████████████████▍                 120     130     $0.67   +433%
  Aug 13   $9.75  █████████▊                         107     114     $0.54    -44%
  Aug 14     $30  ██████████████████████████████     184     174     $0.96   +205%
  Aug 15*  $3.81  ███▊                                65      51     $0.35    -87%
  * today - partial day

  WHERE IT GOES        TOKENS         COST   SHARE
  cache write          4.9M          $31   36.7%  █████▊
  cache read          62.1M          $29   34.0%  █████▍
  output               1.0M          $24   28.4%  ████▌
  input                150K        $0.69    0.8%  ▏
  thinking is 54% of output tokens

  DELTA   last 2 days  vs  prior 5 days
  ──────────────────────────────────────────────────────────────────────────
                            baseline      recent    change
  cost / day                     $10         $17      +66%
  cache read / day              7.3M       12.7M      +73%
  cache write / day             575K        996K      +73%
  output tok / day              126K        207K      +65%
  prompts / day                 17.8        21.0      +18%
  assistant msgs / day          96.2       124.5      +29%
  tool calls / day             100.2       112.5      +12%
  compactions / day              0.0         0.0       -
  ··········································································
  msgs / prompt                  5.4         5.9      +10%
  tool calls / prompt            5.6         5.4       -5%
  output tok / prompt             7K         10K      +40%
  ··········································································
  $ / prompt                   $0.57       $0.80      +41%
  $ / assistant msg            $0.10       $0.13      +28%
  $ / tool call                $0.10       $0.15      +48%
  cache read / prompt           413K        605K      +46%
```

## The cost number is not a bill

Every dollar figure is **equivalent API cost at Anthropic's list price** — what
the same tokens would have cost through the API. If you are on a Claude
subscription you are not being charged this. Treat it as a proxy for
rate-limit weight and as a way to compare one week against another, not as an
invoice.

## Privacy

**Out of the box, ClaudeMaxing makes no network requests of any kind.** It reads
local files under your Claude Code config directory and writes one scan cache at
`~/.claude/claudemax-cache.json` holding per-day token counts and byte offsets.

There are optional community features — a comparison line on the graph, a
leaderboard, and update notifications — and they are **off until you turn them
on**. With `--community on`, each run uploads, for complete days only:

- a random install id, generated locally and not derived from you, your machine,
  or your account
- per day: total tokens, equivalent cost, prompt count
- your handle, only if you chose one with `--handle`

It never uploads file paths, project names, session ids, model names, or any
prompt or response text. Today is excluded because it is still partial. Turn it
all off again with `--community off`.

The service that receives this is [~200 lines in `server/`](server/lambda_function.py)
— that is the whole thing, so you can read exactly what is stored.

## Install

### One command

```sh
curl -fsSL https://raw.githubusercontent.com/ryuhemingway/ClaudeMaxing/main/install.sh | sh
```

Drops the single script into `~/.local/bin`. No sudo, no build step, nothing
compiled. If you would rather read it before running it — reasonable, it is
[40 lines](install.sh) — download it first:

```sh
curl -fsSL -O https://raw.githubusercontent.com/ryuhemingway/ClaudeMaxing/main/install.sh
less install.sh && sh install.sh
```

### Homebrew

```sh
brew tap ryuhemingway/tap
brew trust ryuhemingway/tap     # Homebrew 6+ only; skip if it says "Unknown command"
brew install claudemax
```

Homebrew 6.0.0 added a trust gate on third-party taps, so without the middle
line `brew install` stops with *"Refusing to load formula from untrusted tap"*.
Older Homebrew has no such gate and no `brew trust` command — skip that line.

After that first tap, `brew install claudemax` and `brew upgrade claudemax`
work by bare name. (A bare `brew install claudemax` on a machine that has
never tapped can't work — Homebrew would have to find the formula in
homebrew-core, which has a notability bar this repo doesn't meet yet.)

### From source

Requires Python 3.8+ (standard library only — no pip install, no dependencies).

```sh
git clone https://github.com/ryuhemingway/ClaudeMaxing.git
cd ClaudeMaxing
chmod +x claudemax
mkdir -p ~/.local/bin
ln -s "$PWD/claudemax" ~/.local/bin/claudemax
```

Then run `claudemax`. If the command isn't found, `~/.local/bin` isn't on
your `PATH` — add it:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

Any directory on your `PATH` works, and copying the file instead of
symlinking is fine — the symlink just means `git pull` updates the command.

## Usage

```
claudemax              last 14 active days
claudemax 30           last 30 active days
claudemax all          everything on disk
claudemax --cli        only interactive CLI traffic (exclude SDK/desktop)
claudemax --recent 2   split the delta block at the last 2 days
claudemax --models     per-model breakdown
claudemax --json       machine-readable dump
claudemax --no-color   plain output, no ANSI escapes
claudemax --refresh    discard the incremental cache and rescan
claudemax --help       usage summary
```

Flags combine: `claudemax 30 --cli --models --recent 7`.

### Community (opt-in)

```
claudemax --handle NAME       appear on the leaderboard under NAME
claudemax --community on      share anonymous daily totals without a handle
claudemax --community off     stop sharing
claudemax --no-graph          hide the line graph
claudemax --no-leaderboard    hide the leaderboard
claudemax --check-update      ask whether a newer release exists
```

The graph and leaderboard are part of the normal dashboard — no flag needed.
The graph works offline, drawing your daily cost, your own average and today.
Turning sharing on adds the community median as a second reference line and
fills in the leaderboard. When the community median sits far above your own usage it is pinned to the
top edge and labelled off scale, so your own series stays readable instead of
being squashed into the floor.

```
  YOU VS EVERYONE  ·  cost per day  ·  42 installs sharing
  ──────────────────────────────────────────────────────────────────────────
        $33 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
                           ●  │
                           │  │
                     ●  │  │  │
        $12 ───●──│──│──│──│──│
               │  │  │  ●     │
            ●     │  │        │
                  ●           ◆
         $0
            Aug 09       Aug 15

  ● your daily cost   ◆ today   ─ your avg $12   ╌ everyone (median) $103 - off scale
```

Handles are screened for profanity and slurs on the server, so the check cannot
be bypassed by posting to the endpoint directly. The matcher is separator-aware
rather than naive substring search, so `therapist`, `tycoon`, `Scunthorpe` and
`grape` are fine while `the_rapist` is not.

Setting a handle is a second, separate opt-in: with `--community on` alone you
are counted in the community figure and can see your own rank privately, but
you do not appear on the public board.

### These numbers are self-reported

There is no account system and no way to verify a report, so treat the
leaderboard as a vanity board rather than a measurement. Two things keep it
from being trivially wrecked:

- every published community figure is a **median**, not a mean, so it is
  unmoved by any minority of fabricated installs — a single fake report moves a
  mean enormously and a median not at all
- figures cover a trailing 22-day window, so one unusual day cannot swing a
  standing

Someone determined enough to register more fake installs than there are real
ones can still shift the median. Fixing that properly needs authentication,
which is a bigger thing than a vanity board justifies.

## Updates

`brew upgrade claudemax` is the update path, and it needs no network code in
the tool itself. If you have opted into community features, claudemax also
checks once a day whether a newer version has shipped and prints a one-line
notice. `claudemax --check-update` asks on demand regardless of that setting.

The first run indexes every transcript on disk and may take a few seconds.
After that it only reads the bytes appended since the last run, so subsequent
runs are near-instant.

## Reading the output

**Only active days count.** `claudemax 14` means your last 14 days *with
usage*, not the last 14 calendar days. A week off doesn't leave gaps in the
chart.

**`$ / prompt` is the number to watch.** A prompt is one thing you asked for.
`$ / assistant msg` looks like an efficiency metric but falls automatically
whenever context is compacted — a long session mechanically produces more,
cheaper messages, so the ratio improves while nothing about your work got
better. `$ / prompt` survives that. Read it alongside tool calls and output
tokens per prompt to see what the money actually bought.

**Cache read usually dominates.** In agentic sessions most of the token volume
is re-reading cached context, billed at 0.1× input. A large cache-read number
is normal and cheap; a large cache-*write* number means the prefix keeps
changing and is worth investigating.

**Compaction summaries are counted as prompts.** Claude Code records them as
user-role entries; the tool separates them into their own `compactions` column
rather than inflating your prompt count.

## Where transcripts come from

Claude Code writes one JSONL file per session under
`~/.claude/projects/<encoded-project-path>/<session-id>.jsonl`. If you've
relocated your config directory with `CLAUDE_CONFIG_DIR`, the tool follows it.

Claude Code deletes transcripts after 30 days by default (`cleanupPeriodDays`
in `settings.json`), so `claudemax all` reaches back only as far as your
retention setting allows.

## Pricing table

Prices are Anthropic's published list rates, embedded in the script near the
top and easy to edit. Cache reads are priced at 0.1× input, 5-minute cache
writes at 1.25×, and 1-hour writes at 2×. Cache-creation tokens that carry no
TTL field are priced at the 1-hour rate, which is the conservative choice.

Models with no matching entry are excluded from the cost total and reported in
a footer note, so an unpriced model shows up as a warning rather than silently
reading as $0. Rates for fully retired Claude 3 models are their historical
list prices; everything current tracks the
[pricing page](https://platform.claude.com/docs/en/about-claude/pricing).

## License

MIT — see [LICENSE](LICENSE).
