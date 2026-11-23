#!/usr/bin/env bash
# Writes one JSON object per line to a file, and prints the path and a count of
# each record kind. Needs gh and git only (no jq, no python), and runs under
# bash 3.2, so it works on a stock macOS.
#
# Usage: gather.sh [output-file]

set -o pipefail

OUT=${1:-}
if [ -z "$OUT" ]; then
  OUT=$(mktemp "${TMPDIR:-/tmp}/rounds.XXXXXX") || exit 1
fi
: >"$OUT" || exit 1
ERRF=$(mktemp "${TMPDIR:-/tmp}/rounds-err.XXXXXX") || exit 1
trap 'rm -f "$ERRF"' EXIT

json_str() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\t'/\\t}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  printf '"%s"' "$s"
}

json_arr() {
  local first=1 line
  printf '['
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$first" = 1 ] || printf ','
    first=0
    json_str "$line"
  done
  printf ']'
}

emit() { printf '%s\n' "$1" >>"$OUT"; }

# Printable ASCII only, so a cut at 300 bytes cannot split a character.
err() {
  local msg
  msg=$(printf '%s' "$2" | tr -cd '\11\12\15\40-\176' | head -c 300)
  emit "{\"kind\":\"error\",\"step\":$(json_str "$1"),\"message\":$(json_str "$msg")}"
}

# macOS has no timeout(1), so kill the command from a background timer.
bounded() {
  local secs=$1 pid watcher rc
  shift
  "$@" &
  pid=$!
  (sleep "$secs" && kill "$pid" 2>/dev/null) &
  watcher=$!
  wait "$pid"
  rc=$?
  kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $rc
}

# Flat JSON only: "key": ["a", "b"]. Nested objects are not read.
cfg_list() {
  [ -f "$CFG" ] || return 0
  tr -d '\n\r' <"$CFG" |
    sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/p" |
    tr ',' '\n' |
    sed -e 's/^[[:space:]]*"//' -e 's/"[[:space:]]*$//' |
    grep -v '^[[:space:]]*$'
  return 0
}

LOGIN=$(gh api user --jq .login 2>&1) || {
  err "login" "gh api user failed: $LOGIN"
  printf 'rounds: gh is not signed in. Run gh auth status.\n%s\n' "$OUT"
  exit 1
}

CFG=${ROUNDS_CONFIG:-"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/rounds.json"}
MEMBERS=$(gh api user/orgs --paginate --jq '.[].login' 2>/dev/null)
ORGS=$(cfg_list orgs)
CFG_FOUND=false
if [ -f "$CFG" ]; then CFG_FOUND=true; fi
if [ "$CFG_FOUND" = true ] && [ -z "$ORGS" ]; then
  err "config" "no orgs in $CFG"
  printf 'rounds: %s exists but names no orgs. Add "orgs", or remove the file.\n%s\n' "$CFG" "$OUT"
  exit 1
fi
if [ -z "$ORGS" ]; then ORGS=$(printf '%s\n%s\n' "$LOGIN" "$MEMBERS"); fi

ROOTS=$(cfg_list roots)
if [ -z "$ROOTS" ] && [ -d "$HOME/Git" ]; then ROOTS="$HOME/Git"; fi

SELF_IN=false
if printf '%s\n' "$ORGS" | grep -qx "$LOGIN"; then SELF_IN=true; fi

ORGS_JSON=$(printf '%s\n' "$ORGS" | json_arr)
MEMBERS_JSON=$(printf '%s\n' "$MEMBERS" | json_arr)
ROOTS_JSON=$(printf '%s\n' "$ROOTS" | json_arr)

emit "{\"kind\":\"meta\",\"login\":$(json_str "$LOGIN"),\"config\":$(json_str "$CFG"),\"config_found\":$CFG_FOUND,\"orgs\":$ORGS_JSON,\"memberships\":$MEMBERS_JSON,\"roots\":$ROOTS_JSON,\"self_in_orgs\":$SELF_IN,\"generated_at\":$(json_str "$(date -u +%Y-%m-%dT%H:%M:%SZ)")}"

