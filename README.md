# Brian Micklethwait Dot Com Converter

This directory contains the tooling that converts the local mirror of
`www.brianmicklethwait.com` into static HTML placed directly inside
`../brianmicklethwaitarchive-jekyll`.

## Usage

```sh
nix develop
uv run convert_blog culture
uv run convert_blog education
uv run convert_blog edublog
uv run convert_blog weblog
uv run audit_blog culture
```

Use `all` instead of a single blog name to run every configured blog.

## Output

The converter writes static files into the Jekyll repo under:

- `culture/`
- `education/`
- `edublog/`
- `weblog/`

Each generated blog root also contains a `converter-report.json` file.
