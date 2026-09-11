#!/usr/bin/env python3
"""
Turn structured JSON content into page sources for tools/build-pages.py.

    python tools/import-pages.py                 # every page in the source set
    python tools/import-pages.py liverpool       # slugs matching a substring
    python tools/import-pages.py --list          # show what would be written

Input
    <SOURCE>/content/suburbs/<slug>.json    a suburb page
    <SOURCE>/content/services/<slug>.json   a service page
    <SOURCE>/app/config/site.js             the suburb hub, read once via hub.json

Output
    templates/pages/<slug>.html             front matter plus body

The JSON came from another site, so three things happen on the way through.
Brand names, phone numbers and email addresses are rewritten to this business.
Links to pages that do not exist here are remapped or unlinked, because a
generated page must never ship a 404. Section types are re-expressed in this
site's own components rather than the source markup, since none of the source
CSS lives here.

The renderers below are the whole mapping. Add a section type by adding a
render_<type> function; an unknown type stops the run rather than silently
dropping content.
"""
import io
import os
import re
import sys
import json
import glob
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.environ.get(
    'IMPORT_SOURCE',
    os.path.join(os.path.dirname(ROOT), 'sydneysouth-v2'))
PAGES = os.path.join(ROOT, 'templates', 'pages')
HUB = os.path.join(ROOT, 'templates', 'hub.json')
LINKS = os.path.join(ROOT, 'templates', 'internal-links.json')

BUSINESS = 'Driving School Liverpool Centre'

# Brand, contact details and domain of the source site, rewritten to ours.
# Longest patterns first so a broad one cannot eat a narrow one.
REBRAND = [
    (r'Sydney South Driving School', BUSINESS),
    (r'sydneysouth\.appointy\.com', 'drivingschoolliverpool.sydney/contact-us'),
    (r'https?://(?:www\.)?sydneysouth\.net', 'https://drivingschoolliverpool.sydney'),
    (r'liverpool@sydneysouth\.net', 'info@drivingschoolliverpool.sydney'),
    (r'info@sydneysouth\.net', 'info@drivingschoolliverpool.sydney'),
    (r'\(02\)\s*8277\s*9091', '(02) 8776 1815'),
    (r'02\s*8277\s*9091', '(02) 8776 1815'),
    (r'\+61282779091', '+61287761815'),
    (r'tel:\+?61282779091', 'tel:0287761815'),
    (r'0409\s*129\s*275', '(02) 8776 1815'),
    (r'\bSydney South\b(?! Driving)', 'Driving School Liverpool Centre'),
]

# Source links whose page does not exist here. A path maps to a real
# destination, or to None to keep the words and drop the anchor.
LINK_MAP = {
    '/driving-lesson-prices/': '/our-services/#packages',
    '/about-our-driving-school/': '/about-us/',
    '/how-many-hours-to-learn-driving-in-nsw-australia/': None,
    '/how-to-get-p2-to-full-licence-nsw/': None,
    '/service-nsw-drive-test-criteria-2025/': None,
    '/preparing-for-your-driving-test-for-liverpool-nsw-service-centre/': None,
    '/driving-lesson-gift-vouchers/': None,
}

# Every page's form is the shared enquiry form, so all the source's per-page
# form anchors collapse onto one id.
RE_FORM_ANCHOR = re.compile(r'#[a-z0-9-]*form\b')

SLUGS_BUILT = set()


def die(msg):
    sys.exit('import-pages: ' + msg)


def rebrand(text):
    for pattern, replacement in REBRAND:
        text = re.sub(pattern, replacement, text)
    return text


def e(text):
    """Escape for HTML text, after rebranding."""
    return html.escape(rebrand(str(text)), quote=False)


def attr(text):
    return html.escape(rebrand(str(text)), quote=True)


def href(link):
    """Resolve a source link to something that exists on this site."""
    if not link:
        return None
    link = rebrand(link)
    if link.startswith('#'):
        return RE_FORM_ANCHOR.sub('#enquiry-form', link)
    base = link.split('#')[0]
    if base in LINK_MAP:
        return LINK_MAP[base]
    if base.startswith('/'):
        slug = base.strip('/')
        if slug and slug not in SLUGS_BUILT and not os.path.exists(
                os.path.join(ROOT, slug, 'index.html')):
            return None
    return link


