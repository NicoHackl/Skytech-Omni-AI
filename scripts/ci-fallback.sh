#!/usr/bin/env bash
# Lokale Übernahme bei fehlendem Actions-Kontingent oder einer Actions-Störung.
# Aufruf und Grenzen: docs/git-workflow.md, Abschnitt „Lokaler CI-Fallback“.
set -euo pipefail

branch="dev/dev"
check=(scripts/check.sh)
reason=""
dry_run=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --reason)
            [ "$#" -ge 2 ] || { echo "Bitte den Ausfallgrund angeben." >&2; exit 2; }
            reason="$2"; shift 2 ;;
        --dry-run) dry_run=true; shift ;;
        *) echo 'Aufruf: scripts/ci-fallback.sh --reason "Actions-Kontingent aufgebraucht" [--dry-run]' >&2; exit 2 ;;
    esac
done
[[ "$reason" =~ [^[:space:]] ]] || { echo "Bitte den Ausfallgrund mit --reason angeben." >&2; exit 2; }
fail() { echo "$*" >&2; exit 1; }
for tool in git gh; do command -v "$tool" >/dev/null || fail "Benötigtes Werkzeug fehlt: $tool"; done
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"
[ "$(git rev-parse --show-toplevel)" = "$root" ] || fail "Bitte aus einem vollständigen Projektklon starten."
assert_clean() {
    [ -z "$(git status --porcelain --untracked-files=all)" ] || fail "Es gibt ungespeicherte Änderungen. Bitte zuerst auf dem Arbeitsbranch committen und pushen."
    [ "$(git symbolic-ref --quiet --short HEAD)" = "$branch" ] || fail "Bitte auf den Arbeitsbranch $branch wechseln."
}
assert_clean
sha="$(git rev-parse HEAD)"
repo="$(gh repo view "$(git remote get-url origin)" --json nameWithOwner --jq .nameWithOwner)"
owner="${repo%%/*}"
fetch_state() {
    git fetch --prune origin '+refs/heads/*:refs/remotes/origin/*'
    [ "$(git rev-parse "refs/remotes/origin/$branch")" = "$sha" ] || fail "Lokaler und veröffentlichter Arbeitsstand unterscheiden sich. Bitte zuerst abgleichen."
    git rev-parse --verify origin/main >/dev/null || fail "Der Hauptbranch fehlt."
    if git rev-parse --verify --quiet origin/dev/main >/dev/null; then
        git merge-base --is-ancestor origin/dev/main "$sha" || fail "Der Zwischenstand ist abgewichen. Bitte die Historie prüfen; keine erzwungene Übernahme."
    fi
}
fetch_state
if git diff --quiet "origin/main...$sha"; then
    echo "Keine Änderungen für einen Pull Request vorhanden."
    exit 0
fi
[ -x "${check[0]}" ] || fail "Der gemeinsame Prüfbefehl fehlt oder ist nicht ausführbar."
printf 'Vollständige lokale Prüfung: %s\n' "${check[*]}"
"${check[@]}"
assert_clean
[ "$(git rev-parse HEAD)" = "$sha" ] || fail "Der Stand wurde während der Prüfung verändert. Bitte erneut starten."
# Nach langen Tests erneut lesen: keinen inzwischen überholten Arbeitsstand übernehmen.
fetch_state
if [ "$dry_run" = true ]; then
    echo "Lokale Prüfung bestanden. Probelauf beendet; keine Übernahme und kein Pull Request geändert."
    exit 0
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
{
    echo '<!-- local-ci-fallback:start -->'
    echo '### Lokaler CI-Fallback'
    printf '\nGrund: %s\n' "$reason"
    printf '\nLokal erfolgreich geprüft am %s mit `%s`.\n' "$(TZ=Europe/Berlin date '+%d.%m.%Y um %H:%M')" "${check[*]}"
    printf '\nGeprüfter Commit: `%s`\n' "$sha"
    echo
    echo 'Die GitHub-Prüfung ist damit nicht grün. Dieser Nachweis gilt nur für den genannten Commit'
    echo 'und den lokalen Prüfumfang; zusätzliche CI-Jobs sind dadurch nicht belegt.'
    echo 'Freigabe und Merge nach main erfolgen durch den Repo-Besitzer als Merge-Commit.'
    echo 'Release und Deployment benötigen gegebenenfalls weiterhin GitHub Actions.'
    echo '<!-- local-ci-fallback:end -->'
} > "$work/proof.md"

# Kein Merge-Commit, kein Force-Push. Ein konkurrierender, abweichender Stand wird von Git abgelehnt.
git push origin "${sha}:refs/heads/dev/main"
assert_clean
[ "$(git ls-remote origin refs/heads/dev/main | cut -f1)" = "$sha" ] || fail "Der Zwischenstand wurde inzwischen verändert. Bitte erneut prüfen."
find_pr() {
    gh pr list --repo "$repo" --head dev/main --base main --state open --json number --jq '.[0].number // empty'
}
pr="$(find_pr)"
if [ -z "$pr" ]; then
    cat "$work/proof.md" > "$work/body.md"
    printf '\nNeue Commits seit main:\n' >> "$work/body.md"
    git log --format='- %s' "origin/main..$sha" >> "$work/body.md"
    if gh pr create --repo "$repo" --head dev/main --base main --assignee "$owner" \
        --title 'Freigabe: dev/main → main' --body-file "$work/body.md"; then
        echo "Lokal geprüfter Stand übernommen; Pull Request wartet auf deine Freigabe."
        exit 0
    fi
    # Die CI kann währenddessen denselben PR geöffnet haben. Sonstige Fehler bleiben Fehler.
    pr="$(find_pr)"
    [ -n "$pr" ] || fail "Stand übernommen, aber kein Pull Request angelegt. Nach Behebung des GitHub-Zugriffs denselben Befehl erneut ausführen."
fi
# Bestehende Beschreibung erhalten; einen alten Fallback-Nachweis ersetzen statt duplizieren.
gh pr view "$pr" --repo "$repo" --json body --jq .body > "$work/old.md"
cat "$work/proof.md" > "$work/body.md"
printf '\n' >> "$work/body.md"
awk '/^<!-- local-ci-fallback:start -->$/{skip=1;next} /^<!-- local-ci-fallback:end -->$/{skip=0;next} !skip' \
    "$work/old.md" >> "$work/body.md"
gh pr edit "$pr" --repo "$repo" --add-assignee "$owner" --body-file "$work/body.md"
echo "Lokal geprüfter Stand übernommen; bestehender Pull Request mit Prüfnachweis aktualisiert."
