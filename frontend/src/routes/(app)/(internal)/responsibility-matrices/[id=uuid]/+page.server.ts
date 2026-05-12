import { getModelInfo } from '$lib/utils/crud';
import { loadDetail } from '$lib/utils/load';
import { BASE_API_URL } from '$lib/utils/constants';
import { nestedDeleteFormAction } from '$lib/utils/actions';
import { superValidate } from 'sveltekit-superforms';
import { zod4 as zod } from 'sveltekit-superforms/adapters';
import { z } from 'zod';
import type { PageServerLoad } from './$types';
import type { Actions } from '@sveltejs/kit';

const linkedObjectsSchema = z.object({
	assets: z.array(z.string().uuid()).default([]),
	applied_controls: z.array(z.string().uuid()).default([]),
	task_templates: z.array(z.string().uuid()).default([]),
	risk_assessments: z.array(z.string().uuid()).default([]),
	compliance_assessments: z.array(z.string().uuid()).default([]),
	findings_assessments: z.array(z.string().uuid()).default([]),
	business_impact_analyses: z.array(z.string().uuid()).default([])
});

export const load: PageServerLoad = async (event) => {
	const detailData = await loadDetail({
		event,
		model: getModelInfo('responsibility-matrices'),
		id: event.params.id
	});

	const matrixId = event.params.id;

	const [
		activitiesRes,
		actorsRes,
		assignmentsRes,
		allActorsRes,
		assetsRes,
		controlsRes,
		taskTemplatesRes,
		riskAssessmentsRes,
		complianceAssessmentsRes,
		findingsAssessmentsRes,
		biasRes
	] = await Promise.all([
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-activities/?matrix=${matrixId}&ordering=order`
		),
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-matrix-actors/?matrix=${matrixId}&ordering=order`
		),
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-assignments/?activity__matrix=${matrixId}`
		),
		event.fetch(`${BASE_API_URL}/actors/?ordering=user__email`),
		event.fetch(`${BASE_API_URL}/assets/?ordering=name`),
		event.fetch(`${BASE_API_URL}/applied-controls/?ordering=name`),
		event.fetch(`${BASE_API_URL}/task-templates/?ordering=name`),
		event.fetch(`${BASE_API_URL}/risk-assessments/?ordering=name`),
		event.fetch(`${BASE_API_URL}/compliance-assessments/?ordering=name`),
		event.fetch(`${BASE_API_URL}/findings-assessments/?ordering=name`),
		event.fetch(`${BASE_API_URL}/resilience/business-impact-analysis/?ordering=name`)
	]);

	const activities = activitiesRes.ok ? (await activitiesRes.json()).results ?? [] : [];
	const matrixActors = actorsRes.ok ? (await actorsRes.json()).results ?? [] : [];
	const assignments = assignmentsRes.ok ? (await assignmentsRes.json()).results ?? [] : [];
	const allActors = allActorsRes.ok ? (await allActorsRes.json()).results ?? [] : [];
	const allAssets = assetsRes.ok ? (await assetsRes.json()).results ?? [] : [];
	const allAppliedControls = controlsRes.ok ? (await controlsRes.json()).results ?? [] : [];
	const allTaskTemplates = taskTemplatesRes.ok
		? (await taskTemplatesRes.json()).results ?? []
		: [];
	const allRiskAssessments = riskAssessmentsRes.ok
		? (await riskAssessmentsRes.json()).results ?? []
		: [];
	const allComplianceAssessments = complianceAssessmentsRes.ok
		? (await complianceAssessmentsRes.json()).results ?? []
		: [];
	const allFindingsAssessments = findingsAssessmentsRes.ok
		? (await findingsAssessmentsRes.json()).results ?? []
		: [];
	const allBusinessImpactAnalyses = biasRes.ok ? (await biasRes.json()).results ?? [] : [];

	const linkedObjectsForm = await superValidate(zod(linkedObjectsSchema), { errors: false });

	return {
		...detailData,
		activities,
		matrixActors,
		assignments,
		allActors,
		allAssets,
		allAppliedControls,
		allTaskTemplates,
		allRiskAssessments,
		allComplianceAssessments,
		allFindingsAssessments,
		allBusinessImpactAnalyses,
		linkedObjectsForm
	};
};

export const actions: Actions = {
	delete: async (event) => {
		return nestedDeleteFormAction({ event });
	}
};
