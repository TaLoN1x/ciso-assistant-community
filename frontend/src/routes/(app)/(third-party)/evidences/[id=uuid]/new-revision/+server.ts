import { BASE_API_URL } from '$lib/utils/constants';
import { error, type NumericRange } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ fetch, request, params }) => {
	const incoming = await request.formData();
	const outgoing = new FormData();
	for (const [key, value] of incoming.entries()) {
		if (value instanceof File) {
			const bytes = new Uint8Array(await value.arrayBuffer());
			outgoing.append(key, new Blob([bytes], { type: value.type }), value.name);
		} else {
			outgoing.append(key, value);
		}
	}
	const endpoint = `${BASE_API_URL}/evidences/${params.id}/revisions/create-multifile/`;
	const res = await fetch(endpoint, { method: 'POST', body: outgoing });
	const text = await res.text();
	if (!res.ok) {
		error(res.status as NumericRange<400, 599>, text || 'Upload failed');
	}
	return new Response(text, {
		status: res.status,
		headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
	});
};

export const PUT: RequestHandler = async ({ fetch, request, params }) => {
	const body = await request.json();
	const upstream = await fetch(
		`${BASE_API_URL}/evidences/${params.id}/revisions/preflight/`,
		{
			method: 'POST',
			body: JSON.stringify(body),
			headers: { 'Content-Type': 'application/json' }
		}
	);
	const text = await upstream.text();
	return new Response(text, {
		status: upstream.status,
		headers: { 'Content-Type': 'application/json' }
	});
};
