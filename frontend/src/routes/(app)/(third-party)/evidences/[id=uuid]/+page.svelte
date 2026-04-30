<script lang="ts">
	import NewRevisionButton from '$lib/components/Forms/NewRevisionButton.svelte';
	import type { PageData } from './$types';
	import DetailView from '$lib/components/DetailView/DetailView.svelte';

	interface Props {
		data: PageData;
	}

	let { data }: Props = $props();
</script>

<DetailView {data} />

<div class="mt-4 flex justify-end">
	<NewRevisionButton evidenceId={data.data.id} evidenceName={data.data.name} />
</div>
