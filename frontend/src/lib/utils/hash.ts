export const MAX_HASHABLE_BYTES = 200 * 1024 * 1024;

export async function sha256Hex(blob: Blob): Promise<string> {
	if (blob.size > MAX_HASHABLE_BYTES) {
		throw new Error(`File too large for client-side hashing (${blob.size} bytes)`);
	}
	const buf = await blob.arrayBuffer();
	const hash = await crypto.subtle.digest('SHA-256', buf);
	return Array.from(new Uint8Array(hash))
		.map((b) => b.toString(16).padStart(2, '0'))
		.join('');
}

export function shortHash(hex: string): string {
	if (!hex || hex.length < 10) return hex || '';
	return `${hex.slice(0, 6)}…${hex.slice(-4)}`;
}

export function fmtSize(n: number): string {
	if (n < 1024) return `${n} B`;
	if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
	return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
