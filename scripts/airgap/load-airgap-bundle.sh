#!/usr/bin/env bash
set -Eeuo pipefail

BUNDLE_PATH="${1:-dist/airgap/latest}"
LOAD_TARGET="${LOAD_TARGET:-docker}"
CTR_NAMESPACE="${CTR_NAMESPACE:-k8s.io}"
K3D_CLUSTER="${K3D_CLUSTER:-}"

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

bundle_dir="$(resolve_bundle_dir "$BUNDLE_PATH")"
[ -d "$bundle_dir/images" ] || die "Bundle image directory not found: ${bundle_dir}/images"

case "$LOAD_TARGET" in
  docker)
    require_cmd docker
    loader() {
      docker load -i "$1"
    }
    ;;
  ctr)
    require_cmd ctr
    loader() {
      ctr -n "$CTR_NAMESPACE" images import "$1"
    }
    ;;
  k3s)
    require_cmd k3s
    loader() {
      k3s ctr images import "$1"
    }
    ;;
  k3d)
    require_cmd docker
    require_cmd k3d
    [ -n "$K3D_CLUSTER" ] || die "K3D_CLUSTER is required when LOAD_TARGET=k3d"
    loader() {
      docker load -i "$1"
    }
    ;;
  *)
    die "Unsupported LOAD_TARGET=${LOAD_TARGET}. Use docker, ctr, k3s, or k3d."
    ;;
esac

found=0
for archive in "$bundle_dir"/images/*.tar; do
  [ -e "$archive" ] || continue
  found=1
  note "Loading ${archive} with ${LOAD_TARGET}"
  loader "$archive"
done

[ "$found" -eq 1 ] || die "No image archives found in ${bundle_dir}/images"

if [ "$LOAD_TARGET" = "k3d" ]; then
  [ -f "$bundle_dir/manifests/images.txt" ] || die "Image list not found: ${bundle_dir}/manifests/images.txt"
  while IFS= read -r image || [ -n "$image" ]; do
    [ -n "$image" ] || continue
    note "Importing ${image} into k3d cluster ${K3D_CLUSTER}"
    k3d image import "$image" --cluster "$K3D_CLUSTER" >/dev/null
  done <"$bundle_dir/manifests/images.txt"
fi

pass "Loaded image archives from ${bundle_dir}"
printf '[INFO] Next: create the runtime Secret, adapt values.closed.yaml, then install chart/file-translation-*.tgz\n'
