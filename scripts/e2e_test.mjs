/**
 * E2E headless test — Agentic Ebook Platform
 *
 * Flow:
 *   1. Login to admin UI
 *   2. Create topic "Agentic AI Architecture and Design Pattern"
 *   3. Trigger the AI pipeline
 *   4. Poll backend (DynamoDB via API) for pipeline progress — print each stage as it completes
 *   5. When pipeline reaches WaitForApproval → approve the draft
 *   6. Wait for publish to complete
 *   7. Print final status
 *
 * Run: node scripts/e2e_test.mjs
 */

import { chromium } from 'playwright';

const ADMIN_URL  = 'http://localhost:3000';
const API_URL    = 'http://localhost:8000';
const EMAIL      = 'vaibhavmaurya1986@gmail.com';
const PASSWORD   = 'EbookAdmin2026!';
const TOPIC_TITLE       = 'Agentic AI Architecture and Design Pattern';
const TOPIC_DESC        = 'What is Agent in the Agentic AI. What are the components. What are the most popular design patterns for an Agent.';
const TOPIC_INSTRUCTIONS = `- Start with a clear overview of what an Agentic AI system is
- Present key components in tabular format: name, role, brief description
- Include a conceptual block diagram description (text-based)
- Describe at least 3 common design patterns (ReAct, Plan-and-Execute, Reflection)
- Use sequence diagrams (text) to show agent-tool interaction
- Keep language clear for intermediate developers`;

const POLL_INTERVAL_MS = 10_000;   // check every 10 s
const PIPELINE_TIMEOUT_MS = 20 * 60_000; // 20 min max

// ── Helpers ────────────────────────────────────────────────────────────────────

function log(msg) {
  console.log(`[${new Date().toISOString()}] ${msg}`);
}

async function apiGet(path, token) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${await res.text()}`);
  return res.json();
}

async function apiPost(path, body, token) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${await res.text()}`);
  return res.json();
}