def link_phrase(text, phrase, target):
    """Wrap the first occurrence of `phrase` in `text` with a link."""
    url = href(target)
    if not url or not phrase or phrase not in text:
        return e(text)
    before, _, after = text.partition(phrase)
    return '%s<a href="%s">%s</a>%s' % (e(before), attr(url), e(phrase), e(after))


def img(image, css_class=None, lazy=True):
    """Point at the optimised webp the repo serves, keeping the given size."""
    src = image['src']
    stem = os.path.splitext(os.path.basename(src))[0]
    cls = ' class="%s"' % css_class if css_class else ''
    return (
        '<img%s\n'
        '            src="/img/opt/%s.webp"\n'
        '            alt="%s"\n'
        '            width="%s"\n'
        '            height="%s" decoding="async"%s>'
        % (cls, stem, attr(image.get('alt', '')), image.get('width', ''),
           image.get('height', ''), ' loading="lazy"' if lazy else ''))


def actions(items, indent=8):
    out = []
    for i, a in enumerate(items or []):
        url = href(a.get('href'))
        if not url:
            continue
        # btn--ghost is the white-on-dark variant; sections here sit on a
        # light ground, so the secondary action uses the surface variant.
        style = 'btn--primary' if i == 0 else 'btn--ghost-surface'
        out.append('%s<a class="btn %s" href="%s">%s</a>'
                   % (' ' * (indent + 2), style, attr(url), e(a['label'])))
    if not out:
        return ''
    return ('\n%s<div class="section-actions section-actions--center">\n%s\n%s</div>'
            % (' ' * indent, '\n'.join(out), ' ' * indent))


def heading(sec, centered=True):
    """The eyebrow, h2 and lead every section type shares."""
    cls = ' section-heading--center' if centered else ''
    out = ['        <div class="section-heading%s">' % cls]
    if sec.get('eyebrow'):
        out.append('          <p class="eyebrow">%s</p>' % e(sec['eyebrow']))
    out.append('          <h2>%s</h2>' % e(sec['title']))
    if sec.get('lead'):
        lead = sec['lead']
        ll = sec.get('leadLink')
        body = link_phrase(lead, ll['phrase'], ll['href']) if ll else e(lead)
        out.append('          <p>%s</p>' % body)
    out.append('        </div>')
    return '\n'.join(out)


def section(sec, inner, extra_class=''):
    """Wrap rendered inner markup in this site's section shell."""
    cls = 'section'
    # The source's own modifier names do not exist here; alternate shading
    # with the one modifier this stylesheet defines.
    if sec.get('className') in ('section--light', 'section--accent', 'section--alt'):
        cls += ' section--alt'
    if extra_class:
        cls += ' ' + extra_class
    sid = ' id="%s"' % sec['id'] if sec.get('id') else ''
    return ('    <section class="%s"%s>\n      <div class="container">\n%s\n'
            '      </div>\n    </section>' % (cls, sid, inner))


# --------------------------------------------------------------------------
# section renderers, one per source type
# --------------------------------------------------------------------------

def render_cards(sec):
    cards = []
    for item in sec['items']:
        cards.append('          <article class="topic-card">\n'
                     '            <h3>%s</h3>\n'
                     '            <p>%s</p>\n'
                     '          </article>' % (e(item['title']), e(item['text'])))
    inner = '%s\n\n        <div class="topic-grid">\n%s\n        </div>%s' % (
        heading(sec), '\n'.join(cards), actions(sec.get('actions')))
    return section(sec, inner)


def render_steps(sec):
    cards = []
    for n, item in enumerate(sec['items'], 1):
        cards.append('          <article class="process-card">\n'
                     '            <span class="timeline-step">%d</span>\n'
                     '            <h3>%s</h3>\n'
                     '            <p>%s</p>\n'
                     '          </article>' % (n, e(item['title']), e(item['text'])))
    inner = '%s\n\n        <div class="process-grid">\n%s\n        </div>%s' % (
        heading(sec), '\n'.join(cards), actions(sec.get('actions')))
    return section(sec, inner, 'process-section')


