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

AppBox solves these problems by proving an automated tool for setting up and starting/running sandboxes as a normal user.
This tool does not require additional packages to be installed on most modern Linux systems where user namespaces have been deployed.


# Usage:

<pre> > ./appBox -ra
</pre>

On a RHEL9/Alma9/EL9 host this will drop you into a CentOS7 sandbox for development

If you want root access to the same sandbox you can use:

<pre> > ./appBox -rar
</pre>

### What did this do?

Thie downloaded the docker image _"centos:7"_ from dockerhub. Extracted it as a sandbox. Made some changes to make sure it works well. And then openned an interactive terminal within this sandbox environment.

### What else can it do?

You can configure what image it downloads from dockerhub. You can configure 'where it installs the image to' and you can configure a few other useful things.


## More advanced Usage

<pre> > ./appBox -ii tensorflow/tensorflow:latest-gpu-jupyter -ip $HOME/tf-w-gpu-support -rar -add_nv
</pre>

This will grab the latest tensorflow image from dockerhub which has been installed with working GPU support and jupyter notebooks.
It will install it into your home area within a folder you choose.
It will mount some nvidia components from the host into the sandbox.
Finally it will drop into a pseudo-root terminal within this sandbox.
All without needing local root/admin access.




# FAQs:

AppBox does not respect user or group settings.

AppBox does not provide isolation from sandbox doing her things to user data on the host.

AppBox does allow a user to do everything they have the privileges/permissions to do normally.

AppBox ‘could’ have been written in bash or go.

AppBox isn't a solution looking for a problem. It's fix for what is a usability issue in this area of software development.

AppBox aims to make my life and the life of others easier.

Could I just use Apptainer and ignore this? - Yes, but this tool is about making your life easier. How much time is wasted chaining sandbox options and fake root permissions together?


For more info see FAQ.md
