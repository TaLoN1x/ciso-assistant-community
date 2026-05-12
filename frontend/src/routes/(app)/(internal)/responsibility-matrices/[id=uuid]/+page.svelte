<script lang="ts">
	import DetailView from '$lib/components/DetailView/DetailView.svelte';
	import {
		getModalStore,
		type ModalSettings,
		type ModalStore
	} from '$lib/components/Modals/stores';
	import { invalidateAll } from '$app/navigation';
	import { m } from '$paraglide/messages';
	import type { PageData } from './$types';

	interface Role {
		id: string;
		code: string;
		name: string;
		color?: string;
		order?: number;
	}
	interface Activity {
		id: string;
		name: string;
		description?: string;
		order: number;
	}
	interface MatrixActor {
		id: string;
		actor: { id: string; str: string };
		order: number;
	}
	interface Assignment {
		id: string;
		activity: { id: string };
		actor: { id: string };
		role: Role;
	}

	let { data }: { data: PageData } = $props();
	const modalStore: ModalStore = getModalStore();

	const matrix = $derived(data.data);
	const matrixId = $derived(matrix.id);
	const roles = $derived((matrix.roles ?? []) as Role[]);
	const sortedRoles = $derived([...roles].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)));

	let activities = $state<Activity[]>([]);
	let matrixActors = $state<MatrixActor[]>([]);
	let assignments = $state<Assignment[]>([]);
	let allActors = $state<Array<{ id: string; str: string }>>([]);

	$effect(() => {
		activities = (data.activities ?? []) as Activity[];
		matrixActors = (data.matrixActors ?? []) as MatrixActor[];
		assignments = (data.assignments ?? []) as Assignment[];
		allActors = (data.allActors ?? []) as Array<{ id: string; str: string }>;
	});

	const availableActors = $derived(
		allActors.filter((a) => !matrixActors.some((ma) => ma.actor.id === a.id))
	);

	const cellMap = $derived.by(() => {
		const idx = new Map<string, Assignment>();
		for (const a of assignments) idx.set(`${a.activity.id}::${a.actor.id}`, a);
		return idx;
	});

	// Per-role counts used in the legend
	const roleCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const a of assignments) counts[a.role.id] = (counts[a.role.id] ?? 0) + 1;
		return counts;
	});

	// Per-actor counts for column header badges
	const actorCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const a of assignments) counts[a.actor.id] = (counts[a.actor.id] ?? 0) + 1;
		return counts;
	});

	const filledCount = $derived(assignments.length);
	const gridTotal = $derived(activities.length * matrixActors.length);

	let newActivityName = $state('');
	let actorPickerValue = $state<string | undefined>(undefined);

	let editingActivityId = $state<string | null>(null);
	let editingName = $state('');

	let draggedActivityId = $state<string | null>(null);
	let draggedActorId = $state<string | null>(null);
	let dragOverActivityId = $state<string | null>(null);
	let dragOverActorId = $state<string | null>(null);

	async function ops(action: string, body: Record<string, unknown> = {}): Promise<any> {
		const res = await fetch(`/responsibility-matrices/${matrixId}/ops?action=${action}`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});
		if (!res.ok) {
			const data = await res.json().catch(() => ({}));
			console.error('ops failed', action, data);
			throw new Error(data?.detail ?? 'request failed');
		}
		if (res.status === 204) return null;
		return res.json();
	}

	async function createActivity() {
		const name = newActivityName.trim();
		if (!name) return;
		const order = activities.length;
		try {
			const created = await ops('create-activity', { name, order });
			activities = [...activities, created];
			newActivityName = '';
		} catch (e) {
			console.error(e);
		}
	}

	function startRename(activity: Activity) {
		editingActivityId = activity.id;
		editingName = activity.name;
	}

	async function commitRename() {
		if (!editingActivityId) return;
		const id = editingActivityId;
		const name = editingName.trim();
		editingActivityId = null;
		if (!name) return;
		try {
			await ops('update-activity', { id, name });
			activities = activities.map((a) => (a.id === id ? { ...a, name } : a));
		} catch (e) {
			console.error(e);
		}
	}

	function cancelRename() {
		editingActivityId = null;
		editingName = '';
	}

	async function deleteActivity(activity: Activity) {
		const confirmed = await new Promise<boolean>((resolve) => {
			const modal: ModalSettings = {
				type: 'confirm',
				title: m.confirmDeleteTitle?.() ?? 'Delete',
				body:
					m.areYouSureToDeleteObject?.({ object: activity.name }) ??
					`Delete "${activity.name}"?`,
				response: (r: boolean) => resolve(r)
			};
			modalStore.trigger(modal);
		});
		if (!confirmed) return;
		try {
			await ops('delete-activity', { id: activity.id });
			activities = activities.filter((a) => a.id !== activity.id);
			assignments = assignments.filter((x) => x.activity.id !== activity.id);
		} catch (e) {
			console.error(e);
		}
	}

	async function addActor() {
		if (!actorPickerValue) return;
		const actorId = actorPickerValue;
		if (matrixActors.some((ma) => ma.actor.id === actorId)) {
			actorPickerValue = undefined;
			return;
		}
		const order = matrixActors.length;
		try {
			const created = await ops('create-actor', { actor: actorId, order });
			const actorObj = allActors.find((a) => a.id === actorId) ?? { id: actorId, str: '' };
			matrixActors = [
				...matrixActors,
				{ id: created.id, actor: actorObj, order: created.order ?? order }
			];
			actorPickerValue = undefined;
		} catch (e) {
			console.error(e);
		}
	}

	async function removeActor(ma: MatrixActor) {
		const hasAssignments = assignments.some((a) => a.actor.id === ma.actor.id);
		const body = hasAssignments
			? `Remove ${ma.actor.str}? Existing cells for this actor will be cleared.`
			: `Remove ${ma.actor.str}?`;
		const confirmed = await new Promise<boolean>((resolve) => {
			const modal: ModalSettings = {
				type: 'confirm',
				title: 'Remove actor',
				body,
				response: (r: boolean) => resolve(r)
			};
			modalStore.trigger(modal);
		});
		if (!confirmed) return;
		try {
			await ops('delete-actor', { id: ma.id });
			matrixActors = matrixActors.filter((x) => x.id !== ma.id);
			assignments = assignments.filter((x) => x.actor.id !== ma.actor.id);
		} catch (e) {
			console.error(e);
		}
	}

	async function cycleCell(activity: Activity, actor: { id: string }, e: MouseEvent) {
		const direction = e.shiftKey ? 'backward' : 'forward';
		try {
			const result = await ops('cycle-cell', {
				activity: activity.id,
				actor: actor.id,
				direction
			});
			const existing = assignments.find(
				(a) => a.activity.id === activity.id && a.actor.id === actor.id
			);
			if (result.role === null) {
				assignments = assignments.filter(
					(a) => !(a.activity.id === activity.id && a.actor.id === actor.id)
				);
			} else if (existing) {
				assignments = assignments.map((a) =>
					a.activity.id === activity.id && a.actor.id === actor.id
						? { ...a, role: result.role }
						: a
				);
			} else {
				assignments = [
					...assignments,
					{
						id: crypto.randomUUID(),
						activity: { id: activity.id },
						actor: { id: actor.id },
						role: result.role
					}
				];
			}
		} catch (e) {
			console.error(e);
		}
	}

	function actDragStart(id: string) {
		draggedActivityId = id;
	}
	function actDragOver(e: DragEvent, id?: string) {
		e.preventDefault();
		if (id !== undefined) dragOverActivityId = id;
	}
	function actDragLeave(id: string) {
		if (dragOverActivityId === id) dragOverActivityId = null;
	}
	async function actDrop(e: DragEvent, targetId: string) {
		e.preventDefault();
		dragOverActivityId = null;
		if (!draggedActivityId || draggedActivityId === targetId) return;
		const fromIdx = activities.findIndex((a) => a.id === draggedActivityId);
		const toIdx = activities.findIndex((a) => a.id === targetId);
		if (fromIdx < 0 || toIdx < 0) return;
		const next = [...activities];
		const [moved] = next.splice(fromIdx, 1);
		next.splice(toIdx, 0, moved);
		activities = next.map((a, i) => ({ ...a, order: i }));
		draggedActivityId = null;
		try {
			await ops('reorder-activities', { ids: activities.map((a) => a.id) });
		} catch (e) {
			console.error(e);
			await invalidateAll();
		}
	}

	function actorDragStart(id: string) {
		draggedActorId = id;
	}
	function actorDragOver(e: DragEvent, id: string) {
		e.preventDefault();
		dragOverActorId = id;
	}
	function actorDragLeave(id: string) {
		if (dragOverActorId === id) dragOverActorId = null;
	}
	async function actorDrop(e: DragEvent, targetId: string) {
		e.preventDefault();
		dragOverActorId = null;
		if (!draggedActorId || draggedActorId === targetId) return;
		const fromIdx = matrixActors.findIndex((a) => a.id === draggedActorId);
		const toIdx = matrixActors.findIndex((a) => a.id === targetId);
		if (fromIdx < 0 || toIdx < 0) return;
		const next = [...matrixActors];
		const [moved] = next.splice(fromIdx, 1);
		next.splice(toIdx, 0, moved);
		matrixActors = next.map((a, i) => ({ ...a, order: i }));
		draggedActorId = null;
		try {
			await ops('reorder-actors', { ids: matrixActors.map((a) => a.id) });
		} catch (e) {
			console.error(e);
			await invalidateAll();
		}
	}

	// Mix a role color with the surface to get a soft cell background.
	function tint(color: string | undefined, amount = 14): string {
		if (!color) return 'transparent';
		return `color-mix(in oklch, ${color} ${amount}%, transparent)`;
	}
