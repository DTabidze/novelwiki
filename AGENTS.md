## Git workflow

- Never begin feature work directly on `main`.
- Create feature branches from an up-to-date `origin/main`.
- Incremental commits are acceptable on feature branches.
- Before integration, run the relevant tests and review the complete diff
  against `main`.
- When explicitly asked to finish a feature, first ensure the working tree is
  clean and all relevant tests pass, then run
  `scripts/finish-feature.sh "<descriptive squash commit message>"`.
- Let the finish script update `main`, create the squash commit, push it, and
  delete the completed local and remote feature branches. Do not duplicate
  those steps manually unless the script stops and recovery is required.
- Do not open pull requests unless explicitly requested.
- Do not force-push `main`.
