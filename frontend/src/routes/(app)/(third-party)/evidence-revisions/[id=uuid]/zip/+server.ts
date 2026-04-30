import { BASE_API_URL } from '$lib/utils/constants';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, params, setHeaders }) => {
	const upstream = await fetch(`${BASE_API_URL}/evidence-revisions/${params.id}/zip/`);
	if (!upstream.ok) throw error(upstream.status, 'Bundle not found');
	setHeaders({
		'Content-Type': upstream.headers.get('Content-Type') || 'application/zip',
		'Content-Disposition': upstream.headers.get('Content-Disposition') || 'attachment'
	});
	return new Response(upstream.body, { status: upstream.status });
};
