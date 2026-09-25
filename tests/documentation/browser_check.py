"""Offline documentation/prototype checks using optional local Playwright.

Not a test of the Omnis application or of target confinement. No network allowed.
Run: python tests/documentation/browser_check.py --output <scratch-report.json>
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"
VIEWS = ["dashboard", "overview", "stream", "map", "investigations", "findings", "reports", "setup", "providers", "skills", "runtime"]


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
    page.locator('#approval-open-inline').click()
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
    page.locator('#coverage-panel [data-operation="invoice"] [data-coverage="confirmed"]').click()
    page.locator('#persona').select_option('Anonymous')
    assert page.locator('[data-coverage-operation]:visible').count() == 0, 'coverage must respect Anonymous filter'
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
    rows = page.locator('[data-coverage-operation]:visible')
    assert rows.count() == 1 and '/api/profile' in rows.inner_text()
    page.locator('#coverage-panel [data-operation="profile"] [data-coverage="tested_no_issue"]').click()
    assert '/api/profile' in page.locator('#coverage-heading').inner_text()
    page.locator('#map-search').fill('no-such-operation')
    assert page.locator('[data-coverage-operation]:visible').count() == 0
    assert 'No matching operations' in page.locator('#coverage-heading').inner_text()
    page.locator('[data-map="surfaces"]').click()
    assert not page.locator('.inspector').is_visible()
    page.locator('#map-search').fill('')
    page.locator('#persona').select_option('Alice · member')
    assert page.locator('#surface-rows tr:visible').count() == 4
    assert page.locator('.inspector').is_visible()
    page.locator('[data-map="coverage"]').click()
    assert page.locator('[data-coverage-operation]:visible').count() == 4


def check_selection_clears_other_context(page):
    page.locator('[data-map="coverage"]').click()
    page.locator('#coverage-panel [data-operation="invoice"] [data-coverage="confirmed"]').click()
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
    page.locator('#prototype-tools > summary').click()
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
    expect(page.locator('[data-page="dashboard"]')).to_be_visible()
    page.get_by_role('button', name='Open engagement', exact=True).click()
    expect(page.locator('[data-page="overview"]')).to_be_visible()
    page.locator('#engagement-nav [data-view="stream"]').click()
    expect(page.get_by_role('heading', name='Brain stream', exact=True)).to_be_visible()
    stream = page.locator('#brain-stream')
    assert stream.locator('[data-actor]:visible').count() == 8
    page.locator('#stream-filter').select_option('validator')
    assert stream.locator('[data-actor]:visible').count() == 4
    assert 'Replay and controls' in stream.inner_text()
    assert 'Internal deliberations' not in stream.inner_text()
    stream.locator('[data-open-finding="demo-f-01"]').first.click()
    expect(page.locator('[data-page="findings"]')).to_be_visible()
    expect(page.locator('[data-finding="demo-f-01"] > summary')).to_be_focused()
    row = page.locator('[data-finding="demo-f-01"] > summary').bounding_box()
    header = page.locator('.topbar').bounding_box()
    assert row['y'] >= header['y'] + header['height'], 'finding context must not be under the sticky header'
    page.evaluate("showView('stream', false)")
    page.locator('#stream-filter').select_option('all')
    assert stream.locator('[data-actor]:visible').count() == 8
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
    page.evaluate("showView('stream', false)")
    page.locator('#brain-stream').get_by_role('button', name='Inspect blocked task').click()
    expect(page.locator('#blocked-task')).to_be_visible()
    assert 'demo-task-02' in page.locator('#blocked-task').inner_text()
    assert '/api/export' in page.locator('#blocked-task').inner_text()
    assert 'UNKNOWN' in page.locator('#blocked-task').inner_text()
    page.evaluate("showView('map', false)")
    page.locator('[data-map="coverage"]').click()
    page.locator('#coverage-panel [data-operation="invoice"] [data-coverage="confirmed"]').click()
    assert 'demo-f-01' in page.locator('#coverage-detail').inner_text()
    page.locator('#persona').select_option('Anonymous')
    page.locator('#map-search').fill('/api/profile')
    page.evaluate("showView('stream', false)")
    page.locator('#brain-stream [data-operation-link="invoice"]').click()
    expect(page.locator('#surfaces-panel')).to_be_visible()
    expect(page.locator('#inspect-title')).to_have_text('GET /api/invoices/{id}')
    expect(page.locator('.inspector')).to_be_visible()
    assert page.locator('#map-search').input_value() == ''
    assert page.locator('#persona').input_value() == 'Alice · member'


def check_finding_inspection(page):
    page.evaluate("showView('findings', false)")
    finding = page.locator('[data-finding="demo-f-01"]')
    expect(finding).to_be_visible()
    assert page.locator('[data-finding]').count() == 3
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
    page.locator('#finding-demo-tools > summary').click()
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
    page.evaluate("showView('stream', false)")
    page.locator('#brain-stream [data-open-finding="demo-f-01"]').first.click()
    expect(page.locator('[data-finding="demo-f-01"]')).to_have_attribute('open', '')
    verdict = page.locator('#finding-verdict').inner_text()
    page.locator('#finding-demo-tools > summary').click()
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
        page.evaluate("showView('stream', false)")
        page.locator('#brain-stream [data-open-finding="demo-f-01"]').first.click()
        row = page.locator('[data-finding="demo-f-01"] > summary')
        expect(row).to_be_focused()
        rect, header = row.bounding_box(), page.locator('.topbar').bounding_box()
        assert rect['y'] >= header['y'] + header['height']
        assert rect['y'] + rect['height'] <= 1000


def check_zoom_and_media(page):
    page.set_viewport_size({'width': 1440, 'height': 1100})
    page.emulate_media(reduced_motion='reduce')
    assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
    assert page.evaluate('document.getAnimations().length') == 0
    # CSS zoom is an additional stress test, not native browser zoom certification.
    page.evaluate("document.body.style.zoom='2'")
    for view in ['overview', 'findings', 'map']:
        page.evaluate('name=>showView(name,false)', view)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), view
        expect(page.locator('#stop-control')).to_be_visible()
    page.evaluate("document.body.style.zoom='1';showView('findings',false)")
    page.emulate_media(forced_colors='active')
    assert page.evaluate("matchMedia('(forced-colors: active)').matches")
    page.locator('[data-finding="demo-f-01"] > summary').focus()
    assert page.locator('[data-finding="demo-f-01"] > summary').evaluate('e=>parseFloat(getComputedStyle(e).outlineWidth)') >= 2
    page.emulate_media(forced_colors='none', reduced_motion='no-preference')


def check_dashboard_engagement_settings_separation(page):
    page.goto((DOCS / 'Omnis_UI_Prototype.html').as_uri())
    page.reload()
    expect(page.locator('[data-page="dashboard"]')).to_be_visible()
    expect(page.locator('#engagement-nav')).to_be_hidden()
    expect(page.locator('#settings-nav')).to_be_hidden()
    expect(page.locator('[data-global="dashboard"]')).to_have_attribute('aria-current', 'page')
    page.get_by_role('button', name='Open engagement', exact=True).click()
    expect(page.locator('[data-page="overview"]')).to_be_visible()
    expect(page.locator('#engagement-nav')).to_be_visible()
    expect(page.locator('[data-global="engagement"]')).to_have_attribute('aria-current', 'page')
    assert page.locator('#engagement-nav [data-view="skills"],#engagement-nav [data-view="runtime"]').count() == 0
    expect(page.locator('#brain-stream')).to_be_hidden()
    page.locator('#engagement-nav [data-view="stream"]').click()
    expect(page.locator('#brain-stream')).to_be_visible()
    page.locator('[data-global="settings"]').click()
    expect(page.locator('#engagement-nav')).to_be_hidden()
    expect(page.locator('#settings-nav')).to_be_visible()
    expect(page.locator('[data-global="settings"]')).to_have_attribute('aria-current', 'page')
    page.locator('#settings-nav [data-view="skills"]').click()
    expect(page.locator('[data-page="skills"]')).to_be_visible()
    expect(page.locator('#stop-control')).to_be_visible()
    page.locator('[data-global="dashboard"]').click()
    expect(page.locator('[data-page="dashboard"]')).to_be_visible()
    expect(page.locator('#settings-nav')).to_be_hidden()
    page.locator('#stop-control').click()
    expect(page.locator('[data-run-label]')).to_have_text('STOPPING · demo')
    page.locator('#complete-stop').click()
    expect(page.locator('[data-run-label]')).to_have_text('STOPPED · demo')
    page.locator('[data-page="dashboard"] [data-go="new-engagement"]').first.click()
    expect(page.get_by_role('heading', name='New engagement', exact=True)).to_be_visible()
    expect(page.locator('#engagement-nav')).to_be_hidden()
    page.locator('[data-global="engagement"]').click()
    page.locator('#engagement-setup-control').click()
    expect(page.get_by_role('heading', name='Engagement setup', exact=True)).to_be_visible()
    expect(page.locator('#engagement-nav')).to_be_visible()


def check_navigation_context_regressions(page):
    failures = []
    page.evaluate("showView('setup', false)")
    for _ in range(4):
        page.locator('#wizard-next').click()
    page.locator('[data-global="dashboard"]').click()
    page.locator('[data-page="dashboard"] [data-go="new-engagement"]').first.click()
    if not page.locator('[data-step="0"]').is_visible():
        failures.append('new engagement inherited the existing wizard step')
    page.locator('[data-global="engagement"]').click()
    nav, header = page.locator('#engagement-nav').bounding_box(), page.locator('.topbar').bounding_box()
    if nav['y'] < header['y'] + header['height']:
        failures.append('navigation hidden behind sticky run controls after entering engagement')
    page.set_viewport_size({'width': 390, 'height': 1000})
    for view, scope in [('skills', 'settings'), ('new-engagement', 'dashboard')]:
        page.evaluate('name=>showView(name, false)', view)
        page.locator('#open-menu').click()
        context = page.locator('#drawer-run-context')
        if context.count() != 1 or not context.is_visible() or 'run-demo' not in context.inner_text():
            failures.append(f'{view}: drawer Stop lost its run identity')
        selected = page.locator(f'#sidebar [data-drawer-global="{scope}"][aria-current="page"]')
        if selected.count() != 1:
            failures.append(f'{view}: drawer global selection lost its scope')
        page.keyboard.press('Escape')
    assert not failures, failures


def check_simulation_controls_are_separate(page):
    page.evaluate("showView('dashboard', false)")
    expect(page.locator('#preview-state')).to_be_hidden()
    expect(page.locator('#stop-control')).to_be_visible()
    page.locator('#prototype-tools > summary').click()
    page.locator('#preview-state').select_option('empty')
    expect(page.locator('[data-page="dashboard"]')).to_be_hidden()
    page.locator('#preview-state').select_option('normal')
    expect(page.locator('[data-page="dashboard"]')).to_be_visible()
    page.locator('#prototype-tools > summary').click()
    page.evaluate("showView('findings', false)")
    page.locator('[data-finding="demo-f-01"] > summary').click()
    expect(page.locator('#finding-evidence-state')).to_be_hidden()
    expect(page.locator('#evidence-bundle')).to_be_visible()
    page.locator('#finding-demo-tools > summary').click()
    page.locator('#finding-evidence-state').select_option('MISSING')
    expect(page.locator('#evidence-bundle')).to_be_hidden()
    assert 'CONFIRMED' in page.locator('#finding-verdict').inner_text()


def check_reference_fonts_are_local(page):
    result = page.evaluate('''async () => {
        await document.fonts.ready;
        return {family: getComputedStyle(document.body).fontFamily,
            loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)};
    }''')
    assert 'Geist' in result['family'], 'reference typography must be used, not merely the palette'
    assert 'Geist' in result['loaded'] and 'Geist Mono' in result['loaded'], result


def check_reference_cockpit_projection_flow(page):
    page.evaluate("showView('dashboard', false)")
    assert page.locator('#dashboard-metrics .metric-card').count() == 4, 'reference dashboard metrics are missing'
    page.get_by_role('button', name='Open engagement', exact=True).click()
    for key, value in [('confirmed', '3'), ('critical', '0'), ('high', '2'), ('coverage', '64%'), ('endpoints', '5')]:
        expect(page.locator(f'#overview-metrics [data-metric="{key}"] .metric-value')).to_have_text(value)
    assert 'VALIDATE' in page.locator('#overview-phase').inner_text()
    expect(page.locator('#severity-total')).to_have_text('3')
    assert '84 / 300' in page.locator('#budget-panel').inner_text()
    assert '7 / 11' in page.locator('#overview-progress').inner_text()
    page.locator('#engagement-nav [data-view="stream"]').click()
    page.locator('[data-stream-kind="tools"]').click()
    kinds = page.locator('#brain-stream [data-event-kind]:visible').evaluate_all('items=>items.map(e=>e.dataset.eventKind)')
    assert kinds and set(kinds) <= {'tool_called', 'tool_result'}
    page.locator('[data-stream-kind="endpoint"]').click()
    expect(page.locator('#brain-stream [data-operation-link="file"]')).to_be_visible()
    page.locator('#brain-stream [data-operation-link="file"]').click()
    expect(page.locator('#inspect-title')).to_have_text('GET /api/files/preview')
    page.locator('#engagement-nav [data-view="reports"]').click()
    page.locator('#generate-demo-report').click()
    first = page.locator('[data-report-id="demo-report-1"]')
    assert '2 confirmed' in first.inner_text()
    with page.expect_download() as pending:
        first.locator('[data-export-format="json"]').click()
    with tempfile.TemporaryDirectory(prefix='omnis-demo-report-') as directory:
        path = Path(directory) / 'report.json'
        pending.value.save_as(path)
        report = json.loads(path.read_text())
        assert report['demo'] is True
        assert {f['id'] for f in report['findings']} == {'demo-f-01', 'demo-f-03'}
        assert all(f['validation_status'] == 'CONFIRMED' for f in report['findings'])
        with page.expect_download() as html_pending:
            first.locator('[data-export-format="html"]').click()
        html_path = Path(directory) / 'report.html'
        html_pending.value.save_as(html_path)
        report_page = page.context.new_page()
        report_errors = []
        report_page.on('pageerror', lambda error: report_errors.append(str(error)))
        try:
            report_page.goto(html_path.as_uri())
            assert report_page.locator('article').count() == 2
            assert 'DEMO report' in report_page.locator('h1').inner_text()
            assert 'CONFIRMED' in report_page.locator('body').inner_text()
            assert not report_errors, report_errors
        finally:
            report_page.close()
    page.locator('#engagement-nav [data-view="findings"]').click()
    page.locator('[data-finding-filter="review"]').click()
    finding = page.locator('[data-finding="demo-f-02"]')
    finding.locator('summary').first.click()
    finding.locator('[data-review-decision="APPROVED"]').click()
    assert 'Approved for report' in finding.inner_text()
    page.locator('#engagement-nav [data-view="reports"]').click()
    page.locator('#generate-demo-report').click()
    assert '3 confirmed' in page.locator('[data-report-id="demo-report-2"]').inner_text()
    assert '2 confirmed' in page.locator('[data-report-id="demo-report-1"]').inner_text()
    with page.expect_download() as original_pending:
        page.locator('[data-report-id="demo-report-1"] [data-export-format="json"]').click()
    with tempfile.TemporaryDirectory(prefix='omnis-demo-history-') as directory:
        original_path = Path(directory) / 'original.json'
        original_pending.value.save_as(original_path)
        assert json.loads(original_path.read_text()) == report, 'download must use the saved snapshot, not current findings'


def check_model_projection_text_and_missing_evidence(page):
    page.evaluate("""() => {
        const f = OmnisUI.model.state.findings[0];
        f.title = '<img src="https://untrusted.invalid/x" onerror="window.demoInjected=true">';
        f.summary = '<svg onload="window.demoInjected=true"></svg>';
        OmnisUI.renderProjections();
        OmnisUI.openFinding(f.id);
    }""")
    assert page.locator('[data-finding="demo-f-01"] img,[data-finding="demo-f-01"] svg[onload]').count() == 0
    assert page.evaluate('window.demoInjected') is None
    assert '<img' in page.locator('[data-finding="demo-f-01"] > summary').inner_text()
    page.locator('#finding-demo-tools > summary').click()
    page.locator('#finding-evidence-state').select_option('MISSING')
    assert page.evaluate('OmnisUI.model.summary().coverage.covered') == 6
    page.evaluate("showView('map', false)")
    page.locator('[data-map="surfaces"]').click()
    page.locator('[data-inspect="invoice"]').click()
    assert 'unavailable' in page.locator('#inspect-evidence').inner_text().lower()
    assert 'SYNTHETIC TRANSCRIPT' not in page.locator('#inspect-evidence').inner_text()
    page.locator('[data-map="coverage"]').click()
    page.locator('#coverage-panel [data-operation="invoice"] [data-coverage="confirmed"]').click()
    assert 'MISSING' in page.locator('#coverage-evidence').inner_text()
    assert 'SYNTHETIC TRANSCRIPT' not in page.locator('#coverage-evidence').inner_text()


def check_dashboard_phase_survives_review_rerender(page):
    page.evaluate("showView('dashboard', false)")
    page.locator('#stop-control').click()
    page.locator('#complete-stop').click()
    expect(page.locator('[data-page="dashboard"] [data-demo-phase]')).to_have_text('STOPPED')
    page.locator('[data-page="dashboard"] [data-open-finding="demo-f-02"]').click()
    page.locator('[data-review-finding="demo-f-02"][data-review-decision="HELD"]').click()
    page.locator('.global-nav [data-global="dashboard"]').click()
    expect(page.locator('#run-state')).to_have_text('STOPPED · demo')
    expect(page.locator('[data-page="dashboard"] [data-demo-phase]')).to_have_text('STOPPED')
    expect(page.locator('#dashboard-metrics [data-metric="active"] .metric-value')).to_have_text('0')
    page.locator('#start-control').click()
    page.locator('#start-demo').click()
    expect(page.locator('[data-page="dashboard"] [data-demo-phase]')).to_have_text('VALIDATE')


def check_finding_keyboard_return_clears_sticky_header(page):
    for width in [1440, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.reload()
        page.evaluate("showView('dashboard', false)")
        page.locator('[data-page="dashboard"] [data-open-finding="demo-f-02"]').click()
        page.locator('[data-review-finding="demo-f-02"][data-review-decision="HELD"]').click()
        page.locator('[data-finding-filter="held"]').click()
        page.locator('[data-review-finding="demo-f-02"][data-review-decision="APPROVED"]').click()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        summary = page.locator('[data-finding="demo-f-02"] > summary')
        expect(summary).to_be_focused()
        bounds = summary.evaluate('e => ({top:e.getBoundingClientRect().top,header:document.querySelector(".topbar").getBoundingClientRect().bottom})')
        assert bounds['top'] >= bounds['header'], (width, bounds)


def check_reference_stream_density(page):
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.evaluate("showView('stream')")
    heights = page.locator('#brain-stream .stream-event').evaluate_all('es => es.map(e => e.getBoundingClientRect().height)')
    assert len(heights) == 8 and max(heights) <= 120, heights
    targets = page.locator('#brain-stream button').evaluate_all('es => es.map(e => e.getBoundingClientRect().height)')
    assert targets and min(targets) >= 44, 'compact rows must retain usable hit targets'


REGRESSIONS = [check_drawer_stop, check_approval_stop, check_preflight_stop, check_drawer_resize,
               check_stopped_focus, check_started_focus, check_run_state_live_region,
               check_anonymous_context, check_unknown_epoch, check_filtered_selection, check_selection_clears_other_context,
               check_pause_resume_preflight, check_resume_preflight_stop, check_stop_during_pause_drain,
               check_touch_targets, check_typography, check_run_catalog_copy,
               check_empty_error_previews, check_cockpit_stream, check_cockpit_task_context,
               check_finding_inspection, check_finding_evidence_availability,
               check_finding_return_scroll, check_zoom_and_media,
               check_dashboard_engagement_settings_separation,
               check_navigation_context_regressions, check_simulation_controls_are_separate,
               check_reference_fonts_are_local, check_reference_cockpit_projection_flow,
               check_model_projection_text_and_missing_evidence,
               check_dashboard_phase_survives_review_rerender,
               check_finding_keyboard_return_clears_sticky_header,
               check_reference_stream_density,
               check_generated_document_csp]


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
        page.locator('#coverage-panel [data-operation="profile"] [data-coverage="tested_no_issue"]').click()
        assert "Requires procedure revision" in page.locator("#coverage-detail").inner_text()
        page.locator('#prototype-tools > summary').click()
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
        assert page.locator('#drawer-engagement [data-view="reports"]').evaluate("e=>e===document.activeElement")
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
