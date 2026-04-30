import { BASE_API_URL } from '$lib/utils/constants';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, params, url }) => {
	const evidenceRes = await fetch(`${BASE_API_URL}/evidences/${params.id}/`);
	if (!evidenceRes.ok) throw error(evidenceRes.status, 'Evidence not found');
	const evidence = await evidenceRes.json();

	const revRes = await fetch(`${BASE_API_URL}/evidence-revisions/?evidence=${params.id}`);
	const revisions = revRes.ok ? (await revRes.json()).results || [] : [];
	revisions.sort((a: any, b: any) => (b.version ?? 0) - (a.version ?? 0));
	const latest = revisions[0] ?? null;

	const taskNodeId = url.searchParams.get('task_node');

	return { evidence, latest, revisions, taskNodeId };
};
