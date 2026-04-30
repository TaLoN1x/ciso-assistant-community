<script lang="ts">
	import ConfirmModal from '$lib/components/Modals/ConfirmModal.svelte';
	import { getModelInfo } from '$lib/utils/crud.js';
	import type { ModalComponent, ModalSettings, ModalStore } from '@skeletonlabs/skeleton-svelte';
	import { onMount } from 'svelte';
	import type { PageData } from './$types';
	import { page } from '$app/state';
	import Anchor from '$lib/components/Anchor/Anchor.svelte';
	import DetailView from '$lib/components/DetailView/DetailView.svelte';
	import FilePreviewModal from '$lib/components/Modals/FilePreviewModal.svelte';
	import { m } from '$paraglide/messages';
	import { defaults } from 'sveltekit-superforms';
	import { z } from 'zod';
	import { zod4 as zod } from 'sveltekit-superforms/adapters';
	import { canPerformAction } from '$lib/utils/access-control';
	import { getModalStore } from '$lib/components/Modals/stores';

	interface Props {
		data: PageData;
	}

	let { data }: Props = $props();

	interface Attachment {
		type: string;
		url: string;
		fileExists: boolean;
	}

	let attachment: Attachment | undefined = $state(undefined);
	const modalStore: ModalStore = getModalStore();

	function openFilePreview(file: any) {
		const component: ModalComponent = {
			ref: FilePreviewModal,
			props: {
				fileId: file.id,
				filename: file.original_name,
				downloadHref: `/evidence-files/${file.id}/download`
			}
		};
		modalStore.trigger({ type: 'component', component });
	}

	function modalConfirm(id: string, name: string, action: string): void {
		const modalComponent: ModalComponent = {
			ref: ConfirmModal,
			props: {
				_form: defaults(
					{ id, urlmodel: 'evidence-revisions' },
					zod(z.object({ id: z.string(), urlmodel: z.string() }))
				),
				schema: zod(z.object({ id: z.string(), urlmodel: z.string() })),
				id: id,
				debug: false,
				URLModel: getModelInfo('evidence-revisions').urlModel,
				formAction: action
			}
		};
		const modal: ModalSettings = {
			type: 'component',
			component: modalComponent,
			// Data
			title: m.confirmModalTitle(),
			body: `${m.confirmModalMessage()}: ${name}?`
		};
		modalStore.trigger(modal);
	}

	onMount(async () => {
		const fetchAttachment = async () => {
			const res = await fetch(`./${data.data.id}/attachment`);
			const blob = await res.blob();
			return {
				type: blob.type,
				url: URL.createObjectURL(blob),
				fileExists: res.ok
			};
		};
		attachment = data.data.attachment ? await fetchAttachment() : undefined;
	});

	const user = page.data.user;
	const canEditObject: boolean = canPerformAction({
		user,
		action: 'change',
		model: data.model.name,
		domain:
			data.model.name === 'folder'
				? data.data.id
				: (data.data.folder?.id ?? data.data.folder ?? user.root_folder_id)
	});
</script>

<DetailView {data} />

{#if (!data.data.files || data.data.files.length === 0) && !data.data.attachment && !data.data.link}
	<div class="card mt-8 px-6 py-4 bg-gray-50 border border-dashed text-sm text-gray-600">
		<i class="fa-solid fa-circle-info mr-2"></i>
		This revision is empty (no files, no attachment, no link).
	</div>
{/if}

{#if data.data.files && data.data.files.length > 0}
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
			<a
				href={`/evidence-revisions/${data.data.id}/zip`}
				class="btn preset-tonal-surface btn-sm"
				data-sveltekit-reload
			>
				<i class="fa-solid fa-file-zipper mr-2"></i>Download all (zip)
			</a>
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
							<button
								type="button"
								class="text-left hover:underline hover:text-blue-600 inline-flex items-center"
								onclick={() => openFilePreview(f)}
								title="Preview"
							>
								<i class="fa-solid fa-file mr-2 text-gray-400"></i>{f.original_name}
							</button>
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
							<a
								href={`/evidence-files/${f.id}/download`}
								class="text-gray-500 hover:text-blue-600"
								title="Download"
								data-sveltekit-reload
							>
								<i class="fa-solid fa-download"></i>
							</a>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

{#if data.data.attachment && (!data.data.files || data.data.files.length === 0)}
	<div class="card mt-8 px-6 py-4 bg-white flex flex-col shadow-lg space-y-4">
		<div class="flex flex-row justify-between">
			<h4 class="h4 font-semibold" data-testid="attachment-name-title">
				{data.data.attachment}
			</h4>
			<div class="space-x-2">
				<Anchor
					href={`./${data.data.id}/attachment`}
					class="btn preset-filled-primary-500 h-fit"
					data-testid="attachment-download-button"
					><i class="fa-solid fa-download mr-2"></i> {m.download()}</Anchor
				>
				{#if canEditObject}
					<button
						onclick={(_) => {
							modalConfirm(data.data.id, data.data.attachment, '?/deleteAttachment');
						}}
						onkeydown={(_) =>
							modalConfirm(data.data.id, data.data.attachment, '?/deleteAttachment')}
						class="btn preset-filled-tertiary-500 h-full"><i class="fa-solid fa-trash"></i></button
					>
				{/if}
			</div>
		</div>
		{#if attachment}
			{#if attachment.type.startsWith('image')}
				<img src={attachment.url} alt="attachment" />
			{:else if attachment.type === 'application/pdf'}
				<embed src={attachment.url} type="application/pdf" width="100%" height="600px" />
			{:else}
				<div class="flex items-center justify-center space-x-4">
					{#if !attachment.fileExists}
						<p class="text-error-500 font-bold">{m.couldNotFindAttachmentMessage()}</p>
					{:else}
						<p class="font-bold text-sm">{m.NoPreviewMessage()}</p>
					{/if}
				</div>
			{/if}
		{:else}
			<span data-testid="loading-field">
				{m.loading()}...
			</span>
		{/if}
	</div>
{/if}
