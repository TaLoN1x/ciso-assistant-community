<script lang="ts">
	import EvidenceRevisionUploaderModal from '$lib/components/Modals/EvidenceRevisionUploaderModal.svelte';
	import {
		getModalStore,
		type ModalComponent,
		type ModalSettings
	} from '$lib/components/Modals/stores';

	interface Props {
		evidenceId: string;
		evidenceName: string;
		taskNodeId?: string | null;
		label?: string;
		class?: string;
	}

	let {
		evidenceId,
		evidenceName,
		taskNodeId = null,
		label = 'New revision',
		class: klass = 'btn preset-filled-primary-500'
	}: Props = $props();

	const modalStore = getModalStore();

	async function open() {
		const res = await fetch(`/evidences/${evidenceId}/new-revision`, {
			headers: { Accept: 'application/json' }
		});
		const body = res.ok ? await res.json() : { results: [] };
		const latest = (body.results ?? [])[0] ?? null;

		const component: ModalComponent = {
			ref: EvidenceRevisionUploaderModal,
			props: {
				evidence: { id: evidenceId, name: evidenceName },
				latestRevision: latest,
				taskNodeId
			}
		};
		const modal: ModalSettings = { type: 'component', component };
		modalStore.trigger(modal);
	}
</script>

<button type="button" class={klass} onclick={open} data-testid="new-revision-button">
	<i class="fa-solid fa-plus mr-2"></i>{label}
</button>