def render_routes(sec):
    cards = []
    for item in sec['items']:
        roads = ''.join('<li>%s</li>' % e(r) for r in item.get('roads', []))
        cards.append(
            '          <article class="route-card">\n'
            '            <p class="eyebrow">%s</p>\n'
            '            <h3>%s</h3>\n'
            '            <p>%s</p>\n'
            '            <ul class="area-list">%s</ul>\n'
            '            <p class="card-meta">%s &middot; %s &middot; %s</p>\n'
            '          </article>'
            % (e(item.get('area', '')), e(item['name']), e(item['text']), roads,
               e(item.get('level', '')), e(item.get('distance', '')),
               e(item.get('minutes', ''))))
    note = ('\n        <p class="section-note">%s</p>' % e(sec['note'])) if sec.get('note') else ''
    inner = '%s\n\n        <div class="route-grid">\n%s\n        </div>%s%s' % (
        heading(sec), '\n'.join(cards), note, actions(sec.get('actions')))
    return section(sec, inner)


def render_split(sec):
    paras = '\n'.join('            <p>%s</p>' % e(p) for p in sec.get('paragraphs', []))
    aside = ''
    if sec.get('asideTitle'):
        aside = ('\n            <div class="authority-panel">\n'
                 '              <h3>%s</h3>\n'
                 '              <p>%s</p>\n'
                 '            </div>'
                 % (e(sec['asideTitle']), e(sec.get('asideText', ''))))
    acts = actions(sec.get('actions'), indent=12).replace(
        ' section-actions--center', '')
    media = ''
    if sec.get('image'):
        media = ('\n        <figure class="page-shell-media">\n          %s\n        </figure>'
                 % img(sec['image']))
    inner = ('%s\n\n        <div class="page-shell-grid">\n'
             '          <div class="page-shell-copy">\n%s%s%s\n          </div>%s\n'
             '        </div>' % (heading(sec), paras, aside, acts, media))
    return section(sec, inner)


def render_prose(sec):
    blocks = []
    for block in sec.get('blocks', []):
        part = ['          <div class="about-copy">']
        if block.get('heading'):
            part.append('            <h3>%s</h3>' % e(block['heading']))
        for p in block.get('paragraphs', []):
            part.append('            <p>%s</p>' % e(p))
        if block.get('items'):
            part.append('            <ul class="about-points">')
            for it in block['items']:
                part.append('              <li>%s</li>' % e(it))
            part.append('            </ul>')
        part.append('          </div>')
        blocks.append('\n'.join(part))
    inner = '%s\n\n%s%s' % (heading(sec), '\n'.join(blocks), actions(sec.get('actions')))
    return section(sec, inner)


def render_checklist(sec):
    paras = '\n'.join('            <p>%s</p>' % e(p) for p in sec.get('paragraphs', []))
    items = '\n'.join('              <li>%s</li>' % e(i) for i in sec.get('asideItems', []))
    aside = ''
    if items:
        aside = ('\n          <div class="trust-panel">\n'
                 '            <h3>%s</h3>\n'
                 '            <ul class="trust-list">\n%s\n            </ul>\n'
                 '          </div>' % (e(sec.get('asideTitle', 'Checklist')), items))
    inner = ('%s\n\n        <div class="trust-layout">\n'
             '          <div class="about-copy">\n%s\n          </div>%s\n'
             '        </div>%s' % (heading(sec), paras, aside, actions(sec.get('actions'))))
    return section(sec, inner)


def render_notice(sec):
    items = '\n'.join('              <li>%s</li>' % e(i) for i in sec.get('asideItems', []))
    aside = ''
    if items:
        aside = ('\n          <div class="trust-panel">\n'
                 '            <h3>%s</h3>\n'
                 '            <ul class="trust-list">\n%s\n            </ul>\n'
                 '          </div>' % (e(sec.get('asideTitle', 'The detail')), items))
    paras = '\n'.join('            <p>%s</p>' % e(p) for p in sec.get('paragraphs', []))
    body = ('\n          <div class="about-copy">\n%s\n          </div>' % paras) if paras else ''
    inner = ('%s\n\n        <div class="trust-layout">%s%s\n        </div>%s'
             % (heading(sec), body, aside, actions(sec.get('actions'))))
    return section(sec, inner)


