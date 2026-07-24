## Git workflow

- Never begin feature work directly on `main`.
- Create feature branches from an up-to-date `origin/main`.
- Incremental commits are acceptable on feature branches.
- Before integration, run the relevant tests and review the complete diff
  against `main`.
- When explicitly asked to finish a feature, squash-merge the feature branch
  locally into `main`, creating one descriptive commit.
- Pull `origin/main` with `--ff-only` before integration.
- Push `main` only after tests pass.
- Delete the local and remote feature branches only after the push succeeds.
- Do not open pull requests unless explicitly requested.
- Do not force-push `main`.
