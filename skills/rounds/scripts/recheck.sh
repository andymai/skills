#!/usr/bin/env bash
# Prints one JSON line with the current state of a PR, and the number of
# reviews, PR comments, and thread replies that a person other than <login>
# wrote after <since>. Bots do not count. Needs gh only, and runs under bash 3.2.
#
# Usage: recheck.sh <pr-url> <login> <since, ISO 8601 UTC>

set -o pipefail

url=$1 login=$2 since=$3
if [ -z "$url" ] || [ -z "$login" ] || [ -z "$since" ]; then
  echo 'usage: recheck.sh <pr-url> <login> <since>' >&2
  exit 2
fi

# Both values go into the jq program text (gh --jq has no --arg), so accept
# only a GitHub login and an ISO 8601 UTC time.
case $login in
  *[!A-Za-z0-9-]*)
    echo "recheck.sh: not a GitHub login: $login" >&2
    exit 2
    ;;
esac
case $since in
  [0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9]Z) ;;
  *)
    echo "recheck.sh: not an ISO 8601 UTC time: $since" >&2
    exit 2
    ;;
esac

path=${url#https://github.com/}
owner=${path%%/*}
rest=${path#*/}
repo=${rest%%/*}
number=${path##*/pull/}
number=${number%%[!0-9]*}
if [ -z "$owner" ] || [ -z "$repo" ] || [ -z "$number" ]; then
  echo "recheck.sh: not a PR URL: $url" >&2
  exit 2
fi

# shellcheck disable=SC2016
query='query($o: String!, $r: String!, $n: Int!) { repository(owner: $o, name: $r) { pullRequest(number: $n) {
  state isDraft headRefOid reviewDecision
  reviews(last: 50) { totalCount nodes { author { __typename login } submittedAt } }
  comments(last: 50) { totalCount nodes { author { __typename login } createdAt } }
  reviewThreads(first: 100) { totalCount nodes { comments(last: 50) { totalCount nodes { author { __typename login } createdAt } } } } } } }'

# shellcheck disable=SC2016
prog='.data.repository.pullRequest as $p
| def person: . != null and .__typename == "User" and .login != $login;
  ([$p.reviews.nodes[] | select((.author | person) and (.submittedAt // "") > $since)]
   + [$p.comments.nodes[] | select((.author | person) and .createdAt > $since)]
   + [$p.reviewThreads.nodes[].comments.nodes[] | select((.author | person) and .createdAt > $since)]) as $new
| {state: $p.state, draft: $p.isDraft, head_sha: $p.headRefOid, review_decision: $p.reviewDecision,
   new_human: ($new | length),
   truncated: (($p.reviews.totalCount > ($p.reviews.nodes | length))
     or ($p.comments.totalCount > ($p.comments.nodes | length))
     or ($p.reviewThreads.totalCount > ($p.reviewThreads.nodes | length))
     or any($p.reviewThreads.nodes[]; .comments.totalCount > (.comments.nodes | length)))}'

gh api graphql -f query="$query" -f o="$owner" -f r="$repo" -F n="$number" \
  --jq "(\"$login\") as \$login | (\"$since\") as \$since | $prog"