def render_table(sec):
    head = ''.join('<th scope="col">%s</th>' % e(c) for c in sec['columns'])
    rows = []
    for row in sec['rows']:
        cells = ''.join('<td>%s</td>' % e(c) for c in row)
        rows.append('              <tr>%s</tr>' % cells)
    aside = ''
    if sec.get('asideTitle'):
        aside = ('\n        <div class="authority-panel">\n'
                 '          <h3>%s</h3>\n          <p>%s</p>\n        </div>'
                 % (e(sec['asideTitle']), e(sec.get('asideText', ''))))
    inner = ('%s\n\n        <div class="table-wrap">\n'
             '          <table class="info-table">\n'
             '            <thead><tr>%s</tr></thead>\n'
             '            <tbody>\n%s\n            </tbody>\n'
             '          </table>\n        </div>%s%s'
             % (heading(sec), head, '\n'.join(rows), aside, actions(sec.get('actions'))))
    return section(sec, inner)


def render_accreditations(sec):
    cards = []
    for item in sec.get('items', []):
        cards.append('          <article class="accreditation-card">\n'
                     '            <h3>%s</h3>\n'
                     '            <p>%s</p>\n'
                     '          </article>' % (e(item['title']), e(item.get('text', ''))))
    inner = '%s\n\n        <div class="accreditation-grid">\n%s\n        </div>%s' % (
        heading(sec), '\n'.join(cards), actions(sec.get('actions')))
    return section(sec, inner, 'accreditation-section')


def render_logos(sec):
    cards = []
    for item in sec.get('items', []):
        url = href(item.get('href'))
        title = e(item['title'])
        if url:
            title = '<a href="%s">%s</a>' % (attr(url), title)
        cards.append('          <article class="accreditation-card">\n'
                     '            <h3>%s</h3>\n'
                     '            <p>%s</p>\n'
                     '          </article>' % (title, e(item.get('text', ''))))
    inner = '%s\n\n        <div class="accreditation-grid">\n%s\n        </div>%s' % (
        heading(sec), '\n'.join(cards), actions(sec.get('actions')))
    return section(sec, inner)


def render_pricing(sec):
    # The seven published packages live in one partial, so the page pulls it in.
    return '{{> partials/pricing.html }}'


def render_elfsight(sec):
    # A third-party review widget with no counterpart here, and the brief rules
    # out external links, so the section is dropped rather than faked.
    return ''


def render_suburbs(sec, hub, own_slug=None):
    groups = []
    for group in hub:
        cards = []
        for sub in group['suburbs']:
            url = href(sub['href'])
            slug = sub['href'].strip('/')
            if slug == own_slug:
                continue
            title = e(sub['title'])
            if url:
                title = '<a href="%s">%s</a>' % (attr(url), title)
            cards.append('            <article class="service-area-card">\n'
                         '              <h3>%s</h3>\n'
                         '              <p>%s</p>\n'
                         '            </article>' % (title, e(sub['text'])))
        summary = group['summary'].replace('{count}', str(len(cards)))
        groups.append(
            '        <div class="section-heading">\n'
            '          <p class="eyebrow">%s</p>\n'
            '          <h2>%s</h2>\n'
            '          <p>%s</p>\n'
            '        </div>\n\n'
            '        <details class="suburb-dropdown">\n'
            '          <summary>%s</summary>\n'
            '          <div class="service-area-grid">\n%s\n          </div>\n'
            '        </details>'
            % (e(group['eyebrow']), e(group['title']), e(group['lead']),
               e(summary), '\n'.join(cards)))
    body = '\n\n'.join(groups)
    return ('    <section class="section section--alt" id="service-areas">\n'
            '      <div class="container">\n%s\n      </div>\n    </section>' % body)


RENDERERS = {
    'cards': render_cards, 'steps': render_steps, 'routes': render_routes,
    'split': render_split, 'prose': render_prose, 'checklist': render_checklist,
    'notice': render_notice, 'table': render_table, 'logos': render_logos,
    'accreditations': render_accreditations, 'pricing': render_pricing,
    'elfsight': render_elfsight,
}


SERVICES_PARTIAL = os.path.join(ROOT, 'templates', 'partials', 'services-hub.html')
RE_SERVICE_CARD = re.compile(
    r'[ \t]*<article class="service-area-card">.*?</article>\n', re.S)


