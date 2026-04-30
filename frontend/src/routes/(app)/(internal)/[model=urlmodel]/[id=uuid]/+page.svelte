<script lang="ts">
	import DetailView from '$lib/components/DetailView/DetailView.svelte';
	import Anchor from '$lib/components/Anchor/Anchor.svelte';
	import type { PageData, ActionData } from './$types';
	import { m } from '$paraglide/messages';

	interface Props {
		data: PageData;
		form: ActionData;
	}

	let { data, form }: Props = $props();
</script>

{#if data.model.name === 'fearedevent'}
	<div class="flex items-center justify-between mb-4">
		<Anchor
			breadcrumbAction="push"
			href={`/ebios-rm/${data.data.ebios_rm_study.id}`}
			class="flex items-center space-x-2 text-primary-800 hover:text-primary-600"
		>
			<i class="fa-solid fa-arrow-left"></i>
			<p>{m.goBackToEbiosRmStudy()}</p>
		</Anchor>
	</div>
{/if}

<DetailView {data} />

{#if data.model.name === 'evidence'}
	<div class="mt-4 flex justify-end">
		<a
			href={`/evidences/${data.data.id}/new-revision`}
			class="btn preset-filled-primary-500"
			data-testid="new-revision-button"
		>
			<i class="fa-solid fa-plus mr-2"></i>New revision
		</a>
	</div>
{/if}

{#if data.model.name == 'requirementmappingset' && data.data.frameworks_available}
	<div class="card my-4 p-4 bg-white">
		<span class="bg-purple-700 text-white px-2 py-1 rounded-sm text-sm font-semibold">new</span><a
			class="ml-2 hover:text-purple-700"
			href={`/experimental/mapping/${data.data.id}`}>{m.viewOnGraphExplorer()}</a
		>
	</div>
{/if}

{#if data.model.name === 'evidencerevision' && (!data.data.files || data.data.files.length === 0) && !data.data.attachment && !data.data.link}
	<div class="card mt-8 px-6 py-4 bg-gray-50 border border-dashed text-sm text-gray-600">
		<i class="fa-solid fa-circle-info mr-2"></i>
		This revision is empty (no files, no attachment, no link).
	</div>
{/if}

{#if data.model.name === 'evidencerevision' && data.data.files && data.data.files.length > 0}
	<div class="card mt-8 px-6 py-4 bg-white shadow-lg space-y-3">
		<div class="flex items-center justify-between">
			<h4 class="h4 font-semibold">
				Files ({data.data.files.length})
				{#if data.data.manifest_hash}
					<span class="ml-2 text-xs font-mono text-gray-500"
						>manifest {data.data.manifest_hash.slice(0, 6)}…{data.data.manifest_hash.slice(
							-4
						)}</span
					>
				{/if}
			</h4>
			<Anchor
				href={`/api/evidence-revisions/${data.data.id}/zip/`}
				class="btn preset-tonal-surface btn-sm"
			>
				<i class="fa-solid fa-file-zipper mr-2"></i>Download all (zip)
			</Anchor>
		</div>
		<table class="w-full text-sm">
			<thead class="bg-gray-50 text-xs uppercase text-gray-600">
				<tr>
					<th class="text-left px-3 py-2">File</th>
					<th class="text-right px-3 py-2">Size</th>
					<th class="text-left px-3 py-2">SHA-256</th>
					<th class="px-3 py-2"></th>
				</tr>
			</thead>
			<tbody>
				{#each data.data.files as f}
					<tr class="border-t">
						<td class="px-3 py-2">
							<i class="fa-solid fa-file mr-2 text-gray-400"></i>{f.original_name}
						</td>
						<td class="px-3 py-2 text-right tabular-nums">
							{#if f.size < 1024}{f.size} B
							{:else if f.size < 1024 * 1024}{(f.size / 1024).toFixed(1)} KB
							{:else}{(f.size / 1024 / 1024).toFixed(1)} MB{/if}
						</td>
						<td class="px-3 py-2 font-mono text-xs text-gray-500">
							{f.sha256 ? `${f.sha256.slice(0, 6)}…${f.sha256.slice(-4)}` : '—'}
						</td>
						<td class="px-3 py-2 text-right">
							<Anchor
								href={`/evidence-files/${f.id}/download`}
								class="text-gray-500 hover:text-blue-600"
								title="Download"
							>
								<i class="fa-solid fa-download"></i>
							</Anchor>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
