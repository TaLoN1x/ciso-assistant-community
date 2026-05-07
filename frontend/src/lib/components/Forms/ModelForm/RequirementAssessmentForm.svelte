<script lang="ts">
	import Select from '../Select.svelte';
	import TextArea from '$lib/components/Forms/TextArea.svelte';
	import MarkdownField from '$lib/components/Forms/MarkdownField.svelte';
	import HiddenInput from '$lib/components/Forms/HiddenInput.svelte';
	import type { SuperValidated } from 'sveltekit-superforms';
	import type { ModelInfo, CacheLock } from '$lib/utils/types';
	import { m } from '$paraglide/messages';
	import AutocompleteSelect from '../AutocompleteSelect.svelte';
	import FolderTreeSelect from '../FolderTreeSelect.svelte';
	import { getFieldVisibility } from '$lib/utils/helpers';

	interface Props {
		form: SuperValidated<any>;
		model: ModelInfo;
		cacheLocks?: Record<string, CacheLock>;
		formDataCache?: Record<string, any>;
		context: string;
		object?: any;
	}

	let {
		form,
		model,
		cacheLocks = {},
		formDataCache = $bindable({}),
		context,
		object
	}: Props = $props();

	let isParentLocked = $derived(object?.compliance_assessment?.is_locked || false);

	// Per-RA viewer role from the serialized payload, with a safe auditor
	// default (used by create flows where no instance exists yet). Field
	// visibility is gated against this role so the fallback form honours the
	// same rules as the unified edit page.
	const viewerRole: 'auditor' | 'respondent' =
		object?.viewer_role === 'respondent' ? 'respondent' : 'auditor';
	const fieldVis = getFieldVisibility(object?.compliance_assessment, viewerRole);
</script>

{#if context === 'selectEvidences'}
	<AutocompleteSelect
		multiple
		{form}
		optionsEndpoint="evidences"
		optionsExtraFields={[['folder', 'str']]}
		field="evidences"
		label={m.evidences()}
	/>
{:else if context === 'selectAppliedControls'}
	<AutocompleteSelect
		multiple
		{form}
		optionsEndpoint="applied-controls"
		optionsExtraFields={[['folder', 'str']]}
		field="applied_controls"
		label={m.appliedControls()}
	/>
{:else}
	{#if fieldVis.showStatus}
		<Select
			{form}
			options={model.selectOptions['status']}
			field="status"
			label={m.status()}
			cacheLock={cacheLocks['status']}
			bind:cachedValue={formDataCache['status']}
		/>
	{/if}
	{#if fieldVis.showResult}
		<Select
			{form}
			options={model.selectOptions['result']}
			field="result"
			label={m.result()}
			cacheLock={cacheLocks['result']}
			bind:cachedValue={formDataCache['result']}
		/>
	{/if}
	{#if fieldVis.showExtendedResult && object?.compliance_assessment?.extended_result_enabled}
		<Select
			{form}
			options={model.selectOptions['extended_result']}
			field="extended_result"
			label={m.extendedResult()}
			cacheLock={cacheLocks['extended_result']}
			bind:cachedValue={formDataCache['extended_result']}
		/>
	{/if}
	{#if fieldVis.showObservation}
		<MarkdownField
			{form}
			field="observation"
			label={m.observation()}
			cacheLock={cacheLocks['observation']}
			bind:cachedValue={formDataCache['observation']}
		/>
	{/if}
	<FolderTreeSelect
		{form}
		field="folder"
		cacheLock={cacheLocks['folder']}
		bind:cachedValue={formDataCache['folder']}
		label={m.domain()}
	/>
	<HiddenInput {form} field="compliance_assessment" />
{/if}