def render_services_hub(own_slug=None):
    """The twelve lesson-type pages, as one grid on every generated page.

    Suburb pages take the partial by reference so the build resolves it. A
    service page cannot, because it has to drop its own card rather than link
    to itself, so it inlines the same partial with that one card removed.
    There is still only one list: this file.
    """
    if own_slug is None:
        return '{{> partials/services-hub.html }}'
    body = read_text(SERVICES_PARTIAL).rstrip('\n')
    needle = 'href="/%s/"' % own_slug
    kept = RE_SERVICE_CARD.sub(
        lambda m: '' if needle in m.group(0) else m.group(0), body)
    if kept == body:
        die('services hub has no card for %s; add one to the partial' % own_slug)
    return kept


def render_faq(items, title, lead):
    """Match the accordion markup js/main.js already drives on every page."""
    blocks = []
    for item in items:
        blocks.append('          <article class="faq-item">\n'
                      '            <button type="button" aria-expanded="false">\n'
                      '              <span>%s</span>\n'
                      '            </button>\n'
                      '            <div class="faq-panel" hidden>\n'
                      '              <p>%s</p>\n'
                      '            </div>\n'
                      '          </article>'
                      % (e(item['question']), e(item['answer'])))
    lead_html = ('\n          <p>%s</p>' % e(lead)) if lead else ''
    return ('    <section class="section faq-section" id="faq">\n'
            '      <div class="container">\n'
            '        <div class="section-heading section-heading--center">\n'
            '          <p class="eyebrow">Questions</p>\n'
            '          <h2>%s</h2>%s\n'
            '        </div>\n\n'
            '        <div class="faq-list">\n%s\n        </div>\n'
            '      </div>\n    </section>' % (e(title), lead_html, '\n'.join(blocks)))


def render_closing(closing):
    url = href(closing.get('actionHref') or '#enquiry-form') or '#enquiry-form'
    return ('    <section class="section final-cta" id="final-cta">\n'
            '      <div class="container">\n'
            '        <div class="final-cta__panel">\n'
            '          <div class="final-cta__content">\n'
            '            <p class="eyebrow eyebrow--light">%s</p>\n'
            '            <h2>%s</h2>\n'
            '            <p>%s</p>\n'
            '            <div class="hero__actions">\n'
            '              <a class="btn btn--primary" href="%s">%s</a>\n'
            '              <a class="btn btn--ghost-light" href="{{ phone_href }}">'
            'Call {{ phone_display }}</a>\n'
            '            </div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </div>\n    </section>'
            % (e(closing.get('eyebrow', 'Book a lesson')), e(closing['title']),
               e(closing['text']), attr(url),
               e(closing.get('actionLabel', 'Book a lesson'))))


def render_hero(hero, images, extra_actions=True):
    media = ''
    if images and images.get('hero'):
        media = ('\n\n        <figure class="page-hero__media">\n          %s\n        </figure>'
                 % img(images['hero'], lazy=False))
    return ('    <section class="page-hero page-hero--wide">\n'
            '      <div class="container page-hero__layout">\n'
            '        <div class="page-hero__content">\n'
            '          <p class="page-hero__eyebrow">%s</p>\n'
            '          <h1>%s</h1>\n'
            '          <p class="page-hero__lead">%s</p>\n'
            '          <div class="hero__actions">\n'
            '            <a class="btn btn--primary" href="#enquiry-form">Book a lesson</a>\n'
            '            <a class="btn btn--ghost" href="{{ phone_href }}">'
            'Call {{ phone_display }}</a>\n'
            '          </div>\n'
            '        </div>%s\n'
            '      </div>\n    </section>'
            % (e(hero.get('eyebrow', '')), e(hero['title']), e(hero['lead']), media))


# --------------------------------------------------------------------------
# page builders
# --------------------------------------------------------------------------

