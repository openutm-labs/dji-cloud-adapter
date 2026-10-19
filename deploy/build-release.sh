#!/bin/sh
# Build only committed source. No runtime/private configuration enters the bundle.
set -eu
umask 077
if [ "$#" -ne 1 ]; then
    echo "Usage: deploy/build-release.sh NEW_OUTPUT_DIRECTORY" >&2
    exit 2
fi
root=$(git rev-parse --show-toplevel)
cd "$root"
if [ -n "$(git status --porcelain)" ]; then
    echo "Commit or preserve working changes before packaging a release." >&2
    exit 1
fi
revision=$(git rev-parse HEAD)
output=$1
if [ -e "$output" ]; then
    echo "Refusing to overwrite an existing release." >&2
    exit 1
fi
mkdir -p "$output/source"
output=$(cd "$output" && pwd)
git archive --format=tar --output="$output/source.tar" "$revision"
tar -xf "$output/source.tar" -C "$output/source"
image="dji-cloud-adaptor:$revision"
docker build --build-arg "VCS_REF=$revision" -t "$image" "$output/source"
image_id=$(docker image inspect --format '{{.Id}}' "$image")
printf 'COMMIT=%s\nADAPTOR_IMAGE=%s\nIMAGE_ID=%s\n' "$revision" "$image" "$image_id" > "$output/release.env"
docker save -o "$output/image.tar" "$image"
echo "Immutable source/image package created. Transfer privately; configure runtime separately."
