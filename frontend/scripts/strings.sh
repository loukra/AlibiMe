#!/bin/sh
# Keeps the app's string catalogs in step with the code.
#
#   scripts/strings.sh          build, then add new texts to the catalogs and
#                               mark removed ones stale (translate the new ones
#                               into German afterwards)
#   scripts/strings.sh --check  build and fail if the catalogs miss a text from
#                               the code or a German translation
#
# The compiler finds every text the UI can show (Text("..."), String(localized:),
# LocalizedStringResource and the components that take one). Xcode's own build
# only extracts them; this script merges them into
# App/BelievableCall/{Localizable,AppShortcuts}.xcstrings with xcstringstool.
set -eu

cd "$(dirname "$0")/.."
CATALOGS="App/BelievableCall/Localizable.xcstrings App/BelievableCall/AppShortcuts.xcstrings"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Building to extract texts..."
xcodebuild -project App/BelievableCall.xcodeproj -scheme BelievableCall \
    -destination 'generic/platform=iOS Simulator' -derivedDataPath "$WORK/dd" \
    -quiet build >"$WORK/build.log" 2>&1 || { tail -30 "$WORK/build.log"; exit 1; }

# Every architecture: the Siri phrases (AppShortcuts) are only extracted for
# one of them. Duplicates are merged.
find "$WORK/dd/Build/Intermediates.noindex" -name '*.stringsdata' >"$WORK/files"

sync_into() {
    for catalog in "$@"; do
        # shellcheck disable=SC2046
        xcrun xcstringstool sync "$catalog" $(sed 's/^/--stringsdata /' "$WORK/files")
    done
}

if [ "${1:-}" = "--check" ]; then
    for catalog in $CATALOGS; do
        cp "$catalog" "$WORK/$(basename "$catalog")"
    done
    sync_into $(for c in $CATALOGS; do echo "$WORK/$(basename "$c")"; done)
    status=0
    for catalog in $CATALOGS; do
        if ! cmp -s "$catalog" "$WORK/$(basename "$catalog")"; then
            echo "$catalog is out of date: run scripts/strings.sh and translate the new texts."
            status=1
        fi
    done
    python3 scripts/check_translations.py $CATALOGS App/BelievableCall/InfoPlist.xcstrings || status=1
    exit $status
fi

sync_into $CATALOGS
python3 scripts/check_translations.py $CATALOGS App/BelievableCall/InfoPlist.xcstrings || true
