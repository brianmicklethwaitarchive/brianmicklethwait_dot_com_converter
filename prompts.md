A record of the prompts used to make this tool.

# Initial prompt

The directory brianmicklethwaitarchive-jekyll is a static web site where I archive Brian's writings.

My aim is to add a static version of his blogs to this site. His old site is in the directory www.brianmicklethwait.com . There are separate blogs in the culture, edublog and education directories.

The plan is to create tools in the brianmicklethwait_dot_com_converter directory that I can run to generate static versions of these blogs within the jekyll site.

I don't need to use jekyll for this - we can directly convert/generate HTML with the original css styles. The main aim is to fix links and such, and make it so when we deploy with the scripts in brianmicklethwaitarchive-deploy , we get links from the front page of the main archive site to archived, static versions of the blogs.

Internal links should be fixed. Images should be displayed in their original small sizes - when they link to big versions of images I'd like to remove those links to avoid having to host big images.

It's possible different blogging frameworks were used to make the blogs -- we can deal with them one at a time and if necessary make multiple conversion programs.

I'm open to suggestions about languages to use. We'll have a Nix flake with a devShell to make any language tooling available.

Please look at what we have and make a plan.