// Cognito token via UI login (we already have it in the browser session).
// We'll extract it from localStorage after login.
async function getTokenFromBrowser(page) {
  return page.evaluate(() => {
    const raw = localStorage.getItem('ebook-admin-auth');
    if (!raw) return null;
    return JSON.parse(raw).state?.token ?? null;
  });
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── Main ──────────────────────────────────────────────────────────────────────

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page    = await context.newPage();

  // Capture console errors from the app
  page.on('console', msg => {
    if (msg.type() === 'error') log(`[browser error] ${msg.text()}`);
  });
  page.on('pageerror', err => log(`[page error] ${err.message}`));

  try {
    // ── Step 1: Login ──────────────────────────────────────────────────────────
    log('Navigating to admin login…');
    await page.goto(`${ADMIN_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('input[type="email"]', EMAIL);
    await page.fill('input[type="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${ADMIN_URL}/topics`, { timeout: 15_000 });
    log('✓ Logged in');

    const token = await getTokenFromBrowser(page);
    if (!token) throw new Error('No auth token found in localStorage after login');
    log(`✓ Token obtained (${token.slice(0, 20)}…)`);

    // ── Step 2: Create topic via UI (exercise the form) ────────────────────────
    log('Creating topic via UI…');
    await page.click('button:has-text("+ New topic")');
    await page.waitForURL(`${ADMIN_URL}/topics/new`);
    await page.screenshot({ path: '/tmp/e2e_new_topic_form.png' });

    await page.fill('#title', TOPIC_TITLE);
    await page.fill('#description', TOPIC_DESC);
    await page.fill('#instructions', TOPIC_INSTRUCTIONS);
    await page.fill('#subtopics', 'What is an Agent, Key Components, Design Patterns, ReAct Pattern, Plan and Execute, Reflection Pattern');

    // Schedule = manual (default)
    await page.screenshot({ path: '/tmp/e2e_form_filled.png' });
    await page.click('button[type="submit"]:has-text("Create topic")');
    await page.waitForURL(`${ADMIN_URL}/topics`, { timeout: 10_000 });
    log('✓ Topic created via UI');
    await page.screenshot({ path: '/tmp/e2e_topic_list.png' });

    // ── Get topic_id from API — find the most recently created topic ───────────
    await sleep(1_000);
    const { topics } = await apiGet('/admin/topics', token);
    // Find by title, prefer the one with no runs (freshly created)
    const candidates = topics.filter(t => t.title === TOPIC_TITLE);
    if (!candidates.length) throw new Error('Topic not found in API response after creation');
    // Sort by order (desc) or pick the one without last_run
    const topic = candidates.find(t => !t.last_run) ?? candidates[candidates.length - 1];
    const topicId = topic.topic_id;
    log(`✓ Topic ID: ${topicId}`);

    // ── Step 3: Trigger pipeline ───────────────────────────────────────────────
    log('Triggering AI pipeline…');
    const { run_id, execution_arn } = await apiPost(`/admin/topics/${topicId}/trigger`, {}, token);
    log(`✓ Run started — run_id: ${run_id}`);
    log(`  execution_arn: ${execution_arn}`);

    // ── Step 4: Poll for progress ──────────────────────────────────────────────
    log('\n--- Pipeline monitoring started ---');
    const start = Date.now();
    const seenEvents = new Set();
    let runStatus = 'RUNNING';

    while (Date.now() - start < PIPELINE_TIMEOUT_MS) {
      await sleep(POLL_INTERVAL_MS);

      // Fetch run detail with trace events
      let runDetail;
      try {
        runDetail = await apiGet(`/admin/topics/${topicId}/runs/${run_id}`, token);
      } catch (e) {
        log(`Poll error (will retry): ${e.message}`);
        continue;
      }

      runStatus = runDetail.run.status;
      const events = runDetail.trace_events ?? [];

      // Print any new trace events
      for (const ev of events) {
        const key = ev.sk;
        if (!seenEvents.has(key)) {
          seenEvents.add(key);
          const costStr = ev.cost_usd && parseFloat(ev.cost_usd) > 0
            ? ` | $${parseFloat(ev.cost_usd).toFixed(5)}`
            : '';
          const tokStr = ev.token_usage
            ? ` | tokens: ${JSON.stringify(ev.token_usage)}`
            : '';
          log(`  [${ev.event_type}] stage=${ev.stage ?? '—'} agent=${ev.agent_name ?? '—'}${costStr}${tokStr}`);
          if (ev.error_message) log(`    ERROR: ${ev.error_message}`);
        }
      }

      log(`  Run status: ${runStatus} | trace events so far: ${events.length}`);

      // Check if waiting for approval
      if (runStatus === 'WAITING_APPROVAL') {
        log('\n✓ Pipeline paused at WaitForApproval — draft ready for review');
        break;
      }

      if (runStatus === 'FAILED') {
        throw new Error('Pipeline FAILED — see trace events above for details');
      }
    }

    if (runStatus !== 'WAITING_APPROVAL') {
      throw new Error(`Timed out or unexpected status: ${runStatus}`);
    }

    // ── Step 5: Review & Approve ───────────────────────────────────────────────
    log('\nFetching draft for review…');
    const review = await apiGet(`/admin/topics/${topicId}/review/${run_id}`, token);
    log(`  Review status: ${review.review_status}`);
    log(`  Word count: ${review.word_count}`);
    log(`  Sections: ${(review.sections ?? []).join(', ')}`);
    if (review.scorecard) {
      log(`  Scorecard: overall=${review.scorecard.overall} | adherence=${review.scorecard.instruction_adherence} | style=${review.scorecard.style_compliance} | clarity=${review.scorecard.clarity}`);
    }
    if (review.diff) {
      log(`  Diff: first_version=${review.diff.is_first_version}`);
      log(`  Release notes: ${review.diff.release_notes ?? '(none)'}`);
    }

    log('\nApproving draft via API…');
    await apiPost(`/admin/topics/${topicId}/review/${run_id}`, { decision: 'approve', notes: 'Auto-approved by E2E test' }, token);
    log('✓ Approval submitted');

    // ── Step 6: Wait for publish ───────────────────────────────────────────────
    log('Waiting for publish to complete…');
    const publishStart = Date.now();
    while (Date.now() - publishStart < 3 * 60_000) {
      await sleep(5_000);
      const runDetail = await apiGet(`/admin/topics/${topicId}/runs/${run_id}`, token);
      const st = runDetail.run.status;
      log(`  Post-approval run status: ${st}`);

      if (st === 'APPROVED') {
        log('\n✓ Pipeline completed — topic PUBLISHED');
        const totalCost = runDetail.run.cost_usd ?? '0';
        log(`  Total cost: $${parseFloat(totalCost).toFixed(4)}`);
        break;
      }
      if (st === 'FAILED') {
        log('WARNING: Run failed after approval — check trace events');
        break;
      }
    }

    // ── Step 7: Verify in UI ───────────────────────────────────────────────────
    log('\nVerifying topic appears in topic list…');
    await page.goto(`${ADMIN_URL}/topics`, { waitUntil: 'networkidle' });
    const titleVisible = await page.locator(`text=${TOPIC_TITLE}`).isVisible();
    log(`  Topic visible in UI: ${titleVisible ? '✓ YES' : '✗ NO'}`);

    log('\n=== E2E TEST COMPLETE ===');

  } catch (err) {
    log(`\n✗ TEST FAILED: ${err.message}`);
    // Take a screenshot for debugging
    await page.screenshot({ path: '/tmp/e2e_failure.png', fullPage: true });
    log('Screenshot saved to /tmp/e2e_failure.png');
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
