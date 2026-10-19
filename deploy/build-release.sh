#!/bin/sh
# Build only committed source. No runtime/private configuration enters the bundle.
set -eu
umask 077
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: deploy/build-release.sh NEW_OUTPUT_DIRECTORY [linux/amd64|linux/arm64]" >&2
    exit 2
fi
root=$(git rev-parse --show-toplevel)
cd "$root"
if [ -n "$(git status --porcelain)" ]; then
    echo "Commit or preserve working changes before packaging a release." >&2
    exit 1
fi
revision=$(git rev-parse HEAD)
platform=${2:-$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')}
case "$platform" in
    linux/amd64|linux/arm64) ;;
    *) echo "Unsupported target platform; select linux/amd64 or linux/arm64." >&2; exit 1 ;;
esac
output=$1
if [ -e "$output" ]; then
    echo "Refusing to overwrite an existing release." >&2
    exit 1
fi
mkdir -p "$output/source"
output=$(cd "$output" && pwd)
git archive --format=tar --output="$output/source.tar" "$revision"
tar -xf "$output/source.tar" -C "$output/source"
image="dji-cloud-adaptor:$revision-${platform#linux/}"
docker build --platform "$platform" --build-arg "VCS_REF=$revision" -t "$image" "$output/source"
image_id=$(docker image inspect --format '{{.Id}}' "$image")
printf 'COMMIT=%s\nADAPTOR_IMAGE=%s\nIMAGE_ID=%s\nIMAGE_PLATFORM=%s\n' \
    "$revision" "$image" "$image_id" "$platform" > "$output/release.env"
docker save -o "$output/image.tar" "$image"
echo "Immutable source/image package created. Transfer privately; configure runtime separately."
