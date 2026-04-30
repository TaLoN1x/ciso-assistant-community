import { BASE_API_URL } from '$lib/utils/constants';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, params, setHeaders }) => {
	const upstream = await fetch(`${BASE_API_URL}/evidence-files/${params.id}/download/`);
	if (!upstream.ok) throw error(upstream.status, 'File not found');
	const contentType = upstream.headers.get('Content-Type') || 'application/octet-stream';
	const contentDisposition = upstream.headers.get('Content-Disposition') || '';
	setHeaders({
		'Content-Type': contentType,
		'Content-Disposition': contentDisposition || 'attachment'
	});
	return new Response(upstream.body, { status: upstream.status });
};
