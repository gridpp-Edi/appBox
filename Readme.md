
<p align='center'>
<img src="https://raw.githubusercontent.com/gridpp-Edi/appBox/master/logo.png?raw=true" width=256 align="center"> 
</p>

<pre>
        █████╗ ██████╗ ██████╗ ██████╗  ██████╗ ██╗  ██╗
       ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝
       ███████║██████╔╝██████╔╝██████╔╝██║   ██║ ╚███╔╝ 
       ██╔══██║██╔═══╝ ██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ 
       ██║  ██║██║     ██║     ██████╔╝╚██████╔╝██╔╝ ██╗
       ╚═╝  ╚═╝╚═╝     ╚═╝     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝
</pre>



# About

AppBox was written to address the following problems:

- “I want to keep running my CentOS7 code to do my work”
- “I'm new to ML/AI how do I setup a software development environment with hardware acceleration?”
- “I can't run on Ubuntu I need Scientific Linux.”
- “I can't run on whatever this system is but it works in my laptop.”
- "I want to make a development environment I can more easily _take with me_ from machine to machine."

AppBox solves these problems by proving an automated tool for setting up and starting/running sandboxes as a normal user.
This tool does not require additional packages to be installed on most modern Linux systems where user namespaces have been deployed.


# Usage:

<pre> > ./appBox -ra
</pre>

On a RHEL9/Alma9/EL9 host this will drop you into a CentOS7 sandbox for development

If you want root access to the same sandbox you can use:

<pre> > ./appBox -rar
</pre>

### What did this just do?

1. Downloaded the docker image _"centos:7"_ from dockerhub.
2. Extracted it as a sandbox to `\scratch\appBox_${USER}\sandbox` or `\tmp\appBox_${USER}\sandbox`.
3. Made some changes to the sandbox on disk to make sure it works well.
4. Opened an interactive terminal within this sandbox environment.

### What else can it do?

- You can download any image from dockerhub.
- You can configure 'where it installs the image to'
- You can configure a few other useful things.
- You can copy/delete/move this sandbox folder as a normal user from machine to machine or from location to location.
- You can run this from an external drive if you want to.

### What can I do now?

You can exit and re-enter.

- `deactivate` has been setup to perform the same action as `exit`\\`logout` from the sandbox.

- You can re-enter the same sandbox as a normal user:<br>
 `source \scratch\appBox_${USER}\sandbox\activate`<br>
 This account is effectively just 'you' within the sandbox env.

- You can re-enter the same sandbox as a _'root'_ user:<br>
 `source \scratch\appBox_${USER}\sandbox\activate-asroot`<br>
 This is a pseudo-root account which can install software within the sandbox env.

- You can copy/move this sandbox.
- You can share this sandbox.
- You can rsync this sandbox from one machine to another.<br>
 `rsync -avP --delete USER@SERVER:/scratch/appBox_rcurrie4/sandbox/ ./sandbox-copy`<br>
 `appBox -l ./sandbox-copy -ra`

## More advanced Usage

### Running with 'GPU Support'

<pre> > ./appBox -ii tensorflow/tensorflow:latest-gpu-jupyter -ip $HOME/tf-w-gpu-support -rar -addNV
</pre>

This will grab the latest tensorflow image from dockerhub which has been installed with working GPU support and jupyter notebooks.<br>
It will install it into your home area within a folder you choose.<br>
It will mount some nvidia components from the host into the sandbox.<br>
Finally it will drop into a pseudo-root terminal within this sandbox.<br>
All without needing local root/admin access.

### Pulling from a GitLab instance

<pre> > ./appBox -ii gitlab-registry.cern.ch/atlas-flavor-tagging-tools/training-images/ml-gpu/ml-gpu:latest -ip /scratch/sandboxATLAS -ra
</pre>

This will grab an image from the CERN Gitlab instance which is used for ATLAS ml-gpu work.
This is just a demonstration of how to do this, I don't know what to do in this or why, but it exists for people to grab the sandbox from.

# FAQs:

- **AppBox does not respect user or group settings within the sandbox.**<br><br> Why would it, it's intended to be run as a single user.<br><br>
- **AppBox does not provide isolation from sandbox doing her things to user data on the host.**<br><br> This does not take advantage of network-namespaces or attempt to isolate the users data from the host. X11 forwarding even works.<br><br>
- **AppBox allows a user to do everything they have the privileges/permissions to do normally.**<br><br> This is why it exists.<br><br>
- **AppBox ‘could’ have been written in bash or go.**<br><br> I might one day do this, but frankly I know Python3 and everyone has Python3+namespaces enabled these days.<br><br>
- **AppBox isn't a solution looking for a problem.**<br><br> It's fix for what is a usability issue in this area of software development. If Apptainer rises to the challenge this could quickly become obsolete.<br><br>
- **AppBox aims to make my life and the life of others easier.**<br><br> If it does a thanks is welcome, but go buy yourself a coffee and enjoy the time this will save you.<br><br>
- **Could I just use Apptainer and ignore this?**<br><br> Yes, but this tool is about making your life easier. How much time is wasted chaining sandbox options and fake root permissions together?<br><br>


# Missing Features/TODO


## Support for private repos

Currently this tool only works with public Docker and public GitLab instances which provide a download auth-token system.
This will be modified in time to support either env vars or a direct user/pass challenge to get secure tokens, but this right now is low(er) priority.

## Support for quay.io

Currently this tool does not look for and catch the 'no-redirect' on a quay.io repository. According to RHEL docs public support for this repo service doesn't issue tokens for downloads.

## Support for AMD GPU

Don't have one. I plan to read the code from Apptainer and borrow their dev mount setup to provide rocm support.
In principle this _should_ come for free when running in WSL as we just bind the WSL plan9 guest mount, but YMMV.

## Tested support for nVidia GPU on bare metal Linux host

Don't have one of these either. Again I plan to study how Apptainer does this and copy their solution for nVidia support within containers.

## Support for Windows/MacOS

Neither of these support containers directly. Both just launch a Linux VM and run containers in that. A Linux VM on either **will** work as expected.

## Support for caching container layers

Right now only complete sandboxes are captured/cached.
With a bit of re-factoring the code can cache single layers from complex containers, but for now this has been decided to be 'enough for now'.

For more info see FAQ.md

