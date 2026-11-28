> **🌊 迁移提示：LinuxWave 已并入 Summerwave。官网 <https://linuxwave.org> 已 301 跳转到 <https://summerwave.org/>；本仓库已归档，开发转到 <https://github.com/SummerwaveOrg/Summerwave>。**
> **🌊 Migration notice: LinuxWave has merged into Summerwave. The site <https://linuxwave.org> now 301-redirects to <https://summerwave.org/>. This repository is archived — development continues at <https://github.com/SummerwaveOrg/Summerwave>.**
>
> # 🚚 This repository is archived — LinuxWave is now part of **Summerwave**
>
> **New home: <https://github.com/SummerwaveOrg/Summerwave>**
> **Website: <https://summerwave.org/>** (`linuxwave.org` 301 → here)
>
> - **Existing installs keep working.** `wave`, `wave install` and `wave selfupdate` are
>   unaffected — you do not need to do anything, and this repository stays readable and its
>   releases stay downloadable.
> - **New installs, issues and pull requests go to the new repository.** This one is read-only:
>   no pushes, no issues, no pull requests.
> - Summerwave merges MacWave and LinuxWave into one codebase, one release line and one data
>   layout. LinuxWave's 4.x line ends at 4.6.x; security fixes, if any are ever needed, would be
>   cut here after a temporary unarchive.

---

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

7zz              by Igor Pavlov
act              by nektos
actionlint       by rhysd
age              by FiloSottile
atuin            by atuinsh
bat              by David Peter
btm              by Clement Tsang
btop             by Aristocratos
chezmoi          by twpayne
circleci         by CircleCI
cloudflared      by cloudflare
columbula        by Sha0huaZhang
cosign           by Sigstore
delta            by dandavison
difft            by Wilfred Hughes
direnv           by direnv
docker-compose   by Docker
doggo            by mr-karan
duckdb           by duckdb
dust             by bootandy
eza              by Christina Sørensen and the eza community
fd               by David Peter
ffmpeg           by FFmpeg Team
flyctl           by superfly
fx               by antonmedv
fzf              by Junegunn Choi
gh               by cli
git-lfs          by git-lfs
gitleaks         by gitleaks
glow             by charmbracelet
golangci-lint    by golangci
gping            by orf
grpcurl          by fullstorydev
gwget            by GNU Project
hadolint         by Hadolint
htop             by Hisham Muhammad and the htop team
hyperfine        by sharkdp
ipsw             by blacktop
jj               by Jujutsu contributors
jless            by Paul Julius Martinez
jq               by Stephen Dolan, Nicolas Williams, William Langford, Owen Ou, itchyny, Mattias Wadman, Emanuele Torre, Asaf Meizner, avid Korczynski, et al.
just             by Casey Rodarmor
k9s              by derailed
kind             by Kubernetes SIG Testing
kubecolor        by kubecolor
kubeconform      by yannh
kubectx          by ahmetb
kustomize        by Kubernetes SIG CLI
lazydocker       by Jesse Duffield
lazygit          by jesseduffield
ldid             by Jay Freeman (saurik) / Procursus Team
lefthook         by Evil Martians
linuxwave        by Orhun Parmaksız
lsd              by Abin Simon
mise             by jdx
mkcert           by FiloSottile
ncdu             by Yoran Heling
nvim             by neovim
ollama           by ollama
palera1n         by palera1n Team
pandoc           by John MacFarlane
rclone           by rclone
restic           by restic
rg               by Andrew Gallant
robinsing        by Sha0huaZhang
ruff             by astral-sh
scc              by Ben Boyter
shellcheck       by koalaman
shfmt            by mvdan
sk               by skim-rs
sops             by getsops
spf              by yorukot
starship         by starship
stern            by stern
syncthing        by Syncthing contributors
taskwarrior-tui  by kdheepak
tldr             by tealdeer-rs
tmux             by Nicholas Marriott and contributors
tofu             by opentofu
tree             by Steve Baker, Thomas Moore, Francesc Rocher, Florian Sesser, Kyosuke Tokoro
trivy            by aquasecurity
trollrestore     by JJTech (@JJTech0130)
ty               by Astral
typst            by typst
uv               by astral-sh
vhs              by charmbracelet
watchexec        by Watchexec contributors
websocat         by vi
xh               by ducaale
yazi             by sxyazi
yq               by Mike Farah
yt-dlp           by yt-dlp
zellij           by zellij-org
zoxide           by Ajeet D'Souza
```

# 🌊 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

# 🌊 Contact Us

Email：[hi@macwave.org](mailto:hi@macwave.org)
