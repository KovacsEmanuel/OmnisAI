"""Offline documentation/prototype checks using optional local Playwright.

Not a test of the Omnis application or of target confinement. No network allowed.
Run: python tests/documentation/browser_check.py --output <scratch-report.json>
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"
VIEWS = ["engagements", "overview", "map", "investigations", "findings", "reports", "setup", "providers", "skills", "runtime"]


def assert_overlay_stop(page, overlay):
    stop = page.locator(overlay).get_by_role('button', name='Stop demo', exact=True)
    assert stop.count() == 1, f'{overlay} must contain an equivalent Stop demo action'
    assert stop.is_visible() and stop.is_enabled(), 'overlay Stop must be available without closing it first'
    stop.focus()
    page.keyboard.press('Enter')
    assert 'STOPPING' in page.locator('#run-state').inner_text(), 'Stop must be immediate, without confirmation'
    assert page.locator('dialog[open], #sidebar.open').count() == 0
    assert not page.locator('.maincol').evaluate('e=>e.inert')
    expect(page.locator('#complete-stop')).to_be_focused()


def check_drawer_stop(page):
    page.set_viewport_size({'width': 390, 'height': 1000})
    page.locator('#open-menu').click()
    assert page.locator('.maincol').evaluate('e=>e.inert')
    assert_overlay_stop(page, '#sidebar')


def check_approval_stop(page):
    page.evaluate("showView('overview', false)")
    page.locator('#approval-open').click()
    expect(page.locator('[data-close="approval-dialog"]')).to_be_focused()
    assert_overlay_stop(page, '#approval-dialog')


def check_preflight_stop(page):
    # Exercise the native-modal seam while an active run still exists.
    page.evaluate("openDialog('start-dialog')")
    expect(page.locator('[data-close="start-dialog"]')).to_be_focused()
    assert_overlay_stop(page, '#start-dialog')


def assert_valid_focus(page):
    assert page.evaluate("""() => {
        const e = document.activeElement;
        return e !== document.body && e.checkVisibility() && !e.closest('[inert]') && !e.disabled;
    }"""), 'focus must remain on a visible, enabled, non-inert target'


def check_drawer_resize(page):
    page.set_viewport_size({'width': 390, 'height': 1000})
    page.locator('#open-menu').click()
    expect(page.locator('#close-menu')).to_be_focused()
    page.set_viewport_size({'width': 1440, 'height': 1000})
    expect(page.locator('#open-menu')).to_have_attribute('aria-expanded', 'false')
    assert not page.locator('.maincol').evaluate('e=>e.inert')
    assert page.locator('#sidebar').get_attribute('role') is None
    assert page.locator('#sidebar').get_attribute('aria-modal') is None
    assert_valid_focus(page)
    page.locator('#stop-control').click()
    assert 'STOPPING' in page.locator('#run-state').inner_text()
    page.set_viewport_size({'width': 390, 'height': 1000})
    assert not page.locator('#sidebar').is_visible(), 'drawer must stay closed on return to mobile'
    page.locator('#open-menu').click()
    page.keyboard.press('Escape')
    expect(page.locator('#open-menu')).to_be_focused()


def check_stopped_focus(page):
    page.locator('#stop-control').click()
    page.locator('#complete-stop').click()
    assert 'STOPPED' in page.locator('#run-state').inner_text()
    expect(page.locator('#start-control')).to_be_focused()
    assert_valid_focus(page)


def check_started_focus(page):
    page.locator('#stop-control').click()
    page.locator('#complete-stop').click()
    page.locator('#start-control').click()
    page.locator('#start-demo').click()
    assert 'RUNNING' in page.locator('#run-state').inner_text()
    expect(page.locator('#pause-control')).to_be_focused()
    assert_valid_focus(page)
    page.keyboard.press('Tab')
    expect(page.locator('#stop-control')).to_be_focused()


def check_run_state_live_region(page):
    state = page.locator('#run-state')
    assert state.get_attribute('role') == 'status', 'run state needs a live status region'
    assert state.get_attribute('aria-live') == 'polite'
    assert state.get_attribute('aria-atomic') == 'true'
    page.locator('#stop-control').click()
    expect(state).to_have_text('STOPPING · demo')
    page.locator('#complete-stop').click()
    expect(state).to_have_text('STOPPED · demo')


def check_anonymous_context(page):
    page.locator('[data-map="coverage"]').click()
    page.locator('[data-coverage="confirmed"]').click()
    page.locator('#persona').select_option('Anonymous')
    assert page.locator('#coverage-panel tbody tr:visible').count() == 0, 'coverage must respect Anonymous filter'
    assert 'No matching operations' in page.locator('#coverage-heading').inner_text()
    assert 'Alice' not in page.locator('#coverage-detail').inner_text()
    page.locator('[data-map="surfaces"]').click()
    assert page.locator('#surface-rows tr:visible').count() == 0
    assert not page.locator('.inspector').is_visible(), 'no rows must mean no stale Alice inspector'
    assert page.locator('#surface-rows .selected-row').count() == 0
    assert 'No anonymous observations' in page.locator('#filter-note').inner_text()


def check_unknown_epoch(page):
    page.locator('[data-inspect="export"]').click()
    expect(page.locator('#inspect-identity')).to_have_text('Unknown')
    epoch = page.locator('.inspector dt').filter(has_text='Auth epoch').evaluate('e=>e.nextElementSibling.textContent')
    assert 'unknown' in epoch.lower() and 'demo-epoch-a' not in epoch, 'Unknown identity cannot inherit Alice auth epoch'
    assert not page.locator('.inspector [data-go="investigations"]').is_visible()
    page.locator('[data-map="coverage"]').click()
    page.locator('[data-coverage="blocked"]').click()
    detail = page.locator('#coverage-heading').inner_text()
    assert '/api/export' in detail and 'Unknown' in detail and 'epoch' in detail.lower()
    assert 'demo-epoch-a' not in detail


def check_filtered_selection(page):
    page.locator('#map-search').fill('/api/profile')
    expect(page.locator('#inspect-title')).to_have_text('GET /api/profile')
    assert page.locator('#surface-rows tr.selected-row:visible').count() == 1
    page.locator('[data-map="coverage"]').click()
    rows = page.locator('#coverage-panel tbody tr:visible')
    assert rows.count() == 1 and '/api/profile' in rows.inner_text()
    page.locator('[data-coverage="tested_no_issue"]').click()
    assert '/api/profile' in page.locator('#coverage-heading').inner_text()
    page.locator('#map-search').fill('no-such-operation')
    assert page.locator('#coverage-panel tbody tr:visible').count() == 0
    assert 'No matching operations' in page.locator('#coverage-heading').inner_text()
    page.locator('[data-map="surfaces"]').click()
    assert not page.locator('.inspector').is_visible()
    page.locator('#map-search').fill('')
    page.locator('#persona').select_option('Alice · member')
    assert page.locator('#surface-rows tr:visible').count() == 2
    assert page.locator('.inspector').is_visible()
    page.locator('[data-map="coverage"]').click()
    assert page.locator('#coverage-panel tbody tr:visible').count() == 2


def check_selection_clears_other_context(page):
    page.locator('[data-map="coverage"]').click()
    page.locator('[data-coverage="confirmed"]').click()
    page.locator('[data-map="surfaces"]').click()
    page.locator('[data-inspect="export"]').click()
    page.locator('[data-map="coverage"]').click()
    assert 'demo-epoch-a' not in page.locator('#coverage-heading').inner_text(), 'changing selected operation must clear the prior coverage context'
    assert 'Select a cell' in page.locator('#coverage-heading').inner_text()
    page.locator('[data-coverage="blocked"]').click()
    page.locator('[data-map="surfaces"]').click()
    expect(page.locator('#inspect-title')).to_have_text('POST /api/export')
    assert 'Unknown' in page.locator('#inspect-epoch').inner_text()


def pause_to_paused(page):
    page.locator('#pause-control').click()
    assert page.locator('#run-state').inner_text() == 'PAUSING · demo', 'Pause must drain before PAUSED'
    drain = page.get_by_role('button', name='Simulate drain complete', exact=True)
    assert drain.count() == 1 and drain.is_visible(), 'drain completion must be an explicit demo action'
    expect(drain).to_be_focused()
    assert page.locator('#stop-control').is_enabled()
    drain.click()
    expect(page.locator('#run-state')).to_have_text('PAUSED · demo')
    expect(page.locator('#pause-control')).to_have_text('Resume')
    expect(page.locator('#pause-control')).to_be_focused()


def check_pause_resume_preflight(page):
    pause_to_paused(page)
    page.locator('#pause-control').click()
    assert page.locator('#start-dialog').evaluate('e=>e.open'), 'Resume requires preflight'
    assert page.locator('#run-state').inner_text() == 'PAUSED · demo', 'Resume must not run before confirmation'
    assert 'Resume' in page.locator('#start-title').inner_text()
    page.keyboard.press('Escape')
    expect(page.locator('#pause-control')).to_be_focused()
    assert page.locator('#run-state').inner_text() == 'PAUSED · demo'
    page.locator('#pause-control').click()
    page.locator('#start-demo').click()
    expect(page.locator('#run-state')).to_have_text('RUNNING · demo')
    expect(page.locator('#pause-control')).to_be_focused()


def check_resume_preflight_stop(page):
    pause_to_paused(page)
    page.locator('#pause-control').click()
    assert_overlay_stop(page, '#start-dialog')
    assert page.get_by_role('button', name='Simulate drain complete').count() == 0


def check_stop_during_pause_drain(page):
    page.locator('#pause-control').click()
    assert page.locator('#run-state').inner_text() == 'PAUSING · demo'
    page.set_viewport_size({'width': 390, 'height': 1000})
    page.locator('#open-menu').click()
    assert_overlay_stop(page, '#sidebar')
    assert page.get_by_role('button', name='Simulate drain complete').count() == 0
    page.locator('#complete-stop').click()
    expect(page.locator('#run-state')).to_have_text('STOPPED · demo')
    expect(page.locator('#start-control')).to_be_focused()


def check_touch_targets(page):
    small = []
    for width in [1440, 1024, 390, 330, 320]:
        page.set_viewport_size({'width': width, 'height': 1000})
        for panel, selector in [('surfaces', '[data-inspect]'), ('coverage', '[data-coverage]')]:
            page.locator(f'[data-map="{panel}"]').click()
            sizes = page.locator(selector).evaluate_all("items=>items.map(e=>({label:e.textContent,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))")
            small.extend({'viewport': width, **s} for s in sizes if s['width'] < 44 or s['height'] < 44)
    assert not small, f'operation/coverage targets below 44px: {small}'


def check_typography(page):
    wrong = []
    for width in [1440, 390, 330]:
        page.set_viewport_size({'width': width, 'height': 1000})
        for view in ['map', 'skills']:
            page.evaluate('name=>showView(name, false)', view)
            for selector, minimum, exact in [('h1', 28, True), ('h2', 20, True),
                                              ('.eyebrow,.navlabel,.method,.demo,.topbar .muted,.topbar .status', 12, False)]:
                sizes = page.locator(selector).evaluate_all("items=>items.filter(e=>e.checkVisibility()).map(e=>({text:e.textContent.slice(0,60),size:parseFloat(getComputedStyle(e).fontSize)}))")
                wrong.extend({'viewport': width, **s} for s in sizes if (s['size'] != minimum if exact else s['size'] < minimum))
    assert not wrong, f'typography outside prototype spec: {wrong}'


def check_run_catalog_copy(page):
    page.evaluate("showView('skills', false)")
    text = page.locator('[data-page="skills"]').inner_text()
    assert 'new runs' in text and 'same run' in text and 'catalog snapshot' in text, 'catalog selection is pinned per run'
    page.locator('#skill-preview').click()
    status = page.locator('#skill-state').inner_text()
    assert 'new runs' in status and 'next run' in status and 'same run' in status
    assert 'new tasks' not in status
    page.evaluate("showView('investigations', false)")
    assert 'catalog pinned per run' in page.locator('[data-page="investigations"]').inner_text()


def check_empty_error_previews(page):
    # Re-check the parent's fixes, including navigation while content is unavailable.
    page.set_viewport_size({'width': 330, 'height': 1000})
    for mode, title in [('empty', 'No observations yet'), ('error', 'Evidence unavailable')]:
        page.locator('#preview-state').select_option(mode)
        for view in VIEWS:
            page.evaluate('name=>showView(name, false)', view)
            assert page.locator('[data-page]:visible').count() == 0
            assert not page.locator('.inspector').is_visible()
            expect(page.locator('#state-preview-title')).to_have_text(title)
            assert page.locator('#state-preview').is_visible()
            assert page.locator('#stop-control').is_visible() and page.locator('#stop-control').is_enabled()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#preview-state').select_option('normal')
        assert page.locator('[data-page="runtime"]').is_visible()
    page.evaluate("showView('map', false)")
    page.locator('#preview-state').select_option('stale')
    assert page.locator('[data-page="map"]').is_visible()
    assert 'last-known' in page.locator('#state-preview-title').inner_text()
    assert page.locator('#stop-control').is_enabled()


def check_cockpit_stream(page):
    page.goto((DOCS / 'Omnis_UI_Prototype.html').as_uri())
    page.reload()
    expect(page.locator('[data-page="overview"]')).to_be_visible()
    expect(page.get_by_role('heading', name='Brain stream', exact=True)).to_be_visible()
    stream = page.locator('#brain-stream')
    assert stream.locator('[data-actor]:visible').count() == 4
    page.locator('#stream-filter').select_option('validator')
    assert stream.locator('[data-actor]:visible').count() == 1
    assert 'Replay and controls' in stream.inner_text()
    assert 'Internal deliberations' not in stream.inner_text()
    stream.get_by_role('button', name='Inspect finding').click()
    expect(page.locator('[data-page="findings"]')).to_be_visible()
    expect(page.locator('.finding-row')).to_be_focused()
    row = page.locator('.finding-row').bounding_box()
    header = page.locator('.topbar').bounding_box()
    assert row['y'] >= header['y'] + header['height'], 'finding context must not be under the sticky header'
    page.evaluate("showView('overview', false)")
    page.locator('#stream-filter').select_option('all')
    assert stream.locator('[data-actor]:visible').count() == 4
    for width in [1440, 1280, 1024, 390, 320]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.locator('#stop-control').scroll_into_view_if_needed()
        assert page.locator('#stop-control').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def check_generated_document_csp(page):
    spec = importlib.util.spec_from_file_location('render_docs', ROOT / 'scripts' / 'render_docs.py')
    assert spec is not None and spec.loader is not None
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    # No disk write or network probe. Raw project HTML remains trusted input.
    html = renderer.render('## [Local & link](#local-link)\n\n<script>document.body.dataset.scriptRan="yes"</script>', 'Fixture', 'Fixture.md')
    page.set_content(html)
    assert page.locator('body').get_attribute('data-script-ran') is None, 'document CSP must block inline scripts'
    assert page.locator('body').evaluate('e=>getComputedStyle(e).fontSize') == '17px', 'inline styles must still work'
    assert page.locator('nav a').count() == 2, 'each TOC contains only its own plain heading link'
    assert page.locator('nav a').first.inner_text() == 'Local & link'


def check_cockpit_task_context(page):
    page.evaluate("showView('overview', false)")
    page.locator('#brain-stream').get_by_role('button', name='Inspect blocked task').click()
    expect(page.locator('#blocked-task')).to_be_visible()
    assert 'demo-task-02' in page.locator('#blocked-task').inner_text()
    assert '/api/export' in page.locator('#blocked-task').inner_text()
    assert 'UNKNOWN' in page.locator('#blocked-task').inner_text()
    page.evaluate("showView('map', false)")
    page.locator('[data-map="coverage"]').click()
    page.locator('[data-coverage="confirmed"]').click()
    assert 'demo-f-01' in page.locator('#coverage-detail').inner_text()
    page.locator('#persona').select_option('Anonymous')
    page.locator('#map-search').fill('/api/profile')
    page.evaluate("showView('overview', false)")
    page.locator('#brain-stream').get_by_role('button', name='Inspect operation').click()
    expect(page.locator('#surfaces-panel')).to_be_visible()
    expect(page.locator('#inspect-title')).to_have_text('GET /api/invoices/{id}')
    expect(page.locator('.inspector')).to_be_visible()
    assert page.locator('#map-search').input_value() == ''
    assert page.locator('#persona').input_value() == 'Alice · member'


def check_finding_inspection(page):
    page.evaluate("showView('findings', false)")
    finding = page.locator('[data-finding="demo-f-01"]')
    expect(finding).to_be_visible()
    assert page.locator('[data-finding]').count() == 1
    summary = finding.locator('summary').first
    summary.focus()
    assert summary.evaluate('''e => {
        const style = getComputedStyle(e);
        return parseFloat(style.outlineWidth) >= 2 &&
            parseFloat(style.outlineOffset) <= -parseFloat(style.outlineWidth);
    }'''), 'focus ring must sit inside the clipped finding card'
    focused_pixels = summary.screenshot()
    summary.evaluate('e => e.blur()')
    assert focused_pixels != summary.screenshot(), 'keyboard focus must change visible pixels, not only the DOM'
    summary.focus()
    page.keyboard.press('Enter')
    expect(finding).to_have_attribute('open', '')
    expect(page.get_by_role('heading', name='Validator decision', exact=True)).to_be_visible()
    assert 'CONFIRMED' in page.locator('#finding-verdict').inner_text()
    assert 'demo-r3' in page.locator('#finding-context').inner_text()
    assert 'demo-epoch-a' in page.locator('#finding-context').inner_text()
    page.locator('#replay-evidence summary').click()
    assert 'SYNTHETIC TRANSCRIPT' in page.locator('#replay-evidence pre').inner_text()
    assert 'No request was sent' in page.locator('#replay-evidence pre').inner_text()
    page.locator('#retest-preview').click()
    assert 'RETEST_INCONCLUSIVE' in page.locator('#retest-state').inner_text()
    for width in [1440, 1280, 1024, 390, 320]:
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        expect(page.locator('#finding-verdict')).to_be_visible()
    summary.focus()
    page.keyboard.press('Enter')
    assert finding.get_attribute('open') is None
    expect(summary).to_be_focused()


def check_finding_evidence_availability(page):
    page.evaluate("showView('overview', false)")
    page.locator('#brain-stream').get_by_role('button', name='Inspect finding', exact=True).click()
    expect(page.locator('[data-finding="demo-f-01"]')).to_have_attribute('open', '')
    verdict = page.locator('#finding-verdict').inner_text()
    page.locator('#replay-preview').click()
    assert 'No replay was executed' in page.locator('#replay-message').inner_text()
    for state in ['MISSING', 'TRUNCATED', 'CORRUPT', 'DELETED']:
        page.locator('#finding-evidence-state').select_option(state)
        expect(page.locator('#evidence-bundle')).to_be_hidden()
        expect(page.locator('#replay-preview')).to_be_disabled()
        assert state in page.locator('#evidence-availability').inner_text()
        assert 'unavailable' in page.locator('#evidence-availability').inner_text()
        assert page.locator('#finding-verdict').inner_text() == verdict
    page.locator('#finding-evidence-state').select_option('AVAILABLE')
    expect(page.locator('#evidence-bundle')).to_be_visible()
    expect(page.locator('#replay-preview')).to_be_enabled()
    assert page.locator('#finding-verdict').inner_text() == verdict


def check_finding_return_scroll(page):
    page.set_viewport_size({'width': 390, 'height': 1000})
    for _ in range(2):
        page.evaluate("showView('overview', false)")
        page.locator('#brain-stream').get_by_role('button', name='Inspect finding', exact=True).click()
        row = page.locator('.finding-row')
        expect(row).to_be_focused()
        rect, header = row.bounding_box(), page.locator('.topbar').bounding_box()
        assert rect['y'] >= header['y'] + header['height']
        assert rect['y'] + rect['height'] <= 1000


REGRESSIONS = [check_drawer_stop, check_approval_stop, check_preflight_stop, check_drawer_resize,
               check_stopped_focus, check_started_focus, check_run_state_live_region,
               check_anonymous_context, check_unknown_epoch, check_filtered_selection, check_selection_clears_other_context,
               check_pause_resume_preflight, check_resume_preflight_stop, check_stop_during_pause_drain,
               check_touch_targets, check_typography, check_run_catalog_copy,
               check_empty_error_previews, check_cockpit_stream, check_cockpit_task_context,
               check_finding_inspection, check_finding_evidence_availability,
               check_finding_return_scroll, check_generated_document_csp]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-documents", action="store_true")
    args = parser.parse_args()
    checks = []
    errors = []
    network = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which("chromium"), headless=True)
        context = browser.new_context()
        context.route("http://**/*", lambda route: (network.append(route.request.url), route.abort()))
        context.route("https://**/*", lambda route: (network.append(route.request.url), route.abort()))
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((DOCS / "Omnis_UI_Prototype.html").as_uri())
        for width in [1440, 1280, 1024, 390, 330, 320]:
            page.set_viewport_size({"width": width, "height": 1000})
            for view in VIEWS:
                page.evaluate("name => showView(name, false)", view)
                size = page.evaluate("({viewport:innerWidth, content:document.documentElement.scrollWidth, visible:document.querySelectorAll('[data-page]:not([hidden])').length})")
                checks.append({"kind": "prototype_view", "width": width, "view": view, "passed": size["content"] <= size["viewport"] and size["visible"] == 1, "size": size})
        page.evaluate("showView('map', false)")
        page.locator('[data-map="coverage"]').click()
        page.locator('[data-coverage="tested_no_issue"]').click()
        assert "Requires procedure revision" in page.locator("#coverage-detail").inner_text()
        page.locator("#preview-state").select_option("empty")
        assert page.locator('[data-page]:visible').count() == 0
        assert page.locator("#state-preview").is_visible()
        page.locator("#preview-state").select_option("normal")
        page.locator("#stop-control").click()
        assert "STOPPING" in page.locator("#run-state").inner_text()
        page.locator("#complete-stop").click()
        assert "STOPPED" in page.locator("#run-state").inner_text()
        page.locator("#start-control").click()
        assert page.locator("#start-dialog").evaluate("e=>e.open")
        page.keyboard.press("Escape")
        assert not page.locator("#start-dialog").evaluate("e=>e.open")
        assert page.locator("#start-control").evaluate("e=>e===document.activeElement")
        page.locator("#open-menu").click()
        assert page.locator(".maincol").evaluate("e=>e.inert")
        page.keyboard.press("Shift+Tab")
        assert page.locator('#sidebar [data-view="runtime"]').evaluate("e=>e===document.activeElement")
        page.keyboard.press("Escape")
        assert not page.locator(".maincol").evaluate("e=>e.inert")
        page.evaluate("showView('setup', false)")
        for _ in range(4):
            page.locator("#wizard-next").click()
        assert page.locator('[data-step="4"]').is_visible()
        assert page.get_by_placeholder("Never enter a credential here").is_disabled()
        checks.append({"kind": "interaction_contracts", "passed": True, "checks": ["coverage evidence detail", "empty hides synthetic data", "Stop pending/completed", "preflight dialog Esc/focus restore", "mobile menu inert/focus wrap/Esc", "wizard five steps", "credential input disabled"]})
        for regression in REGRESSIONS:
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.goto((DOCS / 'Omnis_UI_Prototype.html').as_uri() + '#map')
            # Hash navigation alone keeps the prior run/dialog/filter state.
            page.reload()
            try:
                regression(page)
                checks.append({'kind': 'regression', 'name': regression.__name__, 'passed': True})
            except (AssertionError, PlaywrightError) as error:
                checks.append({'kind': 'regression', 'name': regression.__name__, 'passed': False, 'error': str(error)})
        if args.include_documents:
            for stem in ["Omnis_Implementation_Plan", "Omnis_MVP_Architecture", "Omnis_UI_UX_Spec", "Omnis_Stack_Baseline", "Omnis_Implementation_Readiness_Review"]:
                for width in [1440, 390, 320]:
                    page.set_viewport_size({"width": width, "height": 1000})
                    page.goto((DOCS / (stem + ".html")).as_uri())
                    data = page.evaluate("({width:innerWidth,content:document.documentElement.scrollWidth,broken:[...document.querySelectorAll('a[href^=\"#\"]')].filter(a=>!document.getElementById(a.getAttribute('href').slice(1))).map(a=>a.getAttribute('href'))})")
                    checks.append({"kind": "document", "name": stem, "width": width, "passed": data["content"] <= data["width"] and not data["broken"], "data": data})
        browser.close()
    result = {"scope": "OFFLINE_DOCUMENTS_AND_SYNTHETIC_PROTOTYPE_ONLY", "checks": checks, "javascript_errors": errors, "unexpected_network": network, "passed": all(c["passed"] for c in checks) and not errors and not network}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failures": [c for c in checks if not c["passed"]], "javascript_errors": errors, "unexpected_network": network}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
