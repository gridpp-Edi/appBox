#!/bin/env python3

import json
import os
import pwd
import shutil
import stat
import tarfile
import time
import urllib.request
import uuid

def getUN():
    '''
    Return the username of this account
    '''
    return pwd.getpwuid(os.getuid())[0]

appBoxVersion = '1.0.0'

#import requests
#
#image="centos"
#image_tag="7"
#
#token_response = urllib.request.urlopen(urllib.request.Request(
#    "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{}/{}:pull".format("library", image),
##    headers={"Accept" : ''}
#)).read()
##print(token_response)
#
#token = json.loads(token_response.decode())['token']
#
#print(token)
#
##response = requests.get("https://registry-1.docker.io/v2/{}/{}/manifests/{}".format("layers", image, image_tag),
##                        headers={"Authorization": "Bearer {}".format(token)})
##
##print(response)
#
#try:
#    request = urllib.request.Request(
#        "https://registry-1.docker.io/v2/{}/{}/manifests/{}".format("library", image, image_tag),
#        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json",
#                 "Authorization": "Bearer {}".format(token),
#                 "Content-Type": "application/json",
#                 "User-Agent": "curl/8.0.1"}
#    )
#    #print(request.headers)
#    manifest_response = urllib.request.urlopen(request).read()
#    print(manifest_response)
#except Exception as ex:
#    print(ex)
#    #manifest_response = urllib.request.urlopen(request).read()
#    #print(manifest_response)
#    raise


class ImageSource():

    def __init__(self, defaultCacheDir=None):
        if defaultCacheDir:
            self.imageCacheDir = defaultCacheDir
        else:
            self.imageCacheDir = '/tmp/appBox_{}'.format(getUN())

    def writeContainerInfo(self, _file, image, tag):

        appBox_metaData = { '__version__': appBoxVersion,
                            'containerName': '{}://{}:{}'.format(self.proto, image, tag),
                            'installedTime': '{}'.format(str(time.time())),
                          }
        json.dump(appBox_metaData, _file, ensure_ascii=True, indent=2)

    def dumpContainerInfo(self, metaData):

        with open(metaData, 'r') as _file:
            appBoxData = json.loads(_file.read())

        print(appBoxData)

    def getArch(self):

        ## TODO add logic to determine correct string for each arch based on running system
        return 'amd64'


