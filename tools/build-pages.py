#!/usr/bin/env python3
"""
Build static pages from one shared layout.

    python tools/build-pages.py                 # build every page source
    python tools/build-pages.py moorebank       # build one slug
    python tools/build-pages.py --check         # report, write nothing

Inputs
    templates/base.html              the document shell (head, header slot, main, footer slot)
    templates/partials/*.html        shared components pulled in with {{> partials/name.html }}
    templates/site.config.json       public site-wide values
    templates/pages/<slug>.html      one file per page: front matter + body

Output
    <slug>/index.html                (slug "home" writes to index.html at the root)

The build is deliberately dumb: substitute tokens, resolve includes, write the
file. No dependencies, no runtime templating, no JavaScript framework. What
ships is still a plain static HTML file that Cloudflare serves as-is.

After building, run tools/inline-css.py to swap the stylesheet link for the
inlined critical CSS block, exactly as the hand-built pages do. Pass
--no-inline to skip that step.

Editing rules
    Header or footer change  -> edit templates/partials/, rebuild, everything follows.
    Page copy change         -> edit templates/pages/<slug>.html only.
    Design system change     -> edit css/main.css, then run tools/inline-css.py.
"""
import io
import os
import re
import sys
import json
import glob
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, 'templates')
BASE = os.path.join(TPL, 'base.html')
CONFIG = os.path.join(TPL, 'site.config.json')
PAGES = os.path.join(TPL, 'pages')

RE_INCLUDE = re.compile(r'^([ \t]*)\{\{>\s*([A-Za-z0-9_./-]+)\s*\}\}[ \t]*$', re.M)
RE_TOKEN = re.compile(r'\{\{\s*([a-z0-9_]+)\s*\}\}')
RE_BLOCK = re.compile(r'<!--\s*BLOCK:\s*([a-z0-9_]+)\s*-->(.*?)<!--\s*ENDBLOCK\s*-->', re.S)

# A page never needs these, and shipping one would leak it to every visitor.
SECRET_KEY = re.compile(r'secret|password|passwd|private[_-]?key|\bapi[_-]?key\b|access[_-]?token|bearer', re.I)

# Optional tokens: absent means empty string rather than a build failure.
OPTIONAL = ('json_ld', 'page_scripts', 'packages_heading', 'packages_lead')


def die(msg):
    sys.exit('build-pages: ' + msg)


def load_config():
    cfg = json.loads(io.open(CONFIG, encoding='utf-8').read())
    for key in cfg:
        if key.startswith('_'):
            continue
        # "web3forms_public_key" is a publishable form id, not a credential; the
        # name says so. Anything else that reads like a secret stops the build.
        if SECRET_KEY.search(key) and not key.endswith('_public_key'):
            die('%s looks like a secret. Frontend config holds public values only.' % key)
    return dict((k, v) for k, v in cfg.items() if not k.startswith('_'))


def read(path):
    return io.open(path, encoding='utf-8').read()


def resolve_includes(text, seen=()):
    """Expand {{> partials/x.html }}, keeping the include line's indentation."""
    def sub(m):
        indent, rel = m.group(1), m.group(2)
        if rel in seen:
            die('include loop at %s' % rel)
        path = os.path.join(TPL, rel)
        if not os.path.exists(path):
            die('missing include %s' % rel)
        body = resolve_includes(read(path), seen + (rel,))
        lines = body.rstrip('\n').split('\n')
        return '\n'.join(indent + l if l.strip() else l for l in lines)
    return RE_INCLUDE.sub(sub, text)


def parse_page(path):
    """Split a page source into front matter, named blocks and body content."""
    raw = read(path)
    if not raw.startswith('---'):
        die('%s must start with a --- front matter block' % os.path.basename(path))
    _, front, body = raw.split('---', 2)

    data = {}
    for line in front.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            die('bad front matter line in %s: %s' % (os.path.basename(path), line))
        key, value = line.split(':', 1)
        data[key.strip()] = value.strip()

    for name, block in RE_BLOCK.findall(body):
        data[name] = block.strip('\n')
    body = RE_BLOCK.sub('', body)

    data['content'] = body.strip('\n')
    return data


def render_nav(spec):
    """'Services|#services, FAQ|#faq' -> the anchor list the header expects."""
    out = []
    for item in [s.strip() for s in spec.split(',') if s.strip()]:
        if '|' not in item:
            die('nav item needs Label|href, got %r' % item)
        label, href = item.split('|', 1)
        out.append('        <a href="%s">%s</a>' % (href.strip(), label.strip()))
    return '\n'.join(out)


def build_one(src, cfg, check):
    page = parse_page(src)
    slug = page.get('slug') or os.path.splitext(os.path.basename(src))[0]

    values = dict(cfg)
    values.update(page)
    values['slug'] = '' if slug == 'home' else slug
    values['canonical'] = (cfg['site_url'] + '/' if slug == 'home'
                           else '%s/%s/' % (cfg['site_url'], slug))
    values['nav'] = render_nav(page.get('nav', ''))
    values.setdefault('og_title', values.get('title', ''))
    values.setdefault('og_description', values.get('description', ''))
    for key in OPTIONAL:
        values.setdefault(key, '')

    # Content goes into the shell first, so a page may pull in partials of its
    # own. Includes are resolved once over the whole document, then tokens are
    # substituted once, which covers tokens that live inside a partial.
    html = read(BASE).replace('{{ content }}', values.pop('content'))
    html = resolve_includes(html)
    missing = sorted(set(RE_TOKEN.findall(html)) - set(values))
    if missing:
        die('%s is missing: %s' % (os.path.basename(src), ', '.join(missing)))
    html = RE_TOKEN.sub(lambda m: values[m.group(1)], html)

    left = sorted(set(RE_TOKEN.findall(html)))
    if left:
        die('unresolved token(s) after render: %s' % ', '.join(left))

    out = os.path.join(ROOT, 'index.html') if slug == 'home' \
        else os.path.join(ROOT, slug, 'index.html')
    rel = os.path.relpath(out, ROOT).replace(os.sep, '/')

    if check:
        old = read(out) if os.path.exists(out) else ''
        print('%-46s %s' % (rel, 'unchanged' if old == html else 'would change'))
        return False

    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    io.open(out, 'w', encoding='utf-8', newline='\n').write(html)
    print('built %s' % rel)
    return True


def main():
    args = [a for a in sys.argv[1:]]
    check = '--check' in args
    no_inline = '--no-inline' in args
    names = [a for a in args if not a.startswith('--')]

    if not os.path.exists(BASE):
        die('missing templates/base.html')
    cfg = load_config()

    sources = sorted(glob.glob(os.path.join(PAGES, '*.html')))
    # A leading underscore marks a draft. Drafts build only when named, so a
    # half-written page never lands on the live site by accident.
    if not names:
        sources = [s for s in sources
                   if not os.path.basename(s).startswith('_')]
    if names:
        wanted = set(n.replace('.html', '') for n in names)
        sources = [s for s in sources
                   if os.path.splitext(os.path.basename(s))[0] in wanted]
        if not sources:
            die('no page source matched %s' % ', '.join(names))
    if not sources:
        print('no page sources in templates/pages/, nothing to build')
        return

    wrote = sum(1 for s in sources if build_one(s, cfg, check))
    if wrote and not no_inline:
        subprocess.call([sys.executable, os.path.join(ROOT, 'tools', 'inline-css.py')])


if __name__ == '__main__':
    main()
