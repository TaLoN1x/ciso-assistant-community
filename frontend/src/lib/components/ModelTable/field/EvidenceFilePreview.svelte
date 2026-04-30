<script lang="ts">
	interface Props {
		cell: any;
		meta: any;
	}

	let { cell, meta }: Props = $props();

	const fileCount = $derived(Array.isArray(meta.files) ? meta.files.length : 0);
	const firstName = $derived(
		fileCount > 0 ? meta.files[0].original_name : typeof cell === 'string' ? cell : null
	);
</script>

{#if fileCount > 1}
	<span
		class="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 whitespace-nowrap inline-flex items-center gap-1"
	>
		<i class="fa-solid fa-folder"></i>
		{fileCount} files
	</span>
{:else if firstName}
	<span class="inline-flex items-center gap-1 text-sm">
		<i class="fa-solid fa-file text-gray-400"></i>
		<span class="truncate">{firstName}</span>
	</span>
{/if}