def json_ld(data, slug, kind, faq):
    """Breadcrumb plus the page's own type, and the FAQ if the page has one."""
    site = 'https://drivingschoolliverpool.sydney'
    graph = [{
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': site + '/'},
            {'@type': 'ListItem', 'position': 2,
             'name': rebrand(data['seo']['title'].split('|')[0].strip()),
             'item': '%s/%s/' % (site, slug)},
        ],
    }]
    if kind == 'suburb':
        graph.append({
            '@type': 'DrivingSchool', 'name': BUSINESS,
            'areaServed': data['identity']['suburb'] + ' NSW',
            'telephone': '+61287761815', 'priceRange': '$80-$770',
            'url': '%s/%s/' % (site, slug),
        })
    else:
        graph.append({
            '@type': 'Service', 'name': rebrand(data['hero']['title']),
            'provider': {'@type': 'DrivingSchool', 'name': BUSINESS,
                         'telephone': '+61287761815'},
            'areaServed': 'Liverpool NSW and South West Sydney',
            'url': '%s/%s/' % (site, slug),
        })
    if faq:
        graph.append({
            '@type': 'FAQPage',
            'mainEntity': [
                {'@type': 'Question', 'name': rebrand(f['question']),
                 'acceptedAnswer': {'@type': 'Answer', 'text': rebrand(f['answer'])}}
                for f in faq],
        })
    doc = {'@context': 'https://schema.org', '@graph': graph}
    body = json.dumps(doc, indent=2, ensure_ascii=False)
    body = '\n'.join('  ' + l for l in body.split('\n'))
    return ('<!-- BLOCK: json_ld -->\n  <script type="application/ld+json">\n'
            '%s\n  </script>\n<!-- ENDBLOCK -->' % body)



# Paragraph text, with the tags kept so injection can skip anything already
# inside a link.
RE_PARA = re.compile(r'<p>(.*?)</p>', re.S)
PLACED = []


def inject_links(body, slug, plan):
    """Link supporting pages to the primary commercial pages.

    The anchor is the first phrase from the placement's preference list that
    appears in ordinary paragraph copy on this page, so the link reads as part
    of the sentence instead of an appended call to action. Text already inside
    an <a>, and any paragraph in the FAQ answers, is left alone.
    """
    for item in plan.get('placements', []):
        if item['source'] != slug:
            continue
        target = item['target']
        if target.strip('/') == slug:
            continue
        # A call-to-action button pointing at the target does not count: those
        # live in .section-actions, never in a paragraph, and a link inside the
        # sentence carries the anchor text signal a button label does not.
        if re.search(r'<p>[^<]*<a href="%s"' % re.escape(target), body):
            PLACED.append((slug, target, '(already linked in copy)'))
            continue
        # Anchor preference beats document order: try the most specific phrase
        # across the whole page before falling back to a broader one, so a
        # suburb page links on its own test centre rather than on the generic
        # wording that happens to appear in an earlier paragraph.
        done = [False]

        for anchor in item['anchors']:
            def wrap(match, target=target, anchor=anchor, done=done):
                inner = match.group(1)
                if done[0] or '<a ' in inner:
                    return match.group(0)
                pos = inner.lower().find(anchor.lower())
                if pos < 0:
                    return match.group(0)
                found = inner[pos:pos + len(anchor)]
                done[0] = True
                PLACED.append((slug, target, found))
                return '<p>%s<a href="%s">%s</a>%s</p>' % (
                    inner[:pos], target, found, inner[pos + len(anchor):])

            body = RE_PARA.sub(wrap, body)
            if done[0]:
                break
        if not done[0]:
            PLACED.append((slug, target, None))
    return body


def front_matter(pairs):
    lines = ['---']
    for key, value in pairs:
        if value is None:
            continue
        lines.append('%s: %s' % (key, ' '.join(str(value).split())))
    lines.append('---')
    return '\n'.join(lines)


