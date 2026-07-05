# Upstream issue drafts

Copy-paste ready GitHub issue bodies for mirrored packages. Post **after** [PR #12](https://github.com/tonythethompson/numan-registry/pull/12) is merged and production-published.

**Schedule:** one per week (see [upstream-release-outreach.md](../upstream-release-outreach.md)).

| # | Repo | File | Suggested week |
|---|------|------|----------------|
| 1 | [amtoine/nu-git-manager](https://github.com/amtoine/nu-git-manager) | [01-amtoine-nu-git-manager.md](01-amtoine-nu-git-manager.md) | Week 1 |
| 2 | [tesujimath/bash-env-nushell](https://github.com/tesujimath/bash-env-nushell) | [02-tesujimath-bash-env-nushell.md](02-tesujimath-bash-env-nushell.md) | Week 2 |
| 3 | [nushell-prophet/numd](https://github.com/nushell-prophet/numd) (covers dotnu too) | [03-nushell-prophet-dotnu-numd.md](03-nushell-prophet-dotnu-numd.md) | Week 3 |
| 4 | [nushell/nu_scripts](https://github.com/nushell/nu_scripts) | [04-nushell-nu-scripts.md](04-nushell-nu-scripts.md) | Week 4 |

**Precedent:** [vyadh/nutest#29](https://github.com/vyadh/nutest/issues/29)

```bash
# Example: open issue from draft (edit body first if needed)
gh issue create --repo amtoine/nu-git-manager \
  --title "Consider uploaded release zip for nupm/Numan hash-pinned installs" \
  --body-file docs/outreach-issues/01-amtoine-nu-git-manager.md
```
