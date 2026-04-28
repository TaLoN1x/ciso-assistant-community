import { BASE_API_URL } from '$lib/utils/constants';
import { error, type NumericRange } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, url }) => {
	const saId = url.searchParams.get('service_account');
	if (!saId) {
		error(400, { message: 'service_account query param is required' });
	}
	const remaining = new URLSearchParams(url.searchParams);
	remaining.delete('service_account');
	const qs = remaining.toString();
	const endpoint = `${BASE_API_URL}/iam/service-accounts/${saId}/keys/${qs ? '?' + qs : ''}`;

	const res = await fetch(endpoint);
	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: 'Request failed' }));
		error(res.status as NumericRange<400, 599>, body);
	}

	const data = await res.json();
	return new Response(JSON.stringify(data), {
		status: res.status,
		headers: { 'Content-Type': 'application/json' }
	});
};
