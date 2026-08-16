# claudeusage

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

The tool reads only local files under your Claude Code config directory and
sends nothing anywhere. It has no network code at all. The single file it
writes is a scan cache at `~/.claude/usage-cache.json`, which stores per-day
token counts and byte offsets — never prompt or response text.

## Install

Requires Python 3.7+ (standard library only — no pip install, no dependencies).

```sh
git clone https://github.com/ryuhemingway/claudeusage.git
cd claudeusage
chmod +x claudeusage
ln -s "$PWD/claudeusage" ~/.local/bin/claudeusage
```

Then run `claudeusage`. If the command isn't found, `~/.local/bin` isn't on
your `PATH` — add it:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

Any directory on your `PATH` works, and copying the file instead of
symlinking is fine — the symlink just means `git pull` updates the command.

## Usage

```
claudeusage              last 14 active days
claudeusage 30           last 30 active days
claudeusage all          everything on disk
claudeusage --cli        only interactive CLI traffic (exclude SDK/desktop)
claudeusage --recent 2   split the delta block at the last 2 days
claudeusage --models     per-model breakdown
claudeusage --json       machine-readable dump
claudeusage --no-color   plain output, no ANSI escapes
claudeusage --refresh    discard the incremental cache and rescan
claudeusage --help       usage summary
```

Flags combine: `claudeusage 30 --cli --models --recent 7`.

The first run indexes every transcript on disk and may take a few seconds.
After that it only reads the bytes appended since the last run, so subsequent
runs are near-instant.

## Reading the output

**Only active days count.** `claudeusage 14` means your last 14 days *with
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
in `settings.json`), so `claudeusage all` reaches back only as far as your
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
