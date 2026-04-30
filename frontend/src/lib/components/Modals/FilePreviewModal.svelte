<script lang="ts">
	import { onMount } from 'svelte';
	import { getModalStore } from '$lib/components/Modals/stores';

	interface Props {
		fileId: string;
		filename: string;
		downloadHref: string;
	}

	let { fileId, filename, downloadHref }: Props = $props();
	const modalStore = getModalStore();

	let blobType = $state<string | null>(null);
	let blobUrl = $state<string | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const res = await fetch(`/evidence-files/${fileId}/download`);
			if (!res.ok) {
				error = `Failed to load file (${res.status})`;
				return;
			}
			const blob = await res.blob();
			blobType = blob.type || 'application/octet-stream';
			blobUrl = URL.createObjectURL(blob);
		} catch (e: any) {
			error = e?.message ?? 'Preview failed';
		}
	});
</script>

<article class="bg-white rounded-lg shadow-2xl p-4 w-[90vw] h-[90vh] flex flex-col gap-3">
	<header class="flex items-center justify-between border-b pb-2">
		<div class="flex items-center gap-2 min-w-0">
			<i class="fa-solid fa-file text-gray-400"></i>
			<span class="font-semibold truncate">{filename}</span>
			{#if blobType}
				<span class="text-xs font-mono text-gray-500">{blobType}</span>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			<a
				href={downloadHref}
				class="btn preset-tonal-surface btn-sm"
				data-sveltekit-reload
				title="Download"
			>
				<i class="fa-solid fa-download mr-1"></i>Download
			</a>
			<button class="btn preset-tonal-surface btn-sm" onclick={() => modalStore.close()}>
				<i class="fa-solid fa-xmark"></i>
			</button>
		</div>
	</header>

	<div class="flex-1 overflow-auto flex items-center justify-center bg-gray-50 rounded">
		{#if error}
			<p class="text-error-500 font-bold">{error}</p>
		{:else if !blobUrl}
			<span>Loading…</span>
		{:else if blobType?.startsWith('image/')}
			<img src={blobUrl} alt={filename} class="max-w-full max-h-full object-contain" />
		{:else if blobType === 'application/pdf'}
			<embed src={blobUrl} type="application/pdf" class="w-full h-full" />
		{:else if blobType?.startsWith('text/') || blobType?.includes('json')}
			<iframe src={blobUrl} title={filename} class="w-full h-full bg-white"></iframe>
		{:else}
			<div class="text-center space-y-2">
				<i class="fa-solid fa-file text-4xl text-gray-300"></i>
				<p class="font-bold text-sm">No inline preview for this file type.</p>
				<p class="text-xs text-gray-500">{blobType}</p>
			</div>
		{/if}
	</div>
</article>
