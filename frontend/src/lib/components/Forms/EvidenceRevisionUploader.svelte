<script lang="ts">
	import { sha256Hex, shortHash, fmtSize } from '$lib/utils/hash';
	import { m } from '$paraglide/messages';

	interface Props {
		evidence: { id: string; name: string };
		latestRevision?: { version?: number; files?: any[] } | null;
		taskNodeId?: string | null;
		submitUrl?: string;
		onSuccess?: (rev: any) => void;
		onCancel?: () => void;
	}

	let {
		evidence,
		latestRevision = null,
		taskNodeId = null,
		submitUrl,
		onSuccess,
		onCancel
	}: Props = $props();

	const url = submitUrl ?? `/evidences/${evidence.id}/new-revision`;

	type DraftAction = 'keep' | 'replace' | 'remove';
	type DraftEntry = {
		name: string;
		baseSize: number;
		baseHash: string;
		action: DraftAction;
		newFile?: File;
		newSize?: number;
		newHash?: string;
	};

	const inherited: { name: string; size: number; hash: string }[] = (
		latestRevision?.files ?? []
	).map((f: any) => ({
		name: f.original_name,
		size: f.size ?? 0,
		hash: f.sha256
	}));

	let draftEntries = $state<DraftEntry[]>(
		inherited.map((f) => ({
			name: f.name,
			baseSize: f.size,
			baseHash: f.hash,
			action: 'keep' as DraftAction
		}))
	);
	let additions = $state<{ name: string; size: number; hash: string; file: File }[]>([]);
	let observation = $state('');
	let link = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let fileInput: HTMLInputElement | null = $state(null);
	let hashing = $state<{ name: string; status: string }[]>([]);

	const nextVersion = (latestRevision?.version ?? 0) + 1;
	const isSimpleCase = inherited.length <= 1;

	const finalFiles = $derived.by(() => {
		const inheritedKept = draftEntries.filter((e) => e.action === 'keep');
		const replaced = draftEntries.filter((e) => e.action === 'replace');
		return [
			...inheritedKept.map((e) => ({ name: e.name, size: e.baseSize, hash: e.baseHash })),
			...replaced.map((e) => ({
				name: e.name,
				size: e.newSize ?? 0,
				hash: e.newHash ?? ''
			})),
			...additions.map((a) => ({ name: a.name, size: a.size, hash: a.hash }))
		];
	});

	const totalSize = $derived(finalFiles.reduce((s, f) => s + f.size, 0));

	function setAction(idx: number, action: DraftAction) {
		const e = draftEntries[idx];
		if (action !== 'replace') {
			draftEntries[idx] = {
				...e,
				action,
				newFile: undefined,
				newSize: undefined,
				newHash: undefined
			};
			return;
		}
		const replInput = document.createElement('input');
		replInput.type = 'file';
		replInput.onchange = async () => {
			const f = replInput.files?.[0];
			if (!f) return;
			const hash = await sha256Hex(f);
			draftEntries[idx] = {
				...e,
				action: 'replace',
				newFile: f,
				newSize: f.size,
				newHash: hash
			};
		};
		replInput.click();
	}

	async function handleFiles(files: FileList) {
		const records = Array.from(files).map((f) => ({ name: f.name, status: 'hashing' }));
		hashing = [...hashing, ...records];

		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			const recordIdx = hashing.length - records.length + i;
			let hash: string;
			try {
				hash = await sha256Hex(file);
			} catch (e: any) {
				hashing[recordIdx] = { name: file.name, status: `error: ${e.message}` };
				continue;
			}

			const sameNameIdx = draftEntries.findIndex((e) => e.name === file.name);
			if (sameNameIdx >= 0) {
				const entry = draftEntries[sameNameIdx];
				if (entry.baseHash === hash) {
					hashing[recordIdx] = { name: file.name, status: 'duplicate' };
					continue;
				}
				draftEntries[sameNameIdx] = {
					...entry,
					action: 'replace',
					newFile: file,
					newSize: file.size,
					newHash: hash
				};
				hashing[recordIdx] = { name: file.name, status: 'replaced' };
				continue;
			}

			additions = [...additions, { name: file.name, size: file.size, hash, file }];
			hashing[recordIdx] = { name: file.name, status: 'queued' };
		}
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
	}

	async function submit() {
		if (finalFiles.length === 0 && !link) {
			error = 'Add at least one file or a link.';
			return;
		}
		submitting = true;
		error = null;

		const fd = new FormData();
		const manifest: any[] = [];
		let uploadIdx = 0;
		for (const e of draftEntries) {
			if (e.action === 'keep') {
				manifest.push({ name: e.name, source: 'inherit', hash: e.baseHash });
			} else if (e.action === 'replace' && e.newFile) {
				const field = `file_${uploadIdx++}`;
				fd.append(field, e.newFile, e.name);
				manifest.push({ name: e.name, source: 'upload', hash: e.newHash, field });
			}
		}
		for (const a of additions) {
			const field = `file_${uploadIdx++}`;
			fd.append(field, a.file, a.name);
			manifest.push({ name: a.name, source: 'upload', hash: a.hash, field });
		}
		fd.append('manifest', JSON.stringify(manifest));
		fd.append('observation', observation);
		if (link) fd.append('link', link);
		if (taskNodeId) fd.append('task_node', taskNodeId);

		try {
			const res = await fetch(url, { method: 'POST', body: fd });
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				error = body.detail || body.error || `Upload failed (${res.status})`;
				submitting = false;
				return;
			}
			const created = await res.json().catch(() => ({}));
			onSuccess?.(created);
		} catch (e: any) {
			error = e?.message || 'Upload failed';
			submitting = false;
		}
	}
