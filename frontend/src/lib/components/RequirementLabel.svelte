<script lang="ts">
	interface Props {
		ref_id?: string | null;
		name?: string | null;
		bold?: boolean;
		class?: string;
	}

	let { ref_id, name, bold = false, class: className = '' }: Props = $props();

	const sep = $derived(ref_id && /[\p{L}\p{N}]$/u.test(ref_id) ? ' - ' : ' ');
</script>

{#if ref_id || name}
	<span class={className}>
		{#if ref_id}<span
				class="inline-block px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200 font-mono text-xs leading-none align-middle"
				>{ref_id}</span
			>{/if}{#if ref_id && name}{sep}{/if}{#if name}<span class={bold ? 'font-semibold' : ''}
				>{name}</span
			>{/if}
	</span>
{/if}
