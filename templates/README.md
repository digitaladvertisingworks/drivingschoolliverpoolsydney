# Page templates

Two ways to make a page live here. Use the first one for anything new.

## 1. Build system (preferred)

One layout, shared header and footer, one small source file per page.

```
templates/base.html               document shell: head, header slot, <main>, footer slot
templates/partials/header.html    shared header, used by every built page
templates/partials/footer.html    shared footer, used by every built page
templates/partials/pricing.html   the seven published lesson packages
templates/partials/enquiry-form.html  the Web3Forms enquiry form
templates/site.config.json        public site-wide values
templates/pages/<slug>.html       front matter plus body, one per page
tools/build-pages.py              renders sources into <slug>/index.html
```

### Make a page

1. Copy `templates/pages/_example-suburb.html` to `templates/pages/<slug>.html`.
2. Set the front matter and write the body sections.
3. Run `python tools/build-pages.py <slug>`.

The output lands at `<slug>/index.html`, then `tools/inline-css.py` runs and
swaps the stylesheet link for the inlined CSS block. Add `--no-inline` to skip
that, `--check` to see what would change without writing.

A source file starting with `_` is a draft. Drafts build only when you name
them, so an unfinished page never ships by accident.

### Page source format

```
---
slug: driving-lessons-moorebank
title: Driving Lessons in Moorebank | Driving School Liverpool Centre
description: One sentence for search results.
nav: Lessons|#lessons, Packages|#packages, Enquiry|#enquiry-form
---

<!-- BLOCK: json_ld -->
  <script type="application/ld+json"> ... </script>
<!-- ENDBLOCK -->

    <section class="section" id="lessons">
      ...
    </section>

{{> partials/pricing.html }}
{{> partials/enquiry-form.html }}
```

- Front matter is `key: value`, one per line. Every key becomes a `{{ token }}`.
- `nav` is `Label|href` pairs, comma separated. The header renders them.
- A `BLOCK` captures multi-line values such as structured data.
- Everything outside the blocks is the page body, dropped into `<main>`.
- `{{> partials/name.html }}` on its own line pulls in a shared component.
- Values not set in front matter fall back to `templates/site.config.json`.

The build fails loudly on an unknown token or a missing include rather than
shipping a page with `{{ placeholders }}` in it.

### Where to make a change

| Change | Edit | Then run |
|---|---|---|
| Header, footer, form or pricing table | `templates/partials/` | `python tools/build-pages.py` |
| Phone, email, business name, form key | `templates/site.config.json` | `python tools/build-pages.py` |
| Page copy | `templates/pages/<slug>.html` | `python tools/build-pages.py <slug>` |
| Colours, spacing, components | `css/main.css` | `python tools/inline-css.py` |

`css/main.css` stays the single source of truth for styling. Never hand-edit
the `INLINE-CSS:START ... END` block inside a page: it is regenerated and your
edit will be lost.

### Secrets

`templates/site.config.json` is copied verbatim into shipped HTML, so it holds
public values only: business name, phone, email, and the Web3Forms access key,
which is a publishable form identifier. The build refuses to run if a config
key reads like a credential, for example anything named `secret`, `password`,
`private_key` or `access_token`. Anything genuinely secret belongs in a server
or Worker environment variable, never in this repo.

### Scope

The build system covers new pages. The 19 existing pages were hand-built, each
with its own navigation, structured data and in some cases its own stylesheet,
so they are not generated from `base.html`. Converting one means writing its
source file and checking the rendered output against the current page. Do that
page by page rather than in bulk.

## 2. Copy-and-edit template (legacy)

`reusable-page-template.html` is the older single-file shell with `{{TOKENS}}`
replaced by hand. `page-build-checklist.md` lists what to change. It still
works, but it copies the header and footer into every new page, which is the
duplication the build system removes. Prefer the build system.