</script>

<div class="space-y-4">
	<header class="flex items-start justify-between gap-4">
		<div>
			<div class="text-xs uppercase tracking-wide text-gray-500">New revision</div>
			<h1 class="text-xl font-semibold">{evidence.name}</h1>
			<div class="text-sm text-gray-600 mt-1">
				{#if latestRevision}
					Current: <strong>v{latestRevision.version}</strong>
					· {inherited.length}
					{inherited.length === 1 ? m.file() : 'files'}
				{:else}
					First revision
				{/if}
				· will become <strong>v{nextVersion}</strong>
			</div>
		</div>
	</header>

	{#if !isSimpleCase}
		<section class="border rounded">
			<div class="px-3 py-2 bg-gray-50 border-b text-xs uppercase tracking-wide text-gray-600">
				Files in current revision — v{latestRevision?.version}
			</div>
			<ul class="divide-y text-sm">
				{#each draftEntries as e, idx}
					<li class="px-3 py-2 flex items-center gap-3">
						<span
							class="font-mono text-xs px-1.5 py-0.5 rounded border w-24 inline-flex items-center justify-center {e.action ===
							'keep'
								? 'text-gray-600 bg-gray-50 border-gray-200'
								: e.action === 'replace'
									? 'text-amber-700 bg-amber-50 border-amber-200'
									: 'text-red-700 bg-red-50 border-red-200'}"
						>
							{e.action === 'keep' ? 'inherit' : e.action === 'replace' ? 'Replace' : m.remove()}
						</span>
						<span class="flex-1 truncate">
							<i class="fa-solid fa-file mr-1 text-gray-400"></i>{e.name}
						</span>
						<span class="text-xs text-gray-500 tabular-nums w-32 text-right">
							{#if e.action === 'replace' && e.newSize}
								{fmtSize(e.baseSize)} → {fmtSize(e.newSize)}
							{:else}
								{fmtSize(e.baseSize)}
							{/if}
						</span>
						<span class="text-xs font-mono text-gray-400 w-28 text-right">
							{#if e.action === 'replace' && e.newHash}
								{shortHash(e.baseHash)}→{shortHash(e.newHash).slice(-4)}
							{:else}
								{shortHash(e.baseHash)}
							{/if}
						</span>
						<div class="flex gap-1">
							<button
								type="button"
								class="px-2 py-0.5 text-xs rounded border {e.action === 'keep'
									? 'bg-gray-100 border-gray-400'
									: 'bg-white hover:bg-gray-50'}"
								onclick={() => setAction(idx, 'keep')}>Keep</button
							>
							<button
								type="button"
								class="px-2 py-0.5 text-xs rounded border {e.action === 'replace'
									? 'bg-amber-100 border-amber-400'
									: 'bg-white hover:bg-gray-50'}"
								onclick={() => setAction(idx, 'replace')}>Replace…</button
							>
							<button
								type="button"
								class="px-2 py-0.5 text-xs rounded border {e.action === 'remove'
									? 'bg-red-100 border-red-400'
									: 'bg-white hover:bg-gray-50'}"
								onclick={() => setAction(idx, 'remove')}>{m.remove()}</button
							>
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if isSimpleCase && draftEntries.length === 1}
		<section class="border rounded p-3 bg-gray-50 text-sm">
			<div class="flex items-center gap-2">
				<i class="fa-solid fa-file text-gray-400"></i>
				<span class="flex-1 truncate">{draftEntries[0].name}</span>
				<span class="text-xs text-gray-500 tabular-nums">{fmtSize(draftEntries[0].baseSize)}</span>
				<button
					type="button"
					class="btn preset-tonal-surface btn-sm"
					onclick={() => setAction(0, 'replace')}>Replace…</button
				>
				<button
					type="button"
					class="btn preset-tonal-surface btn-sm"
					onclick={() => setAction(0, 'remove')}>{m.remove()}</button
				>
			</div>
			{#if draftEntries[0].action === 'replace' && draftEntries[0].newFile}
				<div class="mt-2 text-xs text-amber-700">
					Replacing with: <strong>{draftEntries[0].newFile.name}</strong>
					({fmtSize(draftEntries[0].newSize ?? 0)})
				</div>
			{:else if draftEntries[0].action === 'remove'}
				<div class="mt-2 text-xs text-red-700">Will be removed from this revision</div>
			{/if}
		</section>
	{/if}

	<section
		class="border-2 border-dashed rounded p-4 bg-gray-50"
		ondragover={(e) => e.preventDefault()}
		ondrop={onDrop}
		role="button"
		tabindex="0"
	>
		<div class="text-xs uppercase tracking-wide text-gray-600 mb-2 flex justify-between">
			<span>Add files</span>
			<span class="text-gray-400 normal-case">SHA-256 computed in your browser</span>
		</div>

		{#if additions.length > 0}
			<ul class="text-sm divide-y mb-2">
				{#each additions as a, idx}
					<li class="py-1 flex items-center gap-2">
						<span
							class="font-mono text-xs px-1.5 py-0.5 rounded border text-green-700 bg-green-50 border-green-200"
							>new</span
						>
						<i class="fa-solid fa-file text-gray-400"></i>
						<span class="flex-1 truncate">{a.name}</span>
						<span class="text-xs text-gray-500 tabular-nums">{fmtSize(a.size)}</span>
						<span class="text-xs font-mono text-gray-400">{shortHash(a.hash)}</span>
						<button
							type="button"
							class="text-gray-400 hover:text-red-600"
							onclick={() => (additions = additions.filter((_, i) => i !== idx))}>×</button
						>
					</li>
				{/each}
			</ul>
		{/if}

		{#if hashing.length > 0}
			<ul class="text-xs space-y-0.5 mb-2 border-t pt-2">
				{#each hashing as h}
					<li class="flex items-center gap-2 text-gray-600">
						{#if h.status === 'hashing'}
							<i class="fa-solid fa-spinner fa-spin text-blue-500"></i>
							<span>{h.name}</span><span class="text-gray-400">hashing…</span>
						{:else if h.status === 'duplicate'}
							<i class="fa-solid fa-equals text-gray-500"></i>
							<span>{h.name}</span>
							<span class="italic text-gray-500"
								>identical to inherited file → nothing to upload</span
							>
						{:else if h.status === 'replaced'}
							<i class="fa-solid fa-arrows-rotate text-amber-600"></i>
							<span>{h.name}</span>
							<span class="italic text-amber-700"
								>auto-promoted to Replace (same name, new content)</span
							>
						{:else if h.status.startsWith('error')}
							<i class="fa-solid fa-triangle-exclamation text-red-500"></i>
							<span>{h.name}</span><span class="text-red-700">{h.status}</span>
						{:else}
							<i class="fa-solid fa-check text-green-600"></i>
							<span>{h.name}</span>
							<span class="italic text-green-700">queued for upload</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}

		<button
			type="button"
			class="w-full text-center text-sm text-gray-500 py-3 hover:bg-gray-100 rounded"
			onclick={() => fileInput?.click()}
		>
			<i class="fa-solid fa-cloud-arrow-up text-2xl mb-1 block"></i>
			Drag files here or click to browse
		</button>
		<input
			bind:this={fileInput}
			type="file"
			multiple
			class="hidden"
			onchange={(e) => {
				const f = (e.currentTarget as HTMLInputElement).files;
				if (f) handleFiles(f);
			}}
		/>
	</section>

	<label class="block">
		<span class="text-xs uppercase tracking-wide text-gray-600">{m.observation()}</span>
		<textarea
			bind:value={observation}
			rows="2"
			class="mt-1 w-full border rounded px-2 py-1.5 text-sm input"
		></textarea>
	</label>

	<label class="block">
		<span class="text-xs uppercase tracking-wide text-gray-600">{m.link()}</span>
		<input
			type="url"
			bind:value={link}
			class="mt-1 w-full border rounded px-2 py-1.5 text-sm input"
			placeholder="https://…"
		/>
	</label>

	{#if finalFiles.length > 0}
		<div class="border rounded-lg bg-blue-50 border-blue-200 p-3 text-sm">
			<div class="font-semibold text-blue-900 mb-1">
				<i class="fa-solid fa-eye mr-1"></i>Preview of v{nextVersion}
			</div>
			<div class="text-xs text-gray-700">
				<strong>{finalFiles.length}</strong>
				{finalFiles.length === 1 ? m.file() : 'files'},
				<strong>{fmtSize(totalSize)}</strong>
			</div>
		</div>
	{/if}

	{#if error}
		<div class="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
			{error}
		</div>
	{/if}

	<div class="flex justify-end gap-2">
		<button type="button" class="btn preset-tonal-surface" onclick={() => onCancel?.()}>
			{m.cancel()}
		</button>
		<button
			type="button"
			disabled={submitting}
			class="btn preset-filled-primary-500"
			onclick={submit}
		>
			<i class="fa-solid fa-check mr-1"></i>
			{submitting ? 'Creating…' : `Create v${nextVersion}`}
		</button>
	</div>
</div>
