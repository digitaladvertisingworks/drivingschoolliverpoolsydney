#!/usr/bin/env python3
"""
Crawl the built site and report its internal link graph.

    python tools/link-audit.py            # full report
    python tools/link-audit.py --json     # machine-readable

Every page ships the same header and footer, so a raw inbound count says
almost nothing: it mostly counts boilerplate. This splits each link by the
region it sits in, and treats only links inside <main> as contextual, which
is the signal an entity-based linking review actually cares about.

Reported numbers are measured from the HTML in this repo. Nothing here knows
about traffic, impressions or rankings, so no metric that depends on those is
produced.
"""
import io
import os
import re
import sys
import json
import glob
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RE_A = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S | re.I)
RE_HREF = re.compile(r'href="([^"]*)"', re.I)
RE_TAG = re.compile(r'<[^>]+>')
RE_WS = re.compile(r'\s+')

# Structure score deductions, from the internal-linking-optimizer methodology.
ORPHAN_PENALTY = 10
DEPTH_PENALTY = 5
NO_CONTEXTUAL_PENALTY = 5
DENSITY_PENALTY = 10
DEPTH_LIMIT = 3
DENSITY_RANGE = (20, 150)


def read(path):
    return io.open(path, encoding='utf-8').read()


def pages():
    out = {}
    for path in ['index.html'] + sorted(glob.glob(os.path.join(ROOT, '*', 'index.html'))):
        full = path if os.path.isabs(path) else os.path.join(ROOT, path)
        d = os.path.relpath(os.path.dirname(full), ROOT).replace(os.sep, '/')
        url = '/' if d == '.' else '/%s/' % d
        out[url] = full
    return out


def regions(html):
    """Split a page into header, main and footer so links can be attributed."""
    body = html[html.index('<body'):]
    out = {}
    for name, pat in (('header', r'<header\b.*?</header>'),
                      ('footer', r'<footer\b.*?</footer>')):
        m = re.search(pat, body, re.S | re.I)
        out[name] = m.group(0) if m else ''
        if m:
            body = body[:m.start()] + body[m.end():]
    out['main'] = body
    return out


def normalise(href, source):
    """Resolve an href to a site path, or None if it is not an internal page."""
    href = href.strip()
    if not href or href.startswith(('http://', 'https://', 'tel:', 'mailto:', '#',
                                    'javascript:', 'data:')):
        return None
    path = href.split('#')[0].split('?')[0]
    if not path:
        return None
    if path.startswith('/'):
        target = path
    else:
        base = source.rstrip('/') or ''
        parts = [p for p in base.split('/') if p]
        for seg in path.split('/'):
            if seg in ('', '.'):
                continue
            if seg == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(seg)
        target = '/' + '/'.join(parts)
        if path.endswith('/') and not target.endswith('/'):
            target += '/'
    if re.search(r'\.(png|jpe?g|webp|svg|ico|css|js|xml|txt|pdf|woff2?)$', target, re.I):
        return None
    if target != '/' and not target.endswith('/'):
        target += '/'
    return target


def crawl():
    page_map = pages()
    known = set(page_map)
    edges = []          # (source, target, region, anchor)
    for url, path in sorted(page_map.items()):
        html = read(path)
        for region, markup in regions(html).items():
            for attrs, inner in RE_A.findall(markup):
                m = RE_HREF.search(attrs)
                if not m:
                    continue
                target = normalise(m.group(1), url)
                if target is None or target not in known or target == url:
                    continue
                anchor = RE_WS.sub(' ', RE_TAG.sub(' ', inner)).strip()
                edges.append((url, target, region, anchor))
    return known, edges


def depths(known, edges):
    """Click depth from the home page, following links in any region."""
    adj = collections.defaultdict(set)
    for s, t, _, _ in edges:
        adj[s].add(t)
    seen = {'/': 0}
    frontier = ['/']
    while frontier:
        nxt = []
        for node in frontier:
            for child in adj[node]:
                if child not in seen:
                    seen[child] = seen[node] + 1
                    nxt.append(child)
        frontier = nxt
    return dict((u, seen.get(u)) for u in known)