class DockerHub(ImageSource):

    def __init__(self, defaultCacheDir=None, should_cleanup=False):

        ImageSource.__init__(self, defaultCacheDir)

        # Cached tokens during this instance
        self.token = {}

        self.docker_auth = "auth.docker.io"
        self.docker_auth_service = "registry.docker.io"
        self.docker_reg = "registry-1.docker.io"
        self.image_pre = "library"

        self._should_cleanup = bool(should_cleanup)

        self.proto = 'docker'

    def _getImageStr(self, image):

        image_pre = self.image_pre
        image_split = image.split('/')
        if len(image_split) > 1:
            image_pre = image_split[0]
            image = image_split[1]
        return image_pre, image

    def checkToken(self, token, image):
        '''
        Just try to list the manifest and return based on the authenticated or not
        '''
        try:
            image_pre, image = self._getImageStr(image)
            _ = urllib.request.urlopen(urllib.request.Request(
                    "https://{}/v2/{}/{}/manifests/{}".format(self.docker_reg, image_pre, image, "latest")
                )).read()
            return True
        except:
            return False

    def getToken(self, image):

        if image in self.token:
            this_token = self.token[image]
            if self.checkToken(this_token, image):
                return this_token

        image_pre, image = self._getImageStr(image)

        print("https://{}/token?service={}&scope=repository:{}/{}:pull".format(self.docker_auth, self.docker_auth_service,
                                                                               image_pre, image))
        token_response = urllib.request.urlopen(urllib.request.Request(
            "https://{}/token?service={}&scope=repository:{}/{}:pull".format(self.docker_auth, self.docker_auth_service,
                                                                             image_pre, image),
            #    headers={"Accept" : ''}
        )).read()
        #appLogger.debug('Requested token for "{}", received: "{}"'.format(image, token_response))

        token = json.loads(token_response.decode())['token']

        self.token[image] = token

        return self.token[image]

    def getDigest(self, manifest, image):

        #print(manifest)

        digest_list = []

        ## '.fsLayers[]' | jq -r '.blobSum'
        ## Read the blobSum and return

        ## '.layers[0]' | jq -r '.digest'
        ## Read the digest from the layers and return
        if 'layers' in manifest:
            for this_layer in manifest['layers']:
                digest_list.append({'mediaType': this_layer['mediaType'],
                                    'digest': this_layer['digest']})

        ## '.manifest[0]' | jq -r '.digest'
        ## Read the manifest, get the correct digests and return
        elif 'manifests' in manifest:
            this_arch = self.getArch()
            for _manifest in manifest['manifests']:
                if _manifest['platform']['architecture'] == this_arch:
                    this_csum = _manifest['digest']

                    token = self.getToken(image)
                    _headers = self.getHeaders(token, "application/vnd.oci.image.manifest.v1+json")

                    manifest_response = self.getManifests(image, this_csum, _headers)

                    manifest_json = json.loads(manifest_response)

                    digest_list = self.getDigest(manifest_json, image)

                    break

        #raise Exception('here')
        return digest_list

    def _assembleImage(self, image_layers, output_image):

        ## Perform logic to assemble layers into single compressed image

        #print(image_layers)

        tmpFolder = os.path.join(self.imageCacheDir, 'appBox_tmpFolder_{}'.format(str(uuid.uuid4())[:8]))
        os.makedirs(tmpFolder)

        for layer in image_layers:
            if layer['mediaType'] in ['application/vnd.docker.image.rootfs.diff.tar.gzip',
                                      'application/vnd.oci.image.layer.v1.tar+gzip']:
                with tarfile.open(layer['cacheFile']) as _tfile:
                    _tfile.extractall(tmpFolder)

        for (root, dirs, files) in os.walk(tmpFolder, topdown=True):
            for _dir in dirs:
                this_path = os.path.join(root,_dir)
                if not os.path.islink(this_path):
                    current = stat.S_IMODE(os.lstat(this_path).st_mode)
                    os.chmod(this_path, current | stat.S_IWUSR | stat.S_IRUSR | stat.S_ISGID)
            for _file in files:
                this_path = os.path.join(root,_file)
                if not os.path.islink(this_path):
                    current = stat.S_IMODE(os.lstat(this_path).st_mode)
                    os.chmod(os.path.join(root,_file), current | stat.S_IWUSR | stat.S_IRUSR)

        with tarfile.open(output_image, "w|gz") as tar:
            contents = os.listdir(tmpFolder)
            for _obj in contents:
                tar.add(os.path.join(tmpFolder,_obj), arcname=_obj)

        shutil.rmtree(tmpFolder)

        return output_image

    def cacheImage(self, image, tag):

        return os.path.join(self.imageCacheDir, 'appBox_{}_{}.compressed'.format(image, tag))

    def getHeaders(self, token, accept="application/vnd.docker.distribution.manifest.v2+json"):

        return {"Accept": accept,
                 "Authorization": "Bearer {}".format(token),
                 "Content-Type": "application/json",
                 "User-Agent": "curl/8.0.1"}

    def getManifests(self, image, tag, _headers):
        print(_headers)

        image_pre, image = self._getImageStr(image)

        print("https://{}/v2/{}/{}/manifests/{}".format(self.docker_reg, image_pre, image, tag))

        return urllib.request.urlopen(urllib.request.Request(
            "https://{}/v2/{}/{}/manifests/{}".format(self.docker_reg, image_pre, image, tag),
            headers = _headers,
        )).read()

    def pullContainer(self, image, tag):

        image_pre, image_sub = self._getImageStr(image)
        output_image = self.cacheImage(image_sub, tag)

        if os.path.isfile(output_image):
            print('Output Image: "{}" found for image: "{}", tag: "{}"'.format(output_image, image, tag))
            return
        else:
            print('Pulling Image for: {}:{}'.format(image, tag))

        token = self.getToken(image)

        _headers = self.getHeaders(token)

        #print(_headers)
        #print("https://{}/v2/{}/{}/manifests/{}".format(self.docker_reg, self.image_pre, image, tag))

        manifest_response = self.getManifests(image, tag, _headers)

        manifest_json = json.loads(manifest_response)

        this_digest_list = self.getDigest(manifest_json, image)

        def checkOutputLocation(outputDir):
            if not os.path.exists(outputDir):
                os.makedirs(outputDir)

        checkOutputLocation(self.imageCacheDir)

        image_layers = []

        image_pre, image = self._getImageStr(image)

        for this_digest in this_digest_list:

            output_cache = '{}_{}_{}.digest'.format(this_digest['digest'], image, tag)
            output_cache = os.path.join(self.imageCacheDir, output_cache)
            image_layers.append({'mediaType': this_digest['mediaType'],
                                 'cacheFile': output_cache,
                                 'digest': this_digest['digest']})

            with urllib.request.urlopen(urllib.request.Request(
                "https://{}/v2/{}/{}/blobs/{}".format(self.docker_reg, image_pre,
                                                      image, this_digest['digest']),
                headers = _headers)) as request_data:

                with open(output_cache, 'wb+') as _file:
                    while True:
                        chunk = request_data.read(32 * 1024)
                        if not chunk:
                            break
                        _file.write(chunk)

        assembled_image = self._assembleImage(image_layers, output_image)

        def cleanUp(to_be_removed):
            ## Loop through and unlink un-needed layer and compressed layer versions
            while _file in to_be_removed:
                os.unlink(_file)

        if self._should_cleanup:
            for _layer in image_layers:
                os.unlink(_layer['cacheFile'])

    def buildSandbox(self, image, tag, dest):

        appBox_file = os.path.join(dest, '._appBoxContainer')

        _, img = self._getImageStr(image)

        this_image = self.cacheImage(img, tag)

        if not os.path.exists(this_image):
            print('Expected to find (cached) image at: "{}", for image: "{}", tag: "{}".'.format(this_image, image, tag))
            print('Did you forget to pull first?')
            return

        if not os.path.exists(dest):
            os.makedirs(dest)
        else:
            if os.path.exists(appBox_file):
                print('Found appBox sandbox at: {}'.format(dest))
                self.dumpContainerInfo(appBox_file)
                return

        print('Extracting Compressed Image.')
        with tarfile.open(this_image) as _tfile:
            _tfile.extractall(dest)

        print('Writing metaData.')
        with open(appBox_file, 'w+') as _file:
            self.writeContainerInfo(_file, image, tag)

