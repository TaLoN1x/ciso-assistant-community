import { getModelInfo } from '$lib/utils/crud';
import { loadDetail } from '$lib/utils/load';
import { BASE_API_URL } from '$lib/utils/constants';
import { nestedDeleteFormAction } from '$lib/utils/actions';
import type { PageServerLoad } from './$types';
import type { Actions } from '@sveltejs/kit';

export const load: PageServerLoad = async (event) => {
	const detailData = await loadDetail({
		event,
		model: getModelInfo('responsibility-matrices'),
		id: event.params.id
	});

	const matrixId = event.params.id;

	const [activitiesRes, actorsRes, assignmentsRes, allActorsRes] = await Promise.all([
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-activities/?matrix=${matrixId}&ordering=order`
		),
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-matrix-actors/?matrix=${matrixId}&ordering=order`
		),
		event.fetch(
			`${BASE_API_URL}/pmbok/responsibility-assignments/?activity__matrix=${matrixId}`
		),
		event.fetch(`${BASE_API_URL}/actors/?ordering=user__email`)
	]);

	const activities = activitiesRes.ok ? (await activitiesRes.json()).results ?? [] : [];
	const matrixActors = actorsRes.ok ? (await actorsRes.json()).results ?? [] : [];
	const assignments = assignmentsRes.ok ? (await assignmentsRes.json()).results ?? [] : [];
	const allActors = allActorsRes.ok ? (await allActorsRes.json()).results ?? [] : [];

	return {
		...detailData,
		activities,
		matrixActors,
		assignments,
		allActors
	};
};

export const actions: Actions = {
	delete: async (event) => {
		return nestedDeleteFormAction({ event });
	}
};