</script>

<DetailView {data} />

<section class="matrix-frame mt-4">
	<header class="matrix-header">
		<div class="matrix-title">
			<span class="matrix-eyebrow">
				<i class="fa-solid fa-table-cells-large"></i>
				<span>{matrix.preset?.toUpperCase?.() ?? 'RACI'}</span>
				<span class="matrix-eyebrow-dot"></span>
				<span>{matrix.folder?.str ?? ''}</span>
			</span>
			<h2 class="matrix-name">{m.responsibilityMatrix()}</h2>
			<div class="matrix-stats">
				<span class="stat"><b>{activities.length}</b> {m.responsibilityActivities()}</span>
				<span class="stat-sep">/</span>
				<span class="stat"><b>{matrixActors.length}</b> actors</span>
				<span class="stat-sep">/</span>
				<span class="stat"><b>{filledCount}</b><span class="stat-faint">/{gridTotal || 0}</span> cells filled</span>
			</div>
		</div>

		<div class="actor-picker">
			<i class="fa-solid fa-user-plus picker-icon"></i>
			<select class="picker-select" bind:value={actorPickerValue}>
				<option value={undefined}>{m.addActor?.() ?? 'Add actor…'}</option>
				{#each availableActors as a (a.id)}
					<option value={a.id}>{a.str}</option>
				{/each}
			</select>
			<button
				class="picker-btn"
				onclick={addActor}
				disabled={!actorPickerValue}
				aria-label="Add actor to matrix"
			>
				<i class="fa-solid fa-arrow-right"></i>
			</button>
		</div>
	</header>

	{#if activities.length === 0 && matrixActors.length === 0}
		<div class="empty-state">
			<i class="fa-solid fa-table-cells-large"></i>
			<p class="empty-title">This matrix is empty</p>
			<p class="empty-hint">Add an actor on the right, then add activities below.</p>
		</div>
	{:else}
		<div class="matrix-scroll">
			<table class="matrix-table">
				<thead>
					<tr>
						<th class="col-activity">
							<span class="col-label">{m.responsibilityActivity()}</span>
						</th>
						{#each matrixActors as ma (ma.id)}
							<th
								class="col-actor"
								class:drag-over={dragOverActorId === ma.id}
								class:dragging={draggedActorId === ma.id}
								draggable="true"
								ondragstart={() => actorDragStart(ma.id)}
								ondragover={(e) => actorDragOver(e, ma.id)}
								ondragleave={() => actorDragLeave(ma.id)}
								ondrop={(e) => actorDrop(e, ma.id)}
							>
								<div class="actor-header">
									<span class="actor-grip" title="Drag to reorder">
										<i class="fa-solid fa-grip"></i>
									</span>
									<span class="actor-name" title={ma.actor.str}>{ma.actor.str}</span>
									<button
										class="actor-remove"
										onclick={() => removeActor(ma)}
										aria-label="Remove actor"
										title="Remove from matrix"
									>
										<i class="fa-solid fa-xmark"></i>
									</button>
									{#if actorCounts[ma.actor.id]}
										<span class="actor-count" title="Assignments">{actorCounts[ma.actor.id]}</span>
									{/if}
								</div>
							</th>
						{/each}
						<th class="col-spacer"></th>
					</tr>
				</thead>
				<tbody>
					{#each activities as activity, rowIdx (activity.id)}
						<tr
							class="row-activity"
							class:drag-over={dragOverActivityId === activity.id}
							class:dragging={draggedActivityId === activity.id}
							ondragover={(e) => actDragOver(e, activity.id)}
							ondragleave={() => actDragLeave(activity.id)}
							ondrop={(e) => actDrop(e, activity.id)}
						>
							<td
								class="cell-activity"
								draggable="true"
								ondragstart={() => actDragStart(activity.id)}
							>
								<div class="activity-row">
									<span class="row-index">{rowIdx + 1}</span>
									<span class="activity-grip" title="Drag to reorder">
										<i class="fa-solid fa-grip-vertical"></i>
									</span>
									{#if editingActivityId === activity.id}
										<input
											type="text"
											class="activity-input"
											bind:value={editingName}
											onblur={commitRename}
											onkeydown={(e) => {
												if (e.key === 'Enter') commitRename();
												if (e.key === 'Escape') cancelRename();
											}}
										/>
									{:else}
										<button
											type="button"
											class="activity-name"
											onclick={() => startRename(activity)}
											title="Click to rename"
										>
											{activity.name}
										</button>
									{/if}
									<button
										class="activity-delete"
										onclick={() => deleteActivity(activity)}
										aria-label="Delete activity"
										title="Delete activity"
									>
										<i class="fa-solid fa-trash-can"></i>
									</button>
								</div>
							</td>
							{#each matrixActors as ma (ma.id)}
								{@const cell = cellMap.get(`${activity.id}::${ma.actor.id}`)}
								<td class="cell" style:background-color={cell ? tint(cell.role.color, 9) : 'transparent'}>
									<button
										class="cell-btn"
										class:filled={!!cell}
										style:--role-color={cell?.role?.color || '#94a3b8'}
										onclick={(e) => cycleCell(activity, ma.actor, e)}
										title={cell
											? `${cell.role.name} — click to cycle, shift-click to reverse`
											: 'Click to assign first role'}
									>
										{#if cell}
											<span class="cell-letter">{cell.role.code}</span>
										{:else}
											<span class="cell-dot"></span>
										{/if}
									</button>
								</td>
							{/each}
							<td class="col-spacer"></td>
						</tr>
					{/each}
					<tr class="row-add">
						<td class="cell-activity">
							<div class="add-row">
								<span class="add-prefix">
									<i class="fa-solid fa-plus"></i>
								</span>
								<input
									type="text"
									class="add-input"
									placeholder="{m.addResponsibilityActivity()}…"
									bind:value={newActivityName}
									onkeydown={(e) => e.key === 'Enter' && createActivity()}
								/>
								<button
									class="add-hint"
									onclick={createActivity}
									aria-label={m.addResponsibilityActivity()}
								>
									<kbd class="kbd">⏎</kbd>
								</button>
							</div>
						</td>
						{#each matrixActors as ma (ma.id)}
							<td class="cell cell-placeholder"></td>
						{/each}
						<td class="col-spacer"></td>
					</tr>
				</tbody>
			</table>
		</div>

		<footer class="matrix-legend">
			<span class="legend-label">{m.roles()}</span>
			{#each sortedRoles as r (r.id)}
				<span class="legend-chip" style:--role-color={r.color || '#6b7280'}>
					<span class="legend-letter">{r.code}</span>
					<span class="legend-name">{r.name}</span>
					{#if roleCounts[r.id]}
						<span class="legend-count">{roleCounts[r.id]}</span>
					{/if}
				</span>
			{/each}
			<span class="legend-spacer"></span>
			<span class="legend-tip">
				<kbd class="kbd">click</kbd> to cycle ·
				<kbd class="kbd">⇧ click</kbd> to reverse
			</span>
		</footer>
	{/if}
</section>

<style>
	/* ----- Frame -------------------------------------------------------- */
	.matrix-frame {
		position: relative;
		background: linear-gradient(
			180deg,
			color-mix(in oklch, var(--color-surface-100) 60%, transparent) 0%,
			var(--color-surface-50) 60%
		);
		border: 1px solid color-mix(in oklch, var(--color-surface-300) 70%, transparent);
		border-radius: 0.75rem;
		box-shadow:
			0 1px 0 color-mix(in oklch, var(--color-surface-950) 4%, transparent),
			0 0 0 1px color-mix(in oklch, var(--color-surface-950) 2%, transparent);
		overflow: hidden;
	}

	:global(.dark) .matrix-frame {
		background: linear-gradient(
			180deg,
			color-mix(in oklch, var(--color-surface-800) 70%, transparent) 0%,
			var(--color-surface-900) 60%
		);
		border-color: color-mix(in oklch, var(--color-surface-700) 80%, transparent);
	}

	/* ----- Header ------------------------------------------------------- */
	.matrix-header {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 2rem;
		padding: 1.25rem 1.5rem 1rem;
		border-bottom: 1px solid color-mix(in oklch, var(--color-surface-300) 60%, transparent);
	}
	:global(.dark) .matrix-header {
		border-bottom-color: color-mix(in oklch, var(--color-surface-700) 70%, transparent);
	}

	.matrix-title {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		min-width: 0;
	}

	.matrix-eyebrow {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--color-primary-600);
	}
	.matrix-eyebrow :global(i) {
		font-size: 0.85rem;
	}
	.matrix-eyebrow-dot {
		width: 3px;
		height: 3px;
		border-radius: 50%;
		background: currentColor;
		opacity: 0.5;
	}

	.matrix-name {
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: -0.015em;
		color: var(--color-surface-950);
		line-height: 1.15;
	}
	:global(.dark) .matrix-name {
		color: var(--color-surface-50);
	}

	.matrix-stats {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 0.75rem;
		color: var(--color-surface-600);
		font-variant-numeric: tabular-nums;
	}
	.matrix-stats b {
		font-weight: 700;
		color: var(--color-surface-900);
	}
	:global(.dark) .matrix-stats b {
		color: var(--color-surface-100);
	}
	.stat-sep {
		opacity: 0.4;
	}
	.stat-faint {
		opacity: 0.5;
		font-weight: 400;
	}

	/* ----- Actor picker ------------------------------------------------- */
	.actor-picker {
		display: flex;
		align-items: stretch;
		min-width: 280px;
		background: var(--color-surface-50);
		border: 1px solid var(--color-surface-300);
		border-radius: 0.5rem;
		overflow: hidden;
		transition: border-color 0.15s ease;
	}
	.actor-picker:focus-within {
		border-color: var(--color-primary-500);
		box-shadow: 0 0 0 3px color-mix(in oklch, var(--color-primary-500) 18%, transparent);
	}
	:global(.dark) .actor-picker {
		background: var(--color-surface-800);
		border-color: var(--color-surface-700);
	}
	.picker-icon {
		display: grid;
		place-items: center;
		padding: 0 0.65rem;
		color: var(--color-surface-500);
		font-size: 0.85rem;
	}
	.picker-select {
		flex: 1;
		border: 0;
		outline: 0;
		background: transparent;
		font-size: 0.85rem;
		padding: 0.5rem 0.25rem;
		min-width: 0;
		color: inherit;
	}
	.picker-btn {
		padding: 0 0.85rem;
		background: var(--color-primary-500);
		color: white;
		border: 0;
		font-size: 0.8rem;
		cursor: pointer;
		transition: background 0.15s ease;
	}
	.picker-btn:hover:not(:disabled) {
		background: var(--color-primary-600);
	}
	.picker-btn:disabled {
		background: var(--color-surface-300);
		cursor: not-allowed;
	}
	:global(.dark) .picker-btn:disabled {
		background: var(--color-surface-700);
	}

	/* ----- Empty state -------------------------------------------------- */
	.empty-state {
		padding: 4rem 2rem;
		text-align: center;
		color: var(--color-surface-500);
	}
	.empty-state i {
		font-size: 2rem;
		opacity: 0.5;
		margin-bottom: 1rem;
	}
	.empty-title {
		font-weight: 600;
		font-size: 1rem;
		color: var(--color-surface-700);
		margin-bottom: 0.25rem;
	}
	:global(.dark) .empty-title {
		color: var(--color-surface-200);
	}
	.empty-hint {
		font-size: 0.85rem;
	}

	/* ----- Table -------------------------------------------------------- */
	.matrix-scroll {
		overflow-x: auto;
		overflow-y: visible;
	}
	.matrix-table {
		border-collapse: separate;
		border-spacing: 0;
		width: 100%;
		font-size: 0.85rem;
	}

	.matrix-table thead th {
		position: sticky;
		top: 0;
		background: color-mix(in oklch, var(--color-surface-100) 75%, transparent);
		backdrop-filter: blur(8px);
		padding: 0.5rem 0.5rem 0.6rem;
		font-weight: 500;
		text-align: center;
		border-bottom: 1px solid var(--color-surface-300);
	}
	:global(.dark) .matrix-table thead th {
		background: color-mix(in oklch, var(--color-surface-800) 75%, transparent);
		border-bottom-color: var(--color-surface-700);
	}

	.col-activity {
		position: sticky;
		left: 0;
		z-index: 3;
		min-width: 20rem;
		text-align: left !important;
		padding: 0.65rem 1rem !important;
		background: color-mix(in oklch, var(--color-surface-100) 90%, transparent) !important;
		box-shadow: 1px 0 0 var(--color-surface-300);
	}
	:global(.dark) .col-activity {
		background: color-mix(in oklch, var(--color-surface-800) 90%, transparent) !important;
		box-shadow: 1px 0 0 var(--color-surface-700);
	}
	.col-label {
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-surface-600);
	}

	.col-actor {
		min-width: 8.5rem;
		max-width: 12rem;
		cursor: move;
		transition: background 0.15s ease;
	}
	.col-actor.drag-over {
		background: color-mix(in oklch, var(--color-primary-500) 14%, transparent) !important;
		box-shadow: inset 0 -2px 0 var(--color-primary-500);
	}
	.col-actor.dragging {
		opacity: 0.4;
	}
	.actor-header {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		position: relative;
	}
	.actor-grip {
		font-size: 0.65rem;
		color: var(--color-surface-400);
		opacity: 0;
		transition: opacity 0.15s ease;
	}
	.col-actor:hover .actor-grip {
		opacity: 1;
	}
	.actor-name {
		font-size: 0.78rem;
		font-weight: 500;
		color: var(--color-surface-800);
		line-height: 1.2;
		max-width: 9rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	:global(.dark) .actor-name {
		color: var(--color-surface-100);
	}
	.actor-remove {
		position: absolute;
		top: -0.35rem;
		right: -0.25rem;
		width: 1.1rem;
		height: 1.1rem;
		display: grid;
		place-items: center;
		font-size: 0.65rem;
		color: var(--color-surface-500);
		background: var(--color-surface-100);
		border: 1px solid var(--color-surface-300);
		border-radius: 50%;
		opacity: 0;
		transform: scale(0.85);
		transition: opacity 0.15s ease, transform 0.15s ease, color 0.15s ease;
		cursor: pointer;
	}
	:global(.dark) .actor-remove {
		background: var(--color-surface-800);
		border-color: var(--color-surface-600);
	}
	.col-actor:hover .actor-remove {
		opacity: 1;
		transform: scale(1);
	}
	.actor-remove:hover {
		color: white;
		background: var(--color-error-500, #ef4444);
		border-color: var(--color-error-500, #ef4444);
	}
	.actor-count {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.65rem;
		font-weight: 600;
		color: var(--color-surface-500);
		font-variant-numeric: tabular-nums;
	}

	.col-spacer {
		width: 1rem;
	}

	/* ----- Activity rows ----------------------------------------------- */
	.row-activity {
		transition: background 0.12s ease;
	}
	.row-activity.drag-over .cell-activity {
		box-shadow: 1px 0 0 var(--color-surface-300), inset 0 2px 0 var(--color-primary-500);
	}
	.row-activity.dragging {
		opacity: 0.4;
	}
	.row-activity:hover .cell {
		background-color: color-mix(in oklch, var(--color-surface-200) 40%, transparent);
	}
	.row-activity:hover .cell[style*='background-color'] {
		/* Preserve the role tint when the row is hovered for filled cells */
	}
	:global(.dark) .row-activity:hover .cell {
		background-color: color-mix(in oklch, var(--color-surface-700) 30%, transparent);
	}
	.row-activity:hover .cell-activity {
		background: color-mix(in oklch, var(--color-surface-100) 75%, transparent);
	}
	:global(.dark) .row-activity:hover .cell-activity {
		background: color-mix(in oklch, var(--color-surface-800) 75%, transparent);
	}

	.cell-activity {
		position: sticky;
		left: 0;
		z-index: 2;
		background: var(--color-surface-50);
		padding: 0.45rem 0.75rem;
		border-bottom: 1px solid color-mix(in oklch, var(--color-surface-200) 80%, transparent);
		box-shadow: 1px 0 0 var(--color-surface-200);
	}
	:global(.dark) .cell-activity {
		background: var(--color-surface-900);
		border-bottom-color: color-mix(in oklch, var(--color-surface-700) 80%, transparent);
		box-shadow: 1px 0 0 var(--color-surface-700);
	}

	.activity-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.row-index {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--color-surface-400);
		font-variant-numeric: tabular-nums;
		min-width: 1.5rem;
		text-align: right;
	}
	.activity-grip {
		color: var(--color-surface-400);
		font-size: 0.85rem;
		cursor: grab;
		opacity: 0;
		transition: opacity 0.15s ease;
	}
	.row-activity:hover .activity-grip {
		opacity: 1;
	}
	.activity-grip:active {
		cursor: grabbing;
	}
	.activity-name {
		flex: 1;
		text-align: left;
		background: transparent;
		border: 0;
		padding: 0.25rem 0.35rem;
		border-radius: 0.3rem;
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--color-surface-900);
		cursor: text;
		transition: background 0.12s ease;
	}
	:global(.dark) .activity-name {
		color: var(--color-surface-100);
	}
	.activity-name:hover {
		background: color-mix(in oklch, var(--color-primary-500) 8%, transparent);
	}
	.activity-input {
		flex: 1;
		padding: 0.25rem 0.35rem;
		border: 1px solid var(--color-primary-500);
		border-radius: 0.3rem;
		font-size: 0.9rem;
		font-weight: 500;
		background: var(--color-surface-50);
		outline: 0;
		box-shadow: 0 0 0 3px color-mix(in oklch, var(--color-primary-500) 18%, transparent);
	}
	:global(.dark) .activity-input {
		background: var(--color-surface-800);
		color: var(--color-surface-50);
	}
	.activity-delete {
		width: 1.4rem;
		height: 1.4rem;
		display: grid;
		place-items: center;
		color: var(--color-surface-400);
		background: transparent;
		border: 0;
		border-radius: 0.25rem;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s ease, color 0.15s ease, background 0.15s ease;
	}
	.row-activity:hover .activity-delete {
		opacity: 1;
	}
	.activity-delete:hover {
		color: var(--color-error-500, #ef4444);
		background: color-mix(in oklch, var(--color-error-500, #ef4444) 12%, transparent);
	}

	/* ----- Cells -------------------------------------------------------- */
	.cell {
		padding: 0.35rem;
		text-align: center;
		border-bottom: 1px solid color-mix(in oklch, var(--color-surface-200) 60%, transparent);
		border-right: 1px solid color-mix(in oklch, var(--color-surface-200) 40%, transparent);
		transition: background-color 0.12s ease;
	}
	:global(.dark) .cell {
		border-bottom-color: color-mix(in oklch, var(--color-surface-700) 60%, transparent);
		border-right-color: color-mix(in oklch, var(--color-surface-700) 40%, transparent);
	}

	.cell-btn {
		--role-color: var(--color-surface-400);
		position: relative;
		width: 2.25rem;
		height: 2.25rem;
		display: inline-grid;
		place-items: center;
		border-radius: 0.45rem;
		background: transparent;
		border: 1.5px dashed transparent;
		color: white;
		cursor: pointer;
		transition:
			background-color 0.15s ease,
			border-color 0.15s ease,
			transform 0.1s ease,
			box-shadow 0.15s ease;
	}
	.cell-btn:hover {
		border-color: color-mix(in oklch, var(--role-color) 50%, transparent);
		transform: scale(1.05);
	}
	.cell-btn:active {
		transform: scale(0.95);
	}
	.cell-btn.filled {
		background: var(--role-color);
		border: 1.5px solid color-mix(in oklch, var(--role-color) 70%, black 12%);
		box-shadow:
			inset 0 1px 0 color-mix(in oklch, white 30%, transparent),
			0 1px 2px color-mix(in oklch, var(--role-color) 50%, transparent);
	}
	.cell-btn.filled:hover {
		transform: scale(1.08);
		box-shadow:
			inset 0 1px 0 color-mix(in oklch, white 35%, transparent),
			0 2px 8px color-mix(in oklch, var(--role-color) 60%, transparent);
	}
	.cell-letter {
		font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
		font-size: 0.85rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		line-height: 1;
		text-shadow: 0 1px 0 color-mix(in oklch, black 15%, transparent);
	}
	.cell-dot {
		width: 0.3rem;
		height: 0.3rem;
		border-radius: 50%;
		background: var(--color-surface-300);
		opacity: 0;
		transition: opacity 0.15s ease;
	}
	:global(.dark) .cell-dot {
		background: var(--color-surface-600);
	}
	.cell-btn:hover .cell-dot {
		opacity: 1;
	}

	.cell-placeholder {
		background: color-mix(in oklch, var(--color-surface-100) 30%, transparent);
	}
	:global(.dark) .cell-placeholder {
		background: color-mix(in oklch, var(--color-surface-800) 30%, transparent);
	}

	/* ----- Add row ------------------------------------------------------ */
	.row-add .cell-activity {
		background: transparent;
		border-bottom: 0;
	}
	:global(.dark) .row-add .cell-activity {
		background: transparent;
	}
	.add-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0;
	}
	.add-prefix {
		display: grid;
		place-items: center;
		width: 1.5rem;
		height: 1.5rem;
		color: var(--color-surface-400);
		font-size: 0.8rem;
	}
	.add-input {
		flex: 1;
		padding: 0.4rem 0.5rem;
		border: 1px dashed transparent;
		border-radius: 0.35rem;
		background: transparent;
		font-size: 0.88rem;
		color: var(--color-surface-900);
		outline: 0;
		transition: border-color 0.15s ease, background 0.15s ease;
	}
	:global(.dark) .add-input {
		color: var(--color-surface-100);
	}
	.add-input::placeholder {
		color: var(--color-surface-400);
		font-style: italic;
	}
	.add-input:hover {
		border-color: color-mix(in oklch, var(--color-surface-400) 60%, transparent);
	}
	.add-input:focus {
		border-style: solid;
		border-color: var(--color-primary-500);
		background: var(--color-surface-50);
		box-shadow: 0 0 0 3px color-mix(in oklch, var(--color-primary-500) 14%, transparent);
	}
	:global(.dark) .add-input:focus {
		background: var(--color-surface-800);
	}
	.add-hint {
		background: transparent;
		border: 0;
		opacity: 0;
		transition: opacity 0.15s ease;
		cursor: pointer;
	}
	.add-input:focus + .add-hint,
	.add-row:hover .add-hint {
		opacity: 1;
	}

	.kbd {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.65rem;
		padding: 0.1rem 0.4rem;
		background: var(--color-surface-100);
		border: 1px solid var(--color-surface-300);
		border-bottom-width: 2px;
		border-radius: 0.25rem;
		color: var(--color-surface-700);
		line-height: 1.4;
	}
	:global(.dark) .kbd {
		background: var(--color-surface-800);
		border-color: var(--color-surface-600);
		color: var(--color-surface-200);
	}

	/* ----- Legend ------------------------------------------------------- */
	.matrix-legend {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		flex-wrap: wrap;
		padding: 0.85rem 1.5rem;
		border-top: 1px solid color-mix(in oklch, var(--color-surface-300) 60%, transparent);
		background: color-mix(in oklch, var(--color-surface-100) 50%, transparent);
	}
	:global(.dark) .matrix-legend {
		border-top-color: color-mix(in oklch, var(--color-surface-700) 70%, transparent);
		background: color-mix(in oklch, var(--color-surface-800) 50%, transparent);
	}
	.legend-label {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-surface-500);
		margin-right: 0.25rem;
	}
	.legend-chip {
		--role-color: var(--color-surface-400);
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.2rem 0.6rem 0.2rem 0.25rem;
		background: var(--color-surface-50);
		border: 1px solid color-mix(in oklch, var(--role-color) 30%, var(--color-surface-300));
		border-radius: 9999px;
		font-size: 0.75rem;
		color: var(--color-surface-800);
		transition: transform 0.12s ease;
	}
	.legend-chip:hover {
		transform: translateY(-1px);
	}
	:global(.dark) .legend-chip {
		background: var(--color-surface-800);
		color: var(--color-surface-100);
	}
	.legend-letter {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.7rem;
		font-weight: 700;
		width: 1.15rem;
		height: 1.15rem;
		display: inline-grid;
		place-items: center;
		border-radius: 50%;
		background: var(--role-color);
		color: white;
		text-shadow: 0 1px 0 color-mix(in oklch, black 15%, transparent);
	}
	.legend-name {
		text-transform: capitalize;
	}
	.legend-count {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.65rem;
		font-weight: 700;
		color: var(--color-surface-500);
		font-variant-numeric: tabular-nums;
		padding-left: 0.35rem;
		border-left: 1px solid color-mix(in oklch, var(--color-surface-400) 50%, transparent);
	}
	.legend-spacer {
		flex: 1;
	}
	.legend-tip {
		font-size: 0.7rem;
		color: var(--color-surface-500);
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
</style>
