import { TestContent, test, expect, type Page } from '../../../utils/test-utils.js';
import { PageContent } from '../../../utils/page-content.js';

const vars = TestContent.generateTestVars();

const sidebar = (page: Page) => page.getByTestId('sidebar');

const gotoFeatureFlags = async (page: Page) => {
	await page.goto('/settings');
	await page.waitForLoadState('networkidle');

	const tab = page.getByRole('tab', { name: /feature.flag/i });
	await expect(tab).toBeVisible();
	await expect(tab).not.toHaveAttribute('data-ssr');

	await tab.click();
	await page.waitForTimeout(500);

	await expect(
		page.locator('[id$="content-featureFlags"] [role="checkbox"]').first()
	).toBeVisible();
};

const setFlag = async (page: Page, flagLabel: string, enable: boolean) => {
	await gotoFeatureFlags(page);

	const panel = page.locator('[id$="content-featureFlags"]');
	const card = panel
		.locator('[role="checkbox"]')
		.filter({ has: page.locator('span.font-semibold', { hasText: flagLabel }) });

	await expect(card).toBeVisible();

	const isChecked = (await card.getAttribute('aria-checked')) === 'true';
	if (isChecked !== enable) {
		await card.click();
		await page.waitForTimeout(300);
		await page.getByRole('button', { name: /save/i }).click();
		await expect(page.getByTestId('toast')).toBeVisible();
		await page.waitForLoadState('networkidle');
	}
};

const FLAGS = {
	xrays: 'X-rays',
	incidents: 'Incidents',
	tasks: 'Tasks',
	objectivesIso: 'Objectives (ISO)',
	issuesIso: 'Issues (ISO)',
	riskAcceptances: 'Risk acceptances',
	exceptions: 'Exceptions',
	followUp: 'Findings tracking',
	ebiosRm: 'Ebios RM',
	scoringAssistant: 'Scoring assistant',
	vulnerabilities: 'Vulnerabilities',
	compliance: 'Compliance',
	tprm: 'Third party',
	privacy: 'Privacy',
	personalData: 'Personal Data',
	purposes: 'Purposes',
	rightRequests: 'Right Requests',
	dataBreaches: 'Data Breaches',
	terminologies: 'Terminologies',
	webhooks: 'Webhooks',
	journeys: 'Journeys',
	experimental: 'Experimental',
	inherentRisk: 'Inherent Risk'
} as const;

const SIDEBAR_TESTID: Record<keyof typeof FLAGS, string> = {
	xrays: 'accordion-item-x-rays',
	incidents: 'accordion-item-incidents',
	tasks: 'accordion-item-task-templates',
	objectivesIso: 'accordion-item-organisation-objectives',
	issuesIso: 'accordion-item-organisation-issues',
	riskAcceptances: 'accordion-item-risk-acceptances',
	exceptions: 'accordion-item-security-exceptions',
	followUp: 'accordion-item-findings-assessments',
	ebiosRm: 'accordion-item-ebios-rm',
	scoringAssistant: 'accordion-item-scoring-assistant',
	vulnerabilities: 'accordion-item-vulnerabilities',
	compliance: 'accordion-item-compliance',
	tprm: 'accordion-item-thirdpartycategory',
	privacy: 'accordion-item-privacy',
	personalData: 'accordion-item-personal-data',
	purposes: 'accordion-item-purposes',
	rightRequests: 'accordion-item-right-requests',
	dataBreaches: 'accordion-item-data-breaches',
	terminologies: 'accordion-item-terminologies',
	webhooks: '',
	journeys: 'accordion-item-presets',
	experimental: 'accordion-item-experimental',
	inherentRisk: ''
};

const SIDEBAR_SECTION: Partial<Record<keyof typeof FLAGS, string | null>> = {
	xrays: 'accordion-item-operations',
	incidents: 'accordion-item-operations',
	tasks: 'accordion-item-operations',
	objectivesIso: 'accordion-item-governance',
	issuesIso: 'accordion-item-governance',
	riskAcceptances: 'accordion-item-governance',
	exceptions: 'accordion-item-governance',
	followUp: 'accordion-item-governance',
	ebiosRm: 'accordion-item-risk',
	scoringAssistant: 'accordion-item-risk',
	vulnerabilities: 'accordion-item-risk',
	compliance: null,
	tprm: null,
	privacy: null,
	personalData: 'accordion-item-privacy',
	purposes: 'accordion-item-privacy',
	rightRequests: 'accordion-item-privacy',
	dataBreaches: 'accordion-item-privacy',
	terminologies: 'accordion-item-extra',
	webhooks: null,
	journeys: 'accordion-item-overview',
	experimental: 'accordion-item-extra',
	inherentRisk: null
};