def build_suburb(data, hub, plan):
    slug = data['slug']
    ident = data['identity']
    images = data.get('images', {})
    body = [render_hero(data['hero'], images)]

    intro_link = data.get('introLink')
    intro = (link_phrase(data['intro'], intro_link['phrase'], intro_link['href'])
             if intro_link else e(data['intro']))
    prep_link = data.get('testPreparationLink')
    prep = (link_phrase(data['testPreparation'], prep_link['phrase'], prep_link['href'])
            if prep_link else e(data['testPreparation']))
    centre = ident.get('testCentre', {})
    body.append(
        '    <section class="section" id="local-roads">\n'
        '      <div class="container page-shell-grid">\n'
        '        <div class="page-shell-copy">\n'
        '          <p class="eyebrow">Driving lessons in %s</p>\n'
        '          <h2>Learning to drive on %s roads</h2>\n'
        '          <p>%s</p>\n'
        '          <h3>Preparing for the %s test</h3>\n'
        '          <p>%s</p>\n'
        '        </div>\n'
        '        <figure class="page-shell-media">\n          %s\n        </figure>\n'
        '      </div>\n    </section>'
        % (e(ident['suburb']), e(ident['suburb']), intro,
           e(centre.get('name', 'Service NSW')), prep,
           img(images['heroSecondary']) if images.get('heroSecondary') else ''))

    steps = []
    for n, step in enumerate(data['progression'], 1):
        steps.append('          <article class="process-card">\n'
                     '            <span class="timeline-step">%d</span>\n'
                     '            <h3>%s</h3>\n'
                     '            <p>%s</p>\n'
                     '            <p class="card-meta">%s</p>\n'
                     '          </article>'
                     % (n, e(step['title']), e(step['focus']), e(step.get('location', ''))))
    body.append(
        '    <section class="section section--alt process-section" id="lesson-plan">\n'
        '      <div class="container">\n'
        '        <div class="section-heading section-heading--center">\n'
        '          <p class="eyebrow">How the lessons build</p>\n'
        '          <h2>Your %s lesson plan, session by session</h2>\n'
        '        </div>\n\n'
        '        <div class="process-grid">\n%s\n        </div>\n'
        '      </div>\n    </section>'
        % (e(ident['suburb']), '\n'.join(steps)))

    if data.get('maneuvers'):
        cards = []
        for m in data['maneuvers']:
            cards.append('          <article class="route-card">\n'
                         '            <h3>%s</h3>\n'
                         '            <p>%s</p>\n'
                         '            <p class="card-meta">%s</p>\n'
                         '          </article>'
                         % (e(m['skill']), e(m['reason']), e(m['roads'])))
        body.append(
            '    <section class="section" id="skills">\n'
            '      <div class="container">\n'
            '        <div class="section-heading section-heading--center">\n'
            '          <p class="eyebrow">Skills and the roads that teach them</p>\n'
            '          <h2>Where each %s skill is practised</h2>\n'
            '        </div>\n\n'
            '        <div class="route-grid">\n%s\n        </div>\n'
            '      </div>\n    </section>' % (e(ident['suburb']), '\n'.join(cards)))

    if data.get('map'):
        m = data['map']
        body.append(
            '    <section class="section section--alt" id="map">\n'
            '      <div class="container">\n'
            '        <div class="section-heading section-heading--center">\n'
            '          <h2>%s</h2>\n          <p>%s</p>\n        </div>\n\n'
            '        <div class="service-map">\n'
            '          <iframe src="%s" title="%s" width="100%%" height="420"\n'
            '            style="border:0" loading="lazy"'
            ' referrerpolicy="no-referrer-when-downgrade"></iframe>\n'
            '        </div>\n'
            '      </div>\n    </section>'
            % (e(m['title']), e(m['lead']), attr(m['embed']), attr(m['title'])))

    body.append(render_suburbs({}, hub, own_slug=slug))
    body.append(render_services_hub())
    body.append('{{> partials/pricing.html }}')
    body.append(render_faq(data['faq'],
                           'Driving lessons in %s: your questions' % ident['suburb'],
                           data.get('communityLead')))
    body.append('{{> partials/enquiry-form.html }}')

    nav = ('Local roads|#local-roads, Lesson plan|#lesson-plan, '
           'Suburbs|#service-areas, Packages|#packages, FAQ|#faq, Enquiry|#enquiry-form')
    fm = front_matter([
        ('slug', slug),
        ('title', rebrand(data['seo']['title'])),
        ('description', rebrand(data['seo']['description'])),
        ('og_title', 'Driving Lessons in %s' % ident['suburb']),
        ('og_description', rebrand(data['seo']['description'])),
        ('nav', nav),
        ('packages_heading', 'Driving lesson packages for %s learners.' % ident['suburb']),
        ('packages_lead', 'The same published prices apply across every suburb '
                          'the Liverpool branch covers.'),
    ])
    rendered = inject_links('\n\n'.join(b for b in body if b), slug, plan)
    return '%s\n\n%s\n\n%s\n' % (fm, json_ld(data, slug, 'suburb', data['faq']),
                                 rendered)


