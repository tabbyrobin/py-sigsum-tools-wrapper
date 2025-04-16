#!/usr/bin/env bash
# Script to bootstrap, for development purposes, an installation of Golang and
# the sigsum-go tools.
set -euo pipefail
set -x

# Install golang toolchain. We use this 3rd-party script because golang can be
# tricky to install.
setupGolang() {
  git clone https://github.com/canha/golang-tools-install-script
  (cd golang-tools-install-script && git checkout 2bb9d3b603709fcbe2fb27b26c70bf0ffee0d4dc)
  bash golang-tools-install-script/goinstall.sh --version 1.24.1
  rm -rf golang-tools-install-script
}

# The script only sets shell init profile for the shell it detects as your
# default $SHELL. This mimics its behavior enough to run `go install`.
envGoPath() {
  [ -z "${GOROOT:-}" ] && GOROOT="$HOME/.go"
  [ -z "${GOPATH:-}" ] && GOPATH="$HOME/go"
  PATH="$GOPATH/bin:$GOROOT/bin:$PATH"
}

# Install the Sigsum tools.
setupSigsumTools() {
  go install sigsum.org/sigsum-go/cmd/sigsum-key@v0.10.1
  go install sigsum.org/sigsum-go/cmd/sigsum-submit@v0.10.1
  go install sigsum.org/sigsum-go/cmd/sigsum-verify@v0.10.1
  go install sigsum.org/sigsum-go/cmd/sigsum-monitor@v0.10.1
}

setupGolang
envGoPath
setupSigsumTools
