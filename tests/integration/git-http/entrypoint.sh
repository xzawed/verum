#!/usr/bin/env bash
set -euo pipefail

FIXTURES_SRC="${FIXTURES_SRC:-/fixtures/sample-repo}"
BARE_REPO="/srv/git/verum-fixtures/sample-repo.git"

echo "[git-http] Initializing bare repo at $BARE_REPO"
mkdir -p "$BARE_REPO"
git init --bare "$BARE_REPO"

echo "[git-http] Seeding from $FIXTURES_SRC"
WORK=$(mktemp -d)
cd "$WORK"
git init
git -c user.email="seed@verum.test" -c user.name="Verum Seed" config user.email "seed@verum.test"
git -c user.email="seed@verum.test" -c user.name="Verum Seed" config user.name "Verum Seed"
cp -r "$FIXTURES_SRC/." .
git add .
git -c user.email="seed@verum.test" -c user.name="Verum Seed" commit -m "init: seed fixture repo"
git remote add origin "file://$BARE_REPO"
git push origin HEAD:main
cd /
rm -rf "$WORK"

echo "[git-http] Starting fcgiwrap"
spawn-fcgi -s /var/run/fcgiwrap/fcgiwrap.socket -M 777 /usr/sbin/fcgiwrap

echo "[git-http] Starting nginx"
exec nginx -g "daemon off;"