def build_service(data, hub, plan):
    slug = data['slug']
    body = [render_hero(data['hero'], None)]
    used_pricing = False
    for sec in data['sections']:
        kind = sec['type']
        if kind == 'suburbs':
            body.append(render_suburbs(sec, hub))
            continue
        if kind not in RENDERERS:
            die('no renderer for section type %r on %s' % (kind, slug))
        if kind == 'pricing':
            used_pricing = True
        body.append(RENDERERS[kind](sec))
    body.append(render_services_hub(own_slug=slug))
    body.append(render_faq(data['faq'], data['faqTitle'], data.get('faqLead')))
    body.append(render_closing(data['closing']))
    body.append('{{> partials/enquiry-form.html }}')

    nav_items = []
    for sec in data['sections'][:4]:
        if sec.get('id') and sec.get('eyebrow'):
            # A comma would split the nav spec and a pipe would split the item.
            # Nav has room for a couple of words, so drop the leading filler
            # and cut on a word boundary rather than shipping an ellipsis.
            label = sec['eyebrow'].split(',')[0].replace('|', ' ').strip()
            label = re.sub(r'^(what|where|when|how|why|your|the)\s+', '',
                           label, flags=re.I)
            if len(label) > 20:
                label = label[:20].rsplit(' ', 1)[0]
            nav_items.append('%s|#%s' % (label[:1].upper() + label[1:], sec['id']))
    nav_items += ['FAQ|#faq', 'Enquiry|#enquiry-form']

    pairs = [
        ('slug', slug),
        ('title', rebrand(data['seo']['title'])),
        ('description', rebrand(data['seo']['description'])),
        ('og_title', rebrand(data['hero']['title'])),
        ('og_description', rebrand(data['seo']['description'])),
        ('nav', ', '.join(nav_items)),
    ]
    if used_pricing:
        pairs += [('packages_heading', 'Lesson packages for this service.'),
                  ('packages_lead', 'The same published prices apply to every '
                                    'lesson the Liverpool branch teaches.')]
    fm = front_matter(pairs)
    rendered = inject_links('\n\n'.join(b for b in body if b), slug, plan)
    return '%s\n\n%s\n\n%s\n' % (fm, json_ld(data, slug, 'service', data['faq']),
                                 rendered)


def main():
    args = sys.argv[1:]
    listing = '--list' in args
    names = [a for a in args if not a.startswith('--')]

    if not os.path.isdir(SOURCE):
        die('source content not found at %s (set IMPORT_SOURCE)' % SOURCE)
    if not os.path.exists(HUB):
        die('missing %s' % HUB)
    hub = json.loads(read_text(HUB))
    plan = json.loads(read_text(LINKS)) if os.path.exists(LINKS) else {}

    files = (sorted(glob.glob(os.path.join(SOURCE, 'content', 'suburbs', '*.json')))
             + sorted(glob.glob(os.path.join(SOURCE, 'content', 'services', '*.json'))))
    if names:
        files = [f for f in files if any(n in os.path.basename(f) for n in names)]
    if not files:
        die('no source content matched')

    for f in files:
        SLUGS_BUILT.add(os.path.splitext(os.path.basename(f))[0])

    written = 0
    for f in files:
        data = json.loads(read_text(f))
        out = os.path.join(PAGES, data['slug'] + '.html')
        page = build_suburb(data, hub, plan) if data['type'] == 'suburb' \
            else build_service(data, hub, plan)
        if listing:
            print('%-52s %6d bytes' % (data['slug'], len(page)))
            continue
        io.open(out, 'w', encoding='utf-8', newline='\n').write(page)
        written += 1
        print('wrote templates/pages/%s.html' % data['slug'])
    report_links()
    if written:
        print('\n%d page sources written. Now run: python tools/build-pages.py' % written)


def read_text(path):
    return io.open(path, encoding='utf-8').read()


def report_links():
    """Print what the link plan actually placed, including anything it could not."""
    if not PLACED:
        return
    missed = [p for p in PLACED if p[2] is None]
    print('')
    print('internal links placed: %d of %d' % (len(PLACED) - len(missed), len(PLACED)))
    for slug, target, found in PLACED:
        print('  %-38s -> %-42s %s'
              % (slug, target, found if found else 'NO ANCHOR PHRASE FOUND'))


if __name__ == '__main__':
    main()
