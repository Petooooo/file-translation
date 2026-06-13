#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PATH="$HOME/.local/bin:$PATH"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d%H%M%S)}"
BUNDLE_DIR="${BUNDLE_DIR:-dist/airgap/file-translation-airgap-${TIMESTAMP}}"
IMAGE_LIST="${IMAGE_LIST:-scripts/airgap/images.closed.txt}"
LOCAL_DEP_IMAGE_LIST="${LOCAL_DEP_IMAGE_LIST:-scripts/airgap/images.local-dependencies.txt}"
INCLUDE_LOCAL_DEPS="${INCLUDE_LOCAL_DEPS:-0}"
PULL_MISSING="${PULL_MISSING:-0}"
CHART_DIR="${CHART_DIR:-charts/file-translation}"
VALUES_FILE="${VALUES_FILE:-charts/file-translation/values.closed.example.yaml}"

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_cmd() {
  has_cmd "$1" || die "$1 is required"
}

read_image_list() {
  file="$1"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
      *) printf '%s\n' "$line" ;;
    esac
  done <"$file"
}

archive_name_for_image() {
  image="$1"
  printf '%s.tar' "$image" | tr '/:@' '___'
}

require_cmd docker
require_cmd helm
require_cmd sha256sum
require_cmd tar

[ -f "$IMAGE_LIST" ] || die "Image list not found: ${IMAGE_LIST}"
[ -f "$VALUES_FILE" ] || die "Values file not found: ${VALUES_FILE}"
[ -d "$CHART_DIR" ] || die "Chart directory not found: ${CHART_DIR}"

rm -rf "$BUNDLE_DIR"
mkdir -p \
  "$BUNDLE_DIR/images" \
  "$BUNDLE_DIR/chart" \
  "$BUNDLE_DIR/values" \
  "$BUNDLE_DIR/scripts" \
  "$BUNDLE_DIR/manifests" \
  "$BUNDLE_DIR/docs"

note "Linting and packaging Helm chart"
helm lint "$CHART_DIR" >/dev/null
helm package "$CHART_DIR" --destination "$BUNDLE_DIR/chart" >/dev/null
cp "$VALUES_FILE" "$BUNDLE_DIR/values/values.closed.example.yaml"
cp charts/file-translation/values.closed.local-rehearsal.yaml "$BUNDLE_DIR/values/values.closed.local-rehearsal.yaml"
cp scripts/airgap/create-secrets.example.sh "$BUNDLE_DIR/scripts/create-secrets.example.sh"
mkdir -p "$BUNDLE_DIR/scripts/airgap"
cp scripts/airgap/*.sh "$BUNDLE_DIR/scripts/airgap/"
cp scripts/airgap/INSTALL_ORDER.README.md "$BUNDLE_DIR/README.install-order.md"
cp docs/AIRGAP_BUNDLE.md "$BUNDLE_DIR/docs/AIRGAP_BUNDLE.md"
cp docs/CLOSED_NETWORK_DEPLOYMENT.md "$BUNDLE_DIR/docs/CLOSED_NETWORK_DEPLOYMENT.md"
cp docs/IMAGE_INVENTORY.md "$BUNDLE_DIR/docs/IMAGE_INVENTORY.md"

tmp_images="$(mktemp)"
cleanup() {
  rm -f "$tmp_images"
}
trap cleanup EXIT

read_image_list "$IMAGE_LIST" >"$tmp_images"
if [ "$INCLUDE_LOCAL_DEPS" = "1" ]; then
  [ -f "$LOCAL_DEP_IMAGE_LIST" ] || die "Local dependency image list not found: ${LOCAL_DEP_IMAGE_LIST}"
  read_image_list "$LOCAL_DEP_IMAGE_LIST" >>"$tmp_images"
fi

sort -u "$tmp_images" -o "$tmp_images"
cp "$tmp_images" "$BUNDLE_DIR/manifests/images.txt"

{
  printf 'image\tarchive\timage_id\trepo_digests\n'
  while IFS= read -r image || [ -n "$image" ]; do
    [ -n "$image" ] || continue
    if ! docker image inspect "$image" >/dev/null 2>&1; then
      if [ "$PULL_MISSING" = "1" ]; then
        note "Pulling missing image ${image}" >&2
        docker pull "$image" >/dev/null
      else
        die "Image is not available locally: ${image}. Pull/build it first or rerun with PULL_MISSING=1."
      fi
    fi

    archive="$(archive_name_for_image "$image")"
    note "Saving ${image} -> images/${archive}" >&2
    docker save -o "$BUNDLE_DIR/images/$archive" "$image"

    image_id="$(docker image inspect --format '{{.Id}}' "$image")"
    repo_digests="$(docker image inspect --format '{{join .RepoDigests ","}}' "$image")"
    printf '%s\t%s\t%s\t%s\n' "$image" "images/$archive" "$image_id" "$repo_digests"
  done <"$tmp_images"
} >"$BUNDLE_DIR/manifests/image-manifest.tsv"

note "Writing checksums"
(
  cd "$BUNDLE_DIR"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum >SHA256SUMS
)

note "Creating compressed bundle archive"
tarball="${BUNDLE_DIR}.tar.gz"
tar -czf "$tarball" -C "$(dirname "$BUNDLE_DIR")" "$(basename "$BUNDLE_DIR")"
sha256sum "$tarball" >"${tarball}.sha256"

pass "Airgap bundle written to ${BUNDLE_DIR}"
pass "Compressed archive written to ${tarball}"
