# 🌊 LinuxWave Data

The package index that LinuxWave reads at runtime: where every package and
dependency comes from, its `sha256`, and what it depends on.

> **Site notice**: the official website has moved to **[linuxwave.org](https://linuxwave.org)** (previously `linuxwave.macwave.org`).

# 🌊 Official Website

[linuxwave.org](https://linuxwave.org)

# 🌊 What is this repository?

LinuxWave itself lives in `LinuxWaveOrg/LinuxWave`. This repository carries
**data only** — the installer and `wave selfupdate` never read it, but
`wave install`, `wave search` and `wave info` do, and they read it live
(there is no local cache to refresh).

# 🌊 Layout

```
pkg/pkginfo_{arch}/{name}/_{name}@common             bin_name / des / hom / lic / aut
pkg/pkginfo_{arch}/{name}/_{name}@{version}          url / sha256 / deps

deps/depsinfo_{arch}/{name}/_{name}@common      dep_name / des / hom / lic / aut
deps/depsinfo_{arch}/{name}/_{name}@{version}   url / sha256 / deps
```

`{arch}` is `amd64` (linux-64) or `arm64` (linux-aarch64).

- `url` must be `https://`.
- `sha256` is verified before anything is extracted.
- `deps` lists one `name@version` per line, written as a quoted multi-line
  list. A package without a `deps` field has no dependencies.

# 🌊 Automatic Package Updates

The `Package index updates` GitHub Actions workflow checks daily for newer
stable releases and can also be started manually from the Actions tab. For a
safe match, it opens or updates a review pull request instead of publishing
records directly. The PR is assigned to the repository maintainer; merging it
creates a bilingual `Index Update` release in `LinuxWaveOrg/LinuxWave`.

The updater currently handles packages whose recorded download URL points to
a public GitHub Release, whose version is plain numeric, and whose current
record has no dependency list. If the homepage is a GitHub repository, it must
match the release repository; otherwise the repository in the existing download
URL is used as the source. The updater recognizes architecture tokens in
release asset filenames (`arm64`/`aarch64` and
`amd64`/`x86_64`/`x86-64`/`x64`), then requires one exact filename-format match
per architecture. It uses GitHub's SHA-256 asset digest, or downloads the
asset to calculate one when GitHub does not provide a digest. Ambiguous assets,
universal binaries, dependency-bearing packages, conda packages, custom mirrors,
and releases with nonstandard version tags are left for manual review.

To enable the automatic release after the PR is merged, create one personal
access token (classic) with the `repo` scope, then add it to this repository as
both the `AUTOMATION_TOKEN` and the `LINUXWAVE_RELEASE_TOKEN` secret (the same
value under both names). A personal access token
is required because the default `GITHUB_TOKEN` cannot trigger the PR checks or
the post-merge release workflow. The PR author will be the token's account, so
create it under the account that should own the automation PRs. The workflow
fails explicitly if a secret is missing; it does not silently skip publishing.
Automated Index Update releases are always created with `latest=false`.

# 🌊 Install LinuxWave

In the terminal, run:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/LinuxWaveOrg/LinuxWave/HEAD/lib/install.sh)" && source ~/.zshrc
```

(If you are using bash instead of zsh, run `source ~/.bashrc`)

**Requirements: Python (3.14 and above), patchelf (for dependency library relocation).**

# 🌊 Supported Packages
(Listed in alphabetical order)

```
bat           by David Peter
btop          by Aristocratos
dust          by bootandy
eza           by Christina Sørensen and the eza community
fd            by David Peter
ffmpeg        by FFmpeg Team
fzf           by Junegunn Choi
htop          by Hisham Muhammad and the htop team
ipsw          by blacktop
jq            by Stephen Dolan, Nicolas Williams, et al.
ldid          by Jay Freeman (saurik) / Procursus Team
lsd           by Abin Simon
ncdu          by Yoran Heling
palera1n      by palera1n Team
pandoc        by John MacFarlane
rg            by Andrew Gallant
tmux          by Nicholas Marriott and contributors
tree          by Steve Baker, Thomas Moore, et al.
trollrestore  by JJTech (@JJTech0130)
wget          by GNU Project
yq            by Mike Farah
zoxide        by Ajeet D'Souza
```

# 🌊 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

# 🌊 Contact Us

Email：[hi@macwave.org](mailto:hi@macwave.org)
