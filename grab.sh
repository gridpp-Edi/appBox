#!/bin/sh
#

LIB=library
#IMAGE=almalinux
#TAG=9

#IMAGE=ubuntu
#TAG=20.04

IMAGE=centos
TAG=7

TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${LIB}/${IMAGE}:pull" | jq -r .token)

echo ${TOKEN}

#TAGS=$(curl -s -H "Authorization: Bearer $TOKEN" https://index.docker.io/v2/${LIB}/${IMAGE}/tags/list)

#echo ${TAGS}

LAYERS_Q=$(curl -vvv --header "Accept: application/vnd.docker.distribution.manifest.v2+json" --header "Authorization: Bearer ${TOKEN}" "https://registry-1.docker.io/v2/${LIB}/${IMAGE}/manifests/${TAG}")

echo "https://registry-1.docker.io/v2/${LIB}/${IMAGE}/manifests/${TAG}"

#LAYERS_Q=$(curl --header "Accept: application/vnd.docker.distribution.manifest.list.v2+json" --header "Authorization: Bearer ${TOKEN}" "https://index.docker.io/v2/${LIB}/${IMAGE}/manifests/${TAG}")
LAYERS_Q=$(curl --header "Accept: application/vnd.docker.distribution.manifest.v2+json" --header "Authorization: Bearer ${TOKEN}" "https://registry-1.docker.io/v2/${LIB}/${IMAGE}/manifests/${TAG}")
#LAYERS_Q=$(curl --header "Accept: application/vnd.oci.image.manifest.v1+json" --header "Authorization: Bearer ${TOKEN}" "https://registry-1.docker.io/v2/${LIB}/${IMAGE}/manifests/${TAG}")

#LAYERS_Q=$(curl --header "Accept: application/vnd.docker.distribution.manifest.v2+json" --header "Authorization: Bearer ${TOKEN}" "https://hub.docker.com/v2/namespaces/${LIB}/repositories/${IMAGE}/tags/${TAG}")

echo ${LAYERS_Q}

#LAYERS=$(echo ${LAYERS_Q} | jq -r '.fsLayers[]' | jq -r '.blobSum' | uniq)
#LAYERS=$(echo ${LAYERS_Q} | jq -r '.layers[0]' | jq -r '.digest' | uniq)

LAYERS=$(echo ${LAYERS_Q} | jq -r '.manifest[0]' | jq -r '.digest' | uniq)

#if [ "$(echo ${LAYERS} | grep 'null')x" == "x" ]; then
#  LAYERS=$(echo ${LAYERS_Q} | jq -r '.manifests[0]' | jq -r '.digest')
#fi

echo "FINAL" ${LAYERS}

i=0
for LAYER in ${LAYERS}; do
  echo ${LAYER}
  curl --location --header "Authorization: Bearer ${TOKEN}" "https://registry-1.docker.io/v2/library/${IMAGE}/blobs/${LAYER}" --output ${IMAGE}_${TAG}.${i}
  i=$((i+1))
done