def pagerank(known, edges, damping=0.85, rounds=60):
    """Internal PageRank over contextual + navigational links."""
    out = collections.defaultdict(set)
    for s, t, _, _ in edges:
        out[s].add(t)
    n = len(known)
    rank = dict((u, 1.0 / n) for u in known)
    for _ in range(rounds):
        nxt = dict((u, (1 - damping) / n) for u in known)
        sink = 0.0
        for u in known:
            targets = out.get(u)
            if not targets:
                sink += rank[u]
                continue
            share = damping * rank[u] / len(targets)
            for t in targets:
                nxt[t] += share
        if sink:
            for u in known:
                nxt[u] += damping * sink / n
        rank = nxt
    total = sum(rank.values()) or 1.0
    return dict((u, v / total) for u, v in rank.items())


def build_report():
    known, edges = crawl()
    depth = depths(known, edges)
    rank = pagerank(known, edges)

    inbound = collections.Counter()
    inbound_ctx = collections.Counter()
    outbound = collections.Counter()
    outbound_ctx = collections.Counter()
    ctx_sources = collections.defaultdict(set)
    anchors = collections.defaultdict(collections.Counter)
    by_region = collections.Counter()

    for s, t, region, anchor in edges:
        inbound[t] += 1
        outbound[s] += 1
        by_region[region] += 1
        if region == 'main':
            inbound_ctx[t] += 1
            outbound_ctx[s] += 1
            ctx_sources[t].add(s)
            anchors[t][anchor.lower()] += 1

    orphans = sorted(u for u in known if inbound[u] == 0 and u != '/')
    no_ctx = sorted(u for u in known if inbound_ctx[u] == 0 and u != '/')
    deep = sorted(u for u in known if depth.get(u) is None or depth[u] > DEPTH_LIMIT)
    avg_links = sum(outbound.values()) / float(len(known))

    score = 100
    score -= ORPHAN_PENALTY * len(orphans)
    score -= DEPTH_PENALTY * len(deep)
    score -= NO_CONTEXTUAL_PENALTY * len(no_ctx)
    if not (DENSITY_RANGE[0] <= avg_links <= DENSITY_RANGE[1]):
        score -= DENSITY_PENALTY
    score = max(0, score)

    return {
        'pages': len(known),
        'edges': len(edges),
        'by_region': dict(by_region),
        'avg_links_per_page': round(avg_links, 1),
        'avg_contextual_out': round(sum(outbound_ctx.values()) / float(len(known)), 1),
        'structure_score': score,
        'orphans': orphans,
        'no_contextual_inbound': no_ctx,
        'deeper_than_limit': deep,
        'inbound': dict(inbound),
        'inbound_contextual': dict(inbound_ctx),
        'outbound_contextual': dict(outbound_ctx),
        'contextual_sources': dict((k, sorted(v)) for k, v in ctx_sources.items()),
        'anchors': dict((k, dict(v)) for k, v in anchors.items()),
        'pagerank': rank,
        'depth': depth,
    }


def main():
    r = build_report()
    if '--json' in sys.argv:
        print(json.dumps(r, indent=1, sort_keys=True))
        return

    print('PHASE 1  CURRENT STRUCTURE            (all figures measured from the repo)')
    print('  pages crawled              %d' % r['pages'])
    print('  internal links             %d' % r['edges'])
    print('  links by region            %s' % r['by_region'])
    print('  average links per page     %.1f' % r['avg_links_per_page'])
    print('  average CONTEXTUAL out     %.1f' % r['avg_contextual_out'])
    print('  structure score            %d / 100' % r['structure_score'])
    print()
    print('PHASE 2  ORPHANS AND THIN PAGES')
    print('  zero inbound of any kind   %d' % len(r['orphans']))
    for u in r['orphans']:
        print('      %s' % u)
    print('  zero CONTEXTUAL inbound    %d' % len(r['no_contextual_inbound']))
    for u in r['no_contextual_inbound']:
        print('      %s' % u)
    print('  deeper than %d clicks       %d' % (DEPTH_LIMIT, len(r['deeper_than_limit'])))
    for u in r['deeper_than_limit']:
        print('      %s (depth %s)' % (u, r['depth'].get(u)))
    print()
    print('PHASE 3  CONTEXTUAL INBOUND, WEAKEST FIRST')
    rows = sorted(r['inbound_contextual'].items(), key=lambda kv: kv[1])
    for u, n in rows[:18]:
        print('  %-46s %3d contextual   pagerank %.4f' % (u, n, r['pagerank'][u]))
    print()
    print('  strongest by internal pagerank')
    for u, v in sorted(r['pagerank'].items(), key=lambda kv: -kv[1])[:8]:
        print('  %-46s pagerank %.4f  ctx-in %d'
              % (u, v, r['inbound_contextual'].get(u, 0)))


if __name__ == '__main__':
    main()
