#!/usr/bin/env bash

set -Eeuo pipefail

readonly main_branch="main"
readonly remote="origin"

usage() {
  printf 'Usage: %s "Squash commit message"\n' "$0" >&2
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

readonly commit_message="$1"
if [[ -z "${commit_message//[[:space:]]/}" ]]; then
  fail "the squash commit message cannot be empty"
fi

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
  fail "run this script from inside the repository"

readonly repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

readonly feature_branch="$(git branch --show-current)"
if [[ -z "$feature_branch" ]]; then
  fail "detached HEAD is not supported"
fi
if [[ "$feature_branch" == "$main_branch" ]]; then
  fail "run this script from the completed feature branch, not main"
fi
if [[ -n "$(git status --porcelain)" ]]; then
  fail "the working tree must be clean; commit or stash changes first"
fi

printf 'Fetching %s...\n' "$remote"
git fetch "$remote"

git show-ref --verify --quiet "refs/heads/$main_branch" ||
  fail "local branch '$main_branch' does not exist"
git show-ref --verify --quiet "refs/remotes/$remote/$main_branch" ||
  fail "remote branch '$remote/$main_branch' does not exist"

if ! git merge-base --is-ancestor \
  "$main_branch" "$remote/$main_branch"; then
  fail "local '$main_branch' has unpushed or divergent commits; reconcile it first"
fi

if [[ "$(git rev-list --count "$remote/$main_branch..$feature_branch")" -eq 0 ]]; then
  fail "the feature branch has no commits to integrate"
fi

printf 'Updating %s...\n' "$main_branch"
git switch "$main_branch"
git pull --ff-only "$remote" "$main_branch"

printf 'Squash-merging %s...\n' "$feature_branch"
git merge --squash "$feature_branch"

if git diff --cached --quiet; then
  fail "the squash produced no changes"
fi

git diff --cached --check
git commit -m "$commit_message"

printf 'Pushing %s/%s...\n' "$remote" "$main_branch"
git push "$remote" "$main_branch"

if git ls-remote --exit-code --heads "$remote" \
  "refs/heads/$feature_branch" >/dev/null 2>&1; then
  printf 'Deleting remote branch %s/%s...\n' "$remote" "$feature_branch"
  git push "$remote" --delete "$feature_branch"
fi

printf 'Deleting local branch %s...\n' "$feature_branch"
git branch -D -- "$feature_branch"

printf 'Finished: %s is on %s as one commit.\n' \
  "$feature_branch" "$main_branch"
