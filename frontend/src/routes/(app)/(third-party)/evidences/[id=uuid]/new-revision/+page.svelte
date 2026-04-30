<script lang="ts">
	import { goto } from '$app/navigation';
	import EvidenceRevisionUploader from '$lib/components/Forms/EvidenceRevisionUploader.svelte';
	import { pageTitle } from '$lib/utils/stores';

	interface Props {
		data: {
			evidence: any;
			latest: any | null;
			revisions: any[];
			taskNodeId: string | null;
		};
	}

	let { data }: Props = $props();
	$pageTitle = `New revision — ${data.evidence?.name ?? ''}`;

	function dest() {
		return data.taskNodeId ? `/task-nodes/${data.taskNodeId}/` : `/evidences/${data.evidence.id}/`;
	}
</script>

<div class="card bg-white shadow-lg p-6">
	<EvidenceRevisionUploader
		evidence={data.evidence}
		latestRevision={data.latest}
		taskNodeId={data.taskNodeId}
		onCancel={() => goto(dest())}
		onSuccess={() => goto(dest(), { invalidateAll: true })}
	/>
</div>
