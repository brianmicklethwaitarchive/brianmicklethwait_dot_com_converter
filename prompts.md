A record of the prompts used to make this tool.

# Step 1: Initial prompt

The directory brianmicklethwaitarchive-jekyll is a static web site where I archive Brian's writings.

My aim is to add a static version of his blogs to this site. His old site is in the directory www.brianmicklethwait.com . There are separate blogs in the culture, edublog and education directories.

The plan is to create tools in the brianmicklethwait_dot_com_converter directory that I can run to generate static versions of these blogs within the jekyll site.

I don't need to use jekyll for this - we can directly convert/generate HTML with the original css styles. The main aim is to fix links and such, and make it so when we deploy with the scripts in brianmicklethwaitarchive-deploy , we get links from the front page of the main archive site to archived, static versions of the blogs.

Internal links should be fixed. Images should be displayed in their original small sizes - when they link to big versions of images I'd like to remove those links to avoid having to host big images.

It's possible different blogging frameworks were used to make the blogs -- we can deal with them one at a time and if necessary make multiple conversion programs.

I'm open to suggestions about languages to use. We'll have a Nix flake with a devShell to make any language tooling available.

Please look at what we have and make a plan.

# The AI's plan
Using Codex, GPT-5.4 in plan mode responded with the following.

## Summary
Build a Python-based conversion toolkit in `brianmicklethwait_dot_com_converter` that reads the local mirror in `www.brianmicklethwait.com`, rewrites it into clean static HTML, and writes the generated output directly into `brianmicklethwaitarchive-jekyll` so Jekyll just copies it through unchanged.

Implement this as a staged migration because the source is not one system:
- Movable Type-style static blogs: `culture` and the older `education` tree
- ExpressionEngine-style static mirror: later `edublog` content under `index.php/education`, plus the much larger `index.php/weblog`

Delivery order:
1. `culture`
2. older `education`
3. `edublog`
4. `weblog`

## Key Changes
- Add a converter flake/devShell in `brianmicklethwait_dot_com_converter` with Python, `uv`, HTML parsing, and a small CLI.
- Expose one CLI with per-blog targets, for example:
  - `uv run convert_blog culture`
  - `uv run convert_blog education`
  - `uv run convert_blog edublog`
  - `uv run convert_blog weblog`
  - `uv run audit_blog <blog>`
- Structure the code as one shared rewrite pipeline plus two source adapters:
  - `mt_adapter` for `culture` and old `education`
  - `ee_adapter` for `edublog` and `weblog`
- Generate final public paths inside the archive site as:
  - `/culture/` for the culture blog
  - `/education/` for the older Movable Type education blog
  - `/edublog/` for the later ExpressionEngine-era education blog
  - `/weblog/` for Brian’s main later blog
- Write generated pages and copied assets into root-level static directories in `brianmicklethwaitarchive-jekyll`, not into `_site`, so normal Jekyll build/deploy remains unchanged.
- Update the archive homepage so it links directly to the new internal static blog entry points instead of the old external site URLs.

Rewrite rules to implement in the shared pipeline:
- Convert all internal old-domain links and relative links to the new archive paths above.
- Materialize CSS currently referenced via `index.php?css=...` into normal static CSS files under the relevant blog output.
- Copy only assets needed by generated pages, preserving existing small-image display dimensions.
- When an image is wrapped in a same-site popup/enlargement link, remove the link but keep the `<img>`.
- Remove or neutralize dynamic behaviors that cannot work statically:
  - comment-post forms
  - trackback links
  - search submit forms
  - CGI endpoints and JS that only supports those features
- Preserve archive/category/comment-view pages where they already exist in the mirrored source, so internal navigation stays intact.
- Emit a per-run manifest/report with:
  - generated page count
  - copied asset count
  - rewritten-link count
  - removed popup-image-link count
  - unresolved local links/assets

## Test Plan
- For each blog run, verify the generator is idempotent and produces no unexpected diffs on a second run.
- Run `bundle exec jekyll build` in `brianmicklethwaitarchive-jekyll` after each blog is added.
- Smoke-test each converted blog with a fixed sample set:
  - home page
  - one post page
  - one archive page
  - one category page
  - one page with inline images
  - one page that originally used a popup/enlarged image link
  - one page with comments or comment navigation where applicable
- Add automated checks that fail if generated HTML still contains:
  - `www.brianmicklethwait.com` internal URLs
  - `index.php?css=`
  - `cgi-bin`
  - `mt-comments`, `mt-search`, or trackback form actions
- For `weblog`, run a small representative subset first, then a full conversion pass, because it is the largest source tree by far.

## Assumptions And Defaults
- The latest naming decision overrides the earlier `/education` preference for the newer blog: old static education stays at `/education/`, and the later education-era blog publishes at `/edublog/` to avoid a path collision.
- V1 guarantees fixed internal navigation inside the archive site; it does not attempt to preserve every old public URL as a redirect unless that becomes necessary later.
- Generated blog HTML/assets will be committed in `brianmicklethwaitarchive-jekyll`, while the converter code lives separately in `brianmicklethwait_dot_com_converter`.
- Jekyll is only the packaging/deploy container for these generated files; the blog pages themselves stay hand-generated static HTML using their original styling rather than being re-authored as Jekyll posts.

# Step 2: synthesising archive pages

My prompt:

Most of the results are good; however the culture blog front page has no articles.

I think it is because articles became more rare towards the period Brian was writing for this blog.

Furthermore, the "archives" sections of the main page is empty, probably because this was a dynamic element and we are now making a static site.

I would like to do two things for pages of this type:
1) synthesise the archives section if needed so that we have links to pages in the monthly archive sections with articles for that month
2) at the bottom of each page, a "more" link that continues to the next page in the blog.

It would be ok for these pages to just have links with date and title of each article, but the more it is practical to add the better.

# AI's final response to page synthesis request (after thinking and testing)

Updated the MT conversion path so culture and education now synthesize real listing pages instead of preserving the old empty dynamic shells. The main logic is in mt_adapter.py with pipeline support in pipeline.py.

That now gives you:

- populated front pages like culture/index.html and education/index.html
- synthetic monthly archive index pages such as culture/archives/2005/10/index.html
- filled-in Archives sidebars with month links and post counts
- a More link at the bottom of these synthesized listing pages to continue into older months
I rebuilt culture and education, both audits are clean, and bundle exec jekyll build succeeds. One residual thing I noticed is that a few source titles still have old encoding mojibake in the underlying mirror, so if you want, the next pass could be about normalizing those titles and excerpts.
