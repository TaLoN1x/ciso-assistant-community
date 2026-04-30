<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import EvidenceRevisionUploader from '$lib/components/Forms/EvidenceRevisionUploader.svelte';
	import { getModalStore } from '$lib/components/Modals/stores';

	interface Props {
		evidence: { id: string; name: string };
		latestRevision?: any;
		taskNodeId?: string | null;
		parent?: any;
	}

	let { evidence, latestRevision = null, taskNodeId = null, parent }: Props = $props();
	const modalStore = getModalStore();

	function close() {
		parent?.onClose?.();
		modalStore.close();
	}

	async function onSuccess() {
		await invalidateAll();
		close();
	}
</script>

<article class="modal-shell w-full max-w-3xl bg-white rounded-lg shadow-2xl p-6">
	<EvidenceRevisionUploader {evidence} {latestRevision} {taskNodeId} onCancel={close} {onSuccess} />
</article>
