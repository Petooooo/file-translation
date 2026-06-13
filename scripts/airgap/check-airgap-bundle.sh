#!/usr/bin/env bash
set -Eeuo pipefail

BUNDLE_PATH="${1:-dist/airgap/latest}"

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

tmp_dir=""
cleanup() {
  if [ -n "$tmp_dir" ]; then
    rm -rf "$tmp_dir"
  fi
}
trap cleanup EXIT

resolve_bundle_dir() {
  path="$1"
  if [ -d "$path" ]; then
    printf '%s\n' "$path"
    return
  fi
  case "$path" in
    *.tar.gz|*.tgz)
      require_cmd tar
      tmp_dir="$(mktemp -d)"
      tar -xzf "$path" -C "$tmp_dir"
      find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1
      return
      ;;
  esac
  die "Bundle path is not a directory or .tar.gz archive: ${path}"
}

require_cmd sha256sum
require_cmd tar

bundle_dir="$(resolve_bundle_dir "$BUNDLE_PATH")"
[ -d "$bundle_dir" ] || die "Bundle directory not found: ${bundle_dir}"

required_paths=(
  "SHA256SUMS"
  "README.install-order.md"
  "chart"
  "values/values.closed.example.yaml"
  "scripts/create-secrets.example.sh"
  "manifests/images.txt"
  "manifests/image-manifest.tsv"
  "docs/AIRGAP_BUNDLE.md"
)

for path in "${required_paths[@]}"; do
  [ -e "$bundle_dir/$path" ] || die "Missing required bundle path: ${path}"
done

note "Verifying SHA256SUMS"
(cd "$bundle_dir" && sha256sum -c SHA256SUMS >/dev/null)

chart_count="$(find "$bundle_dir/chart" -maxdepth 1 -name 'file-translation-*.tgz' -type f | wc -l | tr -d ' ')"
[ "$chart_count" -ge 1 ] || die "No packaged chart found in chart/"

image_count="$(find "$bundle_dir/images" -maxdepth 1 -name '*.tar' -type f | wc -l | tr -d ' ')"
[ "$image_count" -ge 1 ] || die "No Docker image archives found in images/"

if grep -n '^\[INFO\]' "$bundle_dir/manifests/image-manifest.tsv" >/tmp/airgap-manifest-grep.out 2>&1; then
  cat /tmp/airgap-manifest-grep.out >&2
  die "Image manifest contains log lines"
fi

if ! awk 'BEGIN { FS="\t"; ok=1 } NR==1 && $0!="image\tarchive\timage_id\trepo_digests" { ok=0 } NR>1 && NF<3 { ok=0 } END { exit ok ? 0 : 1 }' "$bundle_dir/manifests/image-manifest.tsv"; then
  die "Image manifest is not a valid tab-separated manifest"
fi

manifest_image_count="$(tail -n +2 "$bundle_dir/manifests/image-manifest.tsv" | wc -l | tr -d ' ')"
[ "$manifest_image_count" -eq "$image_count" ] || die "Image manifest count ${manifest_image_count} does not match archive count ${image_count}"

while IFS= read -r archive || [ -n "$archive" ]; do
  [ -n "$archive" ] || continue
  if ! tar -tf "$archive" | grep -Fx 'manifest.json' >/dev/null; then
    die "Image archive does not look like docker save output: ${archive}"
  fi
done < <(find "$bundle_dir/images" -maxdepth 1 -name '*.tar' -type f | sort)

if grep -R --line-number --exclude='create-secrets.example.sh' -E 'local-rehearsal-.*(password|token|secret)|actual-secret|real-secret' "$bundle_dir" >/tmp/airgap-secret-grep.out 2>&1; then
  cat /tmp/airgap-secret-grep.out >&2
  die "Bundle contains text that looks like a real local rehearsal secret"
fi

if ! grep -q '<rabbitmq-password>' "$bundle_dir/scripts/create-secrets.example.sh"; then
  die "Secret example does not contain expected placeholders"
fi

pass "Airgap bundle check passed for ${bundle_dir}"