def testContainerHandler():

    container_list = [['centos', '7', '/scratch/appBox_rcurrie/CO7'],
                      ['almalinux', '9', '/scratch/appBox_rcurrie/AL9'],
                      ['ubuntu', '20.04', '/scratch/appBox_rcurrie/UB20'],
                      ['tensorflow/tensorflow', '2.16.1-gpu-jupyter', '/scratch/appBox_rcurrie/TF216']]

    #container_list = [['ubuntu', '20.04', '/scratch/appBox_rcurrie/UB20'], ]
    #container_list = [['centos', '7', '/scratch/appBox_rcurrie/CO7'], ]
    #container_list = [['tensorflow/tensorflow', '2.14.0-gpu-jupyter', '/scratch/appBox_rcurrie/TF214'], ]
    #container_list = [['pytorch/pytorch', '2.3.0-cuda11.8-cudnn8-runtime', '/scratch/appBox_rcurrie/PYT_230'], ]
    #container_list = [['tensorflow/tensorflow', 'nightly-gpu-jupyter', '/scratch/appBox_rcurrie/TFN'], ]
    container_list = [['almalinux', '8', '/scratch/appBox_rcurrie/AL8'], ]

    for container in container_list:

        # Construct Manager
        dockerhub_images = DockerHub()

        # Download the image in question
        args = {'image': container[0], 'tag': container[1]}
        dockerhub_images.pullContainer(**args)

        # Extract the image to disk
        args = {'image': container[0], 'tag': container[1], 'dest': container[2]}
        dockerhub_images.buildSandbox(**args)

#    container_list = [('almalinux', '9', '/sratch/appBox_rcurrie/AL9_Quay'),]
#
#    for container in container_list:
#
#        quay_images = QuayHub()
#
#        quay_images.pullContainer(**(container[:1]))
#
#        quay_images.extract(**container)


testContainerHandler()

