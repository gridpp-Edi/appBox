
## Why does this exist?

This exists to fill the gap in the between what I want and what userland Podman and Singularity/Apptainer do.

These are awesome tools in their own right, but relying on seeing up group mapping for users on a cluster is just plain annoying.

Yes this tool isn't perfect. Yes this tool does lots of things “wrong”. But frankly this is also the only tool where I can type a *single sort command* and drop into pseudo-root to install applications into a sandbox guest across various hosts without the admin having to worry about what packages are installed or permissions have been granted*.

(*obviously without namespaces we're dead on the water, but then we're doing computing asif it's the late 90s again ;) )

## What was different in Version 0?

Version0 was a very much _'proof of concept'_ tool.
The idea was to build a wrapper for Apptainer/Singularity to allow me to work quicker/faster with a sandbox based on a container.
This worked well(ish). I hit a bunch of common problems with Debian and custom distros and this encouraged me to investigate a bunch of the 'sandbox fixes' that are needed.
It also made me realise (and be thankful for) the mangling that Docker/Podman/Runc do when launching a container image to make everything work.
This was kinda based on a bunch of experiences and frustrations with all of these systems.
I think this had another name, but I forget what it was, it wasn't even in git.
This version was mix of bash templates and python tooling, this is never a good idea even for prototyping :P

## What was different in Version 1?

Version was built to make a bunch of changes and to control entering/leaving the container using nsenter and such.
This was kinda of a weird mix of tools and was good for exploring what can be done and helped me understand some things.
This version wasn't driven by a strong philosophy, however, it was capable of doing some interesting things such as control apptainer container/instances after they had launched.
This version I think was also pre-git.
Here was probably the first 'pure-python' solution.

## What was different in Version 2?

Well version2 was driven by a bet from someone. 'Can't you just make it work without Apptainer?'.
And well, ego says yes. This was the first version to use only unshare for launching sandbox environments.
This version made some design philosophy changes which I wasn't happy with, but were pragmatic. (Use of an external python library for instance)
This version was the first 'pure-python' approach to solving this problem.

## What is different in Version 3?

This version has a re-write of the Image handling layers. This is much cleaner. I've learned a bunch of things about stuff I didn't know and had fun, but this version is kind-of of what I wanted version2 to be, but version2 differed so strongly from version1 that I didn't want to continue without getting everything back to a working state.
The older 'compat' stuff is probably broken here...

## Version4?

I want to explore supporting image layers.
I want to understand how using fuser-layers can support building a sandbox-like env backed by a r/o container, compressed container, and/or CVMFS(!).
(I suspect there is already a CVMFS project to do this and probably in a better way.)

## Future plans?

Explore how sandbox nesting is handled in Apptainer or equivalent with time and emulate this, but there's only so many hours in the day
Clean-up support for multiple different versions of unshare more cleanly.
Add more control over building the environment when dropping into a sandbox.

## What does this do?

This tool installs a “permanent” but mutable sandbox environment for a userspace command to execute pseudo privileged commands within a containerised kernel namespaces. 

## What does that mean?

Think of this as being a half way house between Docker and VirtualBox.

But we still need Linux.

Because the penguin is awesome!

Long live the penguin!!!

## Why does this exist?

My commuting career started by cutting my teeth on the SL5 EOL. That was a bit of a mess.

I survived the SL6 EOL by keeping my heads down in the trenches and letting someone else deal with it.

Frankly we still haven't learned all of the lessons in time for the SL7 EOL…

To be clear we're in a better situation, but we haven't communicated the difficulty of this work to funding councils etc effectively. The EOL of win10 has received more funding and attention IMHO. (Probably because there's already a big fat stack of cash involved…)

## What do I need to install this?

Modern Linux and Python3 is likely enough. 

## But what do I actually need to install this?

Technically you also need user namespaces enabled, beyond that, this tool makes no effort to use network namespaces because that confuses users more than it helps. Besides if you want that just use a proper container orchestration tool like Docker/Podman/k8s/k3s/Azure/EC2/iCloud/… …

## Is this a security tool?

No.

This is about giving more power back to the normative mean of users who don't care about kernel namespaces and want to use a computer to do a job.

If you're an admin scared by this good. FIX YOUR SECURITY MODEL.

## Would this be better if I used package X?

Yes, almost certainly. This can all be mitigated by having admin access on a system.

The intention is for this tool to run “out of the box” on a Fedora/EL/Ubuntu/Debian(?)/… modern Linux host.  (You are running a supported secure release aren't you 😝)

This project is intended to “just work” on as many machines as possible which just have python3 installed.

## Why not just use this awesome python package Y?

See above.

## Why not use —map-{u,g}id?

At the time of writing, I'm aiming to support F39/Alma9/Ubuntu22. Not all of these systems have back ported or updated to a version of util for Linux where this is supported as a single user.

That being said, correctly mapping the user and group accounts requires managing the /etc/{passwd,group} files anyway so I'm yet to be convinced that doing anything other than mapping unknown to a user is any better. (Other than for some situations where software might be detecting this particular uig/gid… to quote team America “That's bad intelligence, very bad”)

## What is this tool?

appBox is a pure Python3 standalone userland sandboxing tool.

There are plenty of tools that do containerisation (for both users and admins), that have superior isolation to make systems more secure. These are all excellent tools at doing their jobs.

Some even support running userland containers. However, almost all require some level of setup/permissions/config from an admin who will (rightly imo!) get concerned when a user asks for elevated permissions across computing clusters or managed systems. 

Creating a user land sandbox allows you to “install a container as a virtualenv”.

This allows you to drop into an Ubuntu OS from Fedora or Redhat on Debian, install packages, compile and run tools.

## What is this not?

This is not a tool for providing isolation.

This is a tool for managing system level networking applications.

This is not a tool designed to work with/instead-of Kubernetes.

This is not a chicken.

This is not the droids you are looking for…

## How does this work?

Step 1) This app initializes a new set of namespaces as root within the host.

Step 2) Then the space is entered and bind mounts and other settings are initialized to create the sandbox.

Step 3) Finally the sandbox namespace is initialized within a pseudo terminal as either ‘anon’/’root’ mappings…

…

Step ?) Profit?

## What fixes does this apply?

This sandbox attempts to remove sandboxing within the OS at a settings level.

## Why doesn't this support X?

Good question, feel free to email me. 

## I insist you to drop everything and support Y.

That's nice but I don't have the time to 'drop everything'.