const testSidebarFlag = async (page: Page, flagKey: keyof typeof FLAGS) => {
	const sectionTestId = SIDEBAR_SECTION[flagKey];
	const itemTestId = SIDEBAR_TESTID[flagKey];

	const openSection = async () => {
		await page.goto('/analytics');
		await page.waitForLoadState('networkidle');
		if (sectionTestId) {
			await sidebar(page).getByTestId(sectionTestId).click();
			await page.waitForTimeout(300);
		}
	};

	await setFlag(page, FLAGS[flagKey], true);
	await openSection();
	await expect(sidebar(page).getByTestId(itemTestId)).toBeVisible();

	await setFlag(page, FLAGS[flagKey], false);
	await openSection();
	await expect(sidebar(page).getByTestId(itemTestId)).not.toBeVisible();

	await setFlag(page, FLAGS[flagKey], true);
};

test.describe.configure({ mode: 'serial' });

test.describe('Feature flags', () => {
	test('X-Rays visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'xrays');
	});

	test('Incidents visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'incidents');
	});

	test('Tasks visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'tasks');
	});

	test('Risk Acceptances visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'riskAcceptances');
	});

	test('Exceptions visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'exceptions');
	});

	test('Findings Tracking visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'followUp');
	});

	test('Ebios RM visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'ebiosRm');
	});

	test('Scoring Assistant visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'scoringAssistant');
	});

	test('Vulnerabilities visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'vulnerabilities');
	});

	test('Compliance visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'compliance');
	});

	test('Third Party visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'tprm');
	});

	test('Objectives (ISO) visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'objectivesIso');
	});

	test('Issues (ISO) visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'issuesIso');
	});

	test('Privacy module visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'privacy');
	});

	test('Personal Data visibility toggling', async ({ logedPage, page }) => {
		await setFlag(page, FLAGS.privacy, true);
		await testSidebarFlag(page, 'personalData');
	});

	test('Purposes visibility toggling', async ({ logedPage, page }) => {
		await setFlag(page, FLAGS.privacy, true);
		await testSidebarFlag(page, 'purposes');
	});

	test('Right Requests visibility toggling', async ({ logedPage, page }) => {
		await setFlag(page, FLAGS.privacy, true);
		await testSidebarFlag(page, 'rightRequests');
	});

	test('Data Breaches visibility toggling', async ({ logedPage, page }) => {
		await setFlag(page, FLAGS.privacy, true);
		await testSidebarFlag(page, 'dataBreaches');
	});

	test('Terminologies visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'terminologies');
	});

	test('Webhooks adds a tab in Settings', async ({ logedPage, page }) => {
		await setFlag(page, FLAGS.webhooks, true);
		await page.goto('/settings');
		await page.waitForLoadState('networkidle');
		const tab = page.getByRole('tab', { name: /webhook/i });
		await expect(tab).toBeVisible();

		await setFlag(page, FLAGS.webhooks, false);
		await page.goto('/settings');
		await page.waitForLoadState('networkidle');
		await expect(page.getByRole('tab', { name: /webhook/i })).not.toBeVisible();

		await setFlag(page, FLAGS.webhooks, true);
	});

	test('Journeys visibility toggling', async ({ logedPage, page }) => {
		const openOverview = async () => {
			await page.goto('/analytics');
			await page.waitForLoadState('networkidle');
			await sidebar(page).getByTestId('accordion-item-overview').click();
			await page.waitForTimeout(300);
		};

		await setFlag(page, FLAGS.journeys, true);
		await openOverview();
		await expect(sidebar(page).getByTestId('accordion-item-presets')).toBeVisible();

		await setFlag(page, FLAGS.journeys, false);
		await openOverview();
		await expect(sidebar(page).getByTestId('accordion-item-presets')).not.toBeVisible();

		await setFlag(page, FLAGS.journeys, true);
	});

	test('Experimental visibility toggling', async ({ logedPage, page }) => {
		await testSidebarFlag(page, 'experimental');
	});

	test('Inherent Risk visibility on Risk Scenarios table view', async ({ logedPage, page }) => {
		const risksPage = new PageContent(page, '/risk-scenarios', 'Risk Scenarios');

		await setFlag(page, FLAGS.inherentRisk, true);
		await risksPage.goto();
		await expect(page.getByText('Inherent Level', { exact: false })).toBeVisible();

		await setFlag(page, FLAGS.inherentRisk, false);
		await risksPage.goto();
		await expect(page.getByText('Inherent Level', { exact: false })).not.toBeVisible();

		await setFlag(page, FLAGS.inherentRisk, true);
	});
});