JQ_DEFS="def orgs: $ORGS_JSON; def members: $MEMBERS_JSON; def self_in: $SELF_IN; def me: $(json_str "$LOGIN");"
# shellcheck disable=SC2016
JQ_CI='
def rollup: (.commits.nodes[0].commit.statusCheckRollup // {state: "NONE", contexts: {nodes: []}});
def failing: [rollup.contexts.nodes[]? | select(
  (.__typename == "CheckRun" and ((.conclusion // "") | test("^(FAILURE|TIMED_OUT|STARTUP_FAILURE|ACTION_REQUIRED|CANCELLED)$")))
  or (.__typename == "StatusContext" and ((.state // "") | test("^(FAILURE|ERROR)$")))) | (.name // .context)];
def person: (.__typename == "User") and (.login != me);
def human_thread: (.comments.totalCount > (.comments.nodes | length))
  or any(.comments.nodes[]; .author != null and (.author | person));
def findings: [rollup.contexts.nodes[]? | select(.__typename == "CheckRun" and .conclusion == "NEUTRAL"
  and ((.title // "") | test("(^|[^0-9])[1-9][0-9]*([^0-9]|$)"))) | {name, title}];
'

PR_FIELDS='number title url isDraft isCrossRepository createdAt headRefName baseRefName mergeable mergeStateStatus reviewDecision
  autoMergeRequest { enabledAt }
  repository { nameWithOwner owner { login } }
  commits(last: 1) { nodes { commit { oid committedDate statusCheckRollup { state
    contexts(first: 100) { nodes { __typename
      ... on CheckRun { name conclusion title }
      ... on StatusContext { context state } } } } } } }'

# Runs a search query page by page, and prints the records that the jq program
# makes. Each page gets one retry, because GitHub search can return a 5xx.
# Args: step, GraphQL query (with $q, $after, $first), jq program, search
# string, page size, page limit.
search_paged() {
  local step=$1 query=$2 prog=$3 q=$4 size=$5 limit=$6
  local after="" page=0 resp tries
  while [ "$page" -lt "$limit" ]; do
    tries=0
    while :; do
      if [ -n "$after" ]; then
        resp=$(gh api graphql -f query="$query" -f q="$q" -F first="$size" -f after="$after" \
          --jq "$JQ_DEFS $JQ_CI ($prog), {cursor: .data.search.pageInfo}" 2>"$ERRF") && break
      else
        resp=$(gh api graphql -f query="$query" -f q="$q" -F first="$size" \
          --jq "$JQ_DEFS $JQ_CI ($prog), {cursor: .data.search.pageInfo}" 2>"$ERRF") && break
      fi
      tries=$((tries + 1))
      if [ "$tries" -ge 2 ]; then
        err "$step" "$(cat "$ERRF")"
        return
      fi
    done
    printf '%s\n' "$resp" | grep -v '^{"cursor"'
    printf '%s\n' "$resp" | grep -q '"hasNextPage":true' || return
    after=$(printf '%s\n' "$resp" | sed -n 's/.*"endCursor":"\([^"]*\)".*/\1/p')
    page=$((page + 1))
  done
  err "$step" "stopped after $((size * limit)) results for: $q"
}

# Own and upstream PRs.
Q_OWN="query(\$q: String!, \$first: Int!, \$after: String) { search(query: \$q, type: ISSUE, first: \$first, after: \$after) {
  pageInfo { hasNextPage endCursor } nodes { ... on PullRequest {
  $PR_FIELDS
  reviewThreads(first: 100) { totalCount nodes { isResolved comments(last: 30) { totalCount nodes { author { __typename login } } } } }
  reviews(last: 30) { totalCount nodes { author { __typename login } state body } }
  comments(last: 30) { totalCount nodes { author { __typename login } } } } } } }"
# shellcheck disable=SC2016
JQ_OWN='.data.search.nodes[] | select(.number) | .repository.owner.login as $o
| (if any(orgs[]; . == $o) then "own"
   elif self_in and (any(members[]; . == $o) | not) then "upstream"
   else empty end) as $scope
| (.reviewThreads.nodes | map(select(.isResolved | not))) as $open
| {kind: "pr", scope: $scope, repo: .repository.nameWithOwner, number, url, title,
   draft: .isDraft, created: .createdAt, head: .headRefName, base: .baseRefName,
   head_sha: .commits.nodes[0].commit.oid, last_commit: .commits.nodes[0].commit.committedDate,
   mergeable, merge_state: .mergeStateStatus, review_decision: .reviewDecision,
   auto_merge: (.autoMergeRequest != null), ci: rollup.state, failing: failing, findings: findings,
   cross_repo: .isCrossRepository,
   open_threads: {bot: ($open | map(select(human_thread | not)) | length),
                  human: ($open | map(select(human_thread)) | length)},
   truncated: ((.reviewThreads.totalCount > (.reviewThreads.nodes | length))
     or (.reviews.totalCount > (.reviews.nodes | length))
     or (.comments.totalCount > (.comments.nodes | length))),
   human_reviews: ([.reviews.nodes[] | select(.author != null and (.author | person) and ((.body // "") != ""))] | length),
   human_comments: ([.comments.nodes[] | select(.author != null and (.author | person))] | length)}'
search_paged prs "$Q_OWN" "$JQ_OWN" "is:pr is:open author:$LOGIN archived:false" 20 10 >>"$OUT"

# Dependabot PRs, only in repos that the user's own login owns. The update type
# comes from the metadata in Dependabot's first commit, not from the PR body:
# the body holds release notes (slow to fetch) and text from other bots.
if [ "$SELF_IN" = true ]; then
  Q_DEP="query(\$q: String!, \$first: Int!, \$after: String) { search(query: \$q, type: ISSUE, first: \$first, after: \$after) {
    pageInfo { hasNextPage endCursor } nodes { ... on PullRequest {
    $PR_FIELDS
    firstCommit: commits(first: 1) { nodes { commit { message } } }
    comments(last: 10) { nodes { body createdAt } } } } } }"
  # A 0.x minor update can break callers, so it counts as major.
  # shellcheck disable=SC2016
  JQ_DEP='.data.search.nodes[] | select(.number)
| (.firstCommit.nodes[0].commit.message // "") as $m
| ([$m | scan("dependency-name: ")] | length) as $names
| [$m | scan("update-type: ([a-z:-]+)") | .[0]] as $types
| ([$m | scan("dependency-version: 0\\.[^\\n]*\\n[^\\n]*\\n *update-type: version-update:semver-minor")] | length > 0) as $zero_minor
| {kind: "dependabot", repo: .repository.nameWithOwner, number, url, title, created: .createdAt,
   head_sha: .commits.nodes[0].commit.oid, base: .baseRefName, mergeable, merge_state: .mergeStateStatus,
   auto_merge: (.autoMergeRequest != null), ci: rollup.state, failing: failing,
   update_types: ($types | unique),
   major: (if ($types | length) == 0 or ($types | length) < $names then null
           elif any($types[]; . == "version-update:semver-major") or $zero_minor then true
           else false end),
   last_rebase_request: ([.comments.nodes[] | select(.body | test("^@dependabot (rebase|recreate)")) | .createdAt] | max)}'
  DEP_LINES=$(search_paged dependabot "$Q_DEP" "$JQ_DEP" "is:pr is:open author:app/dependabot user:$LOGIN archived:false" 20 10)

  SEEN_REPOS=""
  AUTO_REPOS=""
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case $line in '{"kind":"error"'*) emit "$line"; continue ;; esac
    repo=$(printf '%s' "$line" | sed -n 's/.*"repo":"\([^"]*\)".*/\1/p')
    base=$(printf '%s' "$line" | sed -n 's/.*"base":"\([^"]*\)".*/\1/p')
    sha=$(printf '%s' "$line" | sed -n 's/.*"head_sha":"\([^"]*\)".*/\1/p')
    case " $SEEN_REPOS " in
      *" $repo "*) ;;
      *)
        SEEN_REPOS="$SEEN_REPOS $repo"
        n=$(gh api "repos/$repo/contents/.github/workflows" \
          --jq '[.[].name | select(test("dependabot|auto-?merge"; "i"))] | length' 2>/dev/null)
        case $n in '' | *[!0-9]*) n=0 ;; esac
        if [ "$n" -gt 0 ]; then AUTO_REPOS="$AUTO_REPOS $repo"; fi
        ;;
    esac
    behind=$(gh api "repos/$repo/compare/$base...$sha" --jq .behind_by 2>/dev/null)
    case $behind in '' | *[!0-9]*) behind=null ;; esac
    case " $AUTO_REPOS " in *" $repo "*) auto=true ;; *) auto=false ;; esac
    emit "${line%\}},\"behind_by\":$behind,\"repo_automerge_workflow\":$auto}"
  done <<EOF
$DEP_LINES
EOF
fi

# Issues: every open issue in repos the login owns, and issues assigned to the
# user in the other orgs.
Q_ISS="query(\$q: String!, \$first: Int!, \$after: String) { search(query: \$q, type: ISSUE, first: \$first, after: \$after) {
  pageInfo { hasNextPage endCursor } nodes { ... on Issue { number title url createdAt updatedAt
  author { __typename login } labels(first: 5) { nodes { name } } comments { totalCount }
  repository { nameWithOwner owner { login } pushedAt } } } } }"
# shellcheck disable=SC2016
JQ_ISS='.data.search.nodes[] | select(.number) | .repository.owner.login as $o | select(any(orgs[]; . == $o))
| {kind: "issue", repo: .repository.nameWithOwner, number, title: (.title | .[0:120]),
   author: (.author.login // "ghost"), bot: ((.author.__typename // "User") != "User"),
   created: .createdAt, updated: .updatedAt, repo_pushed: .repository.pushedAt,
   stale: ((now - (.updatedAt | fromdateiso8601)) > 5184000),
   labels: [.labels.nodes[].name], comments: .comments.totalCount}'
if [ "$SELF_IN" = true ]; then
  search_paged issues "$Q_ISS" "$JQ_ISS" "is:issue is:open archived:false user:$LOGIN" 50 6 >>"$OUT"
fi
search_paged issues "$Q_ISS" "$JQ_ISS" "is:issue is:open archived:false assignee:$LOGIN -user:$LOGIN" 50 6 >>"$OUT"

# Local state: one repo per folder, one level below each root.
printf '%s\n' "$ROOTS" | while IFS= read -r root; do
  case $root in "~"/*) root="$HOME/${root#"~/"}" ;; esac
  [ -d "$root" ] || { [ -n "$root" ] && err "local" "root not found: $root"; continue; }
  for dir in "$root"/*/; do
    dir=${dir%/}
    # A symlink to another clone would list that clone twice.
    [ -L "$dir" ] && continue
    [ -d "$dir/.git" ] || continue
    url=$(git -C "$dir" remote get-url origin 2>/dev/null) || continue
    slug=$(printf '%s' "$url" | sed -n 's#.*github\.com[:/]\([^/]*/[^/]*\)$#\1#p')
    slug=${slug%.git}
    [ -n "$slug" ] || continue
    owner=${slug%%/*}
    printf '%s\n' "$ORGS" | grep -qx "$owner" || continue

    default=$(git -C "$dir" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)
    default=${default#origin/}
    default=${default:-main}
    emit "{\"kind\":\"clone\",\"repo\":$(json_str "$slug"),\"path\":$(json_str "$dir"),\"default_branch\":$(json_str "$default")}"
    others=$(git -C "$dir" for-each-ref --format='%(refname:short)' refs/heads | grep -vx "$default")
    prs=""
    if [ -n "$others" ]; then
      bounded 20 git -C "$dir" fetch --prune --quiet 2>/dev/null || err "local" "fetch failed: $dir"
      # Newest first, so the first match for a branch is its latest PR.
      prs=$(gh pr list -R "$slug" --author "$LOGIN" --state all --limit 1000 \
        --json headRefName,state,number,headRefOid --jq '.[] | "\(.headRefName):\(.state):\(.number):\(.headRefOid)"' 2>"$ERRF") ||
        err "local" "gh pr list failed for $slug: $(cat "$ERRF")"
    fi

    current=$(git -C "$dir" symbolic-ref --short -q HEAD)
    wt=$(git -C "$dir" worktree list --porcelain 2>/dev/null)
    # ':' cannot occur in a branch name, and a non-blank IFS keeps empty fields.
    git -C "$dir" for-each-ref --format='%(refname:short):%(objectname):%(upstream:short):%(upstream:track):%(committerdate:unix)' refs/heads |
      while IFS=: read -r branch sha upstream track ctime; do
        [ "$branch" = "$default" ] && continue
        wpath=$(printf '%s\n' "$wt" | awk -v ref="branch refs/heads/$branch" '/^worktree /{w=substr($0,10)} $0==ref{print w}')
        dirty=false
        if [ -n "$wpath" ] && [ -n "$(git -C "$wpath" status --porcelain 2>/dev/null | head -1)" ]; then dirty=true; fi
        wjson=null
        [ -n "$wpath" ] && wjson=$(json_str "$wpath")
        pr=$(printf '%s\n' "$prs" | awk -F: -v b="$branch" '$1 == b { print $2 " " $3 " " $4; exit }')
        pstate=null pnum=null in_pr=false
        if [ -n "$pr" ]; then
          # shellcheck disable=SC2086
          set -- $pr
          pstate=$(json_str "$1")
          pnum=$2
          if [ "$1" = MERGED ] && git -C "$dir" merge-base --is-ancestor "$sha" "$3" 2>/dev/null; then in_pr=true; fi
        fi
        in_default=false
        if git -C "$dir" merge-base --is-ancestor "$sha" "refs/remotes/origin/$default" 2>/dev/null; then in_default=true; fi
        main_checkout=false
        [ "$branch" = "$current" ] && main_checkout=true

        # A branch with no commits of its own is in the default branch too, so
        # a worktree on it can be a session that just started. Delete a branch
        # with a worktree only when a merged PR holds it, and only when no file
        # in the worktree changed in the last hour.
        safe_delete=false recent=false
        if [ "$dirty" = false ] && [ "$main_checkout" = false ]; then
          if [ -z "$wpath" ] && { [ "$in_pr" = true ] || [ "$in_default" = true ]; }; then
            safe_delete=true
          elif [ -n "$wpath" ] && [ "$in_pr" = true ]; then
            if [ -n "$(find "$wpath" \( -name .git -o -name node_modules -o -name target \) -prune -o -mmin -60 -type f -print 2>/dev/null | head -1)" ]; then
              recent=true
            else
              safe_delete=true
            fi
          fi
        fi
        emit "{\"kind\":\"local_branch\",\"repo\":$(json_str "$slug"),\"path\":$(json_str "$dir"),\"branch\":$(json_str "$branch"),\"sha\":$(json_str "$sha"),\"upstream\":$(json_str "$upstream"),\"track\":$(json_str "$track"),\"worktree\":$wjson,\"worktree_dirty\":$dirty,\"worktree_recent\":$recent,\"checked_out_in_main\":$main_checkout,\"last_commit_unix\":${ctime:-0},\"pr_state\":$pstate,\"pr_number\":$pnum,\"in_pr\":$in_pr,\"in_default\":$in_default,\"safe_delete\":$safe_delete}"
      done

    stashes=$(git -C "$dir" stash list 2>/dev/null | wc -l | tr -d ' ')
    ddirty=false
    if [ -n "$(git -C "$dir" status --porcelain 2>/dev/null | head -1)" ]; then ddirty=true; fi
    if [ "${stashes:-0}" -gt 0 ] || [ "$ddirty" = true ]; then
      emit "{\"kind\":\"local_repo\",\"repo\":$(json_str "$slug"),\"path\":$(json_str "$dir"),\"default_branch\":$(json_str "$default"),\"checkout_dirty\":$ddirty,\"stashes\":${stashes:-0}}"
    fi
  done
done

printf 'rounds: wrote %s\n' "$OUT"
grep -o '"kind":"[a-z_]*"' "$OUT" | sed 's/"kind":"//; s/"$//' | sort | uniq -c
