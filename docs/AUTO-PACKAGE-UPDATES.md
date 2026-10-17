# Automated package version updates

## Overview

The `Package index updates` GitHub Actions workflow checks the package index
once a day and can also be started with **Actions → Package index updates →
Run workflow**. It never writes to `main` directly:

1. The updater checks supported upstream GitHub Releases and looks for newer
   stable versions.
2. It downloads candidate assets only when GitHub does not provide an asset
   SHA-256 digest, calculates the checksum, writes new version records on a
   dedicated branch, and validates those records.
3. `peter-evans/create-pull-request` opens or updates
   `automation/auto-package-index-updates` and assigns it to `Sha0huaZhang`.
   It assigns rather than requests a review because the pull request is
   authored by the token's account, and GitHub rejects a review request aimed
   at the author.
4. CI validates changes in the pull request. A maintainer reviews and merges
   the PR.
5. The merge event creates a bilingual `Index Update` release in
   `LinuxWaveOrg/LinuxWave`. The release title and tag include the Shanghai date
   and a per-day sequence number (for example,
   `Index Update-2026101301` / `index2026101301`). It is explicitly created
   with `latest=false`.

The daily schedule is `17:17 UTC`, which is `01:17` the following day in
Shanghai.

## Supported upstreams and architecture matching

The updater deliberately handles only straightforward, reviewable cases:

- The current package record must point to a public HTTPS GitHub Release asset
  (`github.com/{owner}/{repo}/releases/download/...`).
- The package's current version and upstream stable release tag must be plain
  numeric versions, optionally prefixed with `v` or a project name such as
  `jq-1.8.3`.
- The current record must not have a `deps` field. A new package build may
  change its dependencies, and dependency data needs a human to verify and
  add before publishing.
- A GitHub repository homepage, when present, must be the same repository as
  the release source. For projects whose homepage is not GitHub, the existing
  release URL identifies the upstream repository.
- Assets are matched independently for `arm64` and `amd64` using exact
  architecture keywords in the asset filename:
  - `arm64`: `arm64` or `aarch64`
  - `amd64`: `amd64`, `x86_64`, `x86-64`, or `x64`
- The asset must also identify Linux (`linux`, or a GNU triples target such as
  `unknown-linux-gnu` / `unknown-linux-musl`) and
  match the existing filename shape after substituting its version and
  architecture tokens. There must be exactly one match for an architecture.

Universal builds, ambiguous or renamed assets, nonstandard version tags,
dependency-bearing packages, conda packages, custom mirrors, test packages,
and packages without a numeric version are skipped rather than guessed. The
workflow includes skip reasons in the run summary. When only one architecture
has an unambiguous matching asset, only that architecture is proposed; inspect
the PR's changed paths before merging.

A failing or transient GitHub API call is retried a few times and then skips
only the affected packages, recording the reason, so one bad upstream cannot
abort the whole run. The run fails outright only when every request fails,
which points at a broken token or network rather than one flaky package.

## Checksums and validation

For each matching asset, the updater uses GitHub's release asset `sha256`
digest when present. If GitHub omits it, the updater downloads the file from a
`github.com` release URL over HTTPS and calculates SHA-256 locally, with a
512 MiB safety limit. It does not accept a missing or malformed checksum.

The record validator checks that:

- the record filename matches its package directory and architecture;
- SHA-256 is exactly 64 lowercase hexadecimal characters;
- the URL uses HTTPS; and
- the architecture the URL identifies — in the asset filename or in the mirror
  path (`linux-aarch64` / `linux-64`, as conda-forge names it) — is the one encoded
  by the record's path. A URL that identifies no architecture at all is
  accepted.

`@common` metadata files and the deliberately malformed `test_*` fixture
packages are not version records, so the validator skips both.

Unit tests cover version parsing, architecture keywords, ambiguous assets,
versionless asset names, creating paired `arm64`/`amd64` records, release-note
generation, and record validation.

## Required repository secrets

Create one personal access token (classic) with the **`repo`** scope and store
it as two Actions secrets in `LinuxWaveOrg/infosource`, both set to the same
value:

| Secret | Used for |
| --- | --- |
| `AUTOMATION_TOKEN` | pushing the automation branch and opening or updating the review PR |
| `LINUXWAVE_RELEASE_TOKEN` | creating the Index Update release in `LinuxWaveOrg/LinuxWave` |

Both secrets belong to `LinuxWaveOrg/infosource`, because that is where this
workflow runs and where GitHub resolves `secrets.*`. The release secret is
named after the repository it publishes to, not the one that stores it.

The `repo` scope covers every repository the token's owner can write to; no
other scope is needed, so do not add `workflow` or the broader `admin` scopes.
A classic token is used because a fine-grained token only reaches
organization-owned repositories once the organization allows fine-grained
personal access tokens.

A personal access token is used instead of the default `GITHUB_TOKEN` because
GitHub suppresses workflow runs caused by events initiated with
`GITHUB_TOKEN`; the PR validation and merge-triggered release would otherwise
not run. The PR will be authored by the account that owns the token, so create
it under the account that should own the automation PRs. Keep the token in
repository secrets only; never commit it.

If the secret is missing or lacks access, the workflow fails explicitly. The
merge-triggered release uses the token to create the release in `LinuxWaveOrg/LinuxWave`.
Index Update releases are explicitly marked `latest=false`, so they do not
replace the LinuxWave application release as GitHub's latest release.

## Manual review checklist

Before merging an automated PR:

1. Confirm the upstream release is the intended stable release.
2. Check that each added filename and URL is the correct Linux architecture.
3. Confirm checksums are present and the record validator passed.
4. Check whether any dependency changes are required. The updater skips
   records that already declare dependencies but cannot infer new dependency
   requirements.
5. Make sure the PR only contains expected version records.
