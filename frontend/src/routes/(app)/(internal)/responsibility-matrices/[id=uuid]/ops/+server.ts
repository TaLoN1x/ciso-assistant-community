import { BASE_API_URL } from '$lib/utils/constants';
import { error, json, type NumericRange } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

async function proxy(
	fetchFn: typeof fetch,
	url: string,
	method: string,
	body?: unknown
): Promise<Response> {
	const opts: RequestInit = {
		method,
		headers: { 'Content-Type': 'application/json' }
	};
	if (body !== undefined) opts.body = JSON.stringify(body);
	const res = await fetchFn(url, opts);
	if (res.status === 204) return new Response(null, { status: 204 });
	const data = await res.json().catch(() => ({}));
	if (!res.ok) error(res.status as NumericRange<400, 599>, data);
	return json(data, { status: res.status });
}

export const POST: RequestHandler = async ({ fetch, params, request, url }) => {
	const action = url.searchParams.get('action');
	const matrixId = params.id;
	const body = await request.json().catch(() => ({}));

	switch (action) {
		case 'create-activity':
			return proxy(fetch, `${BASE_API_URL}/pmbok/responsibility-activities/`, 'POST', {
				matrix: matrixId,
				name: body.name,
				order: body.order ?? 0
			});

		case 'update-activity':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-activities/${body.id}/`,
				'PATCH',
				{ name: body.name, description: body.description }
			);

		case 'delete-activity':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-activities/${body.id}/`,
				'DELETE'
			);

		case 'create-actor':
			return proxy(fetch, `${BASE_API_URL}/pmbok/responsibility-matrix-actors/`, 'POST', {
				matrix: matrixId,
				actor: body.actor,
				order: body.order ?? 0
			});

		case 'delete-actor':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-matrix-actors/${body.id}/`,
				'DELETE'
			);

		case 'cycle-cell':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-matrices/${matrixId}/cycle-cell/`,
				'POST',
				{ activity: body.activity, actor: body.actor, direction: body.direction }
			);

		case 'reorder-activities':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-matrices/${matrixId}/reorder-activities/`,
				'POST',
				{ ids: body.ids }
			);

		case 'reorder-actors':
			return proxy(
				fetch,
				`${BASE_API_URL}/pmbok/responsibility-matrices/${matrixId}/reorder-actors/`,
				'POST',
				{ ids: body.ids }
			);

		default:
			error(400, { detail: `unknown action: ${action}` });
	}
};
