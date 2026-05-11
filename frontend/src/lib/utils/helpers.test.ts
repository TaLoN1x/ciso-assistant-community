import { describe, it, expect } from 'vitest';
import { getFieldVisibility, isFieldEditable, isFieldVisible } from './helpers';

// Convenience pairs — match the per-role shape `field_visibility` stores on
// the backend and ships to the frontend.
const EDIT = { auditor: 'edit', respondent: 'edit' };
const AUDITOR_ONLY = { auditor: 'edit', respondent: 'hidden' };
const HIDDEN = { auditor: 'hidden', respondent: 'hidden' };

function ca(overrides: Record<string, any> = {}) {
	return { field_visibility: overrides };
}

describe('getFieldVisibility', () => {
	it('exposes a show flag for every field the visibility editor knows about', () => {
		const flags = getFieldVisibility(ca(), 'auditor');
		// Every key that the per-CA editor surfaces must be reflected here, so
		// markup gating cannot accidentally miss one.
		expect(Object.keys(flags).sort()).toEqual(
			[
				'showAnswers',
				'showAppliedControls',
				'showComments',
				'showDocumentationScore',
				'showEvidences',
				'showExtendedResult',
				'showObservation',
				'showRespondentAlignment',
				'showResult',
				'showScore',
				'showStatus'
			].sort()
		);
	});

	it('respects explicit per-field overrides for the requested role', () => {
		const flags = getFieldVisibility(
			ca({
				score: { auditor: 'edit', respondent: 'hidden' },
				observation: { auditor: 'hidden', respondent: 'edit' }
			}),
			'respondent'
		);
		expect(flags.showScore).toBe(false);
		expect(flags.showObservation).toBe(true);
	});

	it('honours backend DEFAULT_VISIBILITY when it is baked into the CA payload', () => {
		// Backend `build_initial_field_visibility` seeds every CA with the
		// DEFAULT_VISIBILITY map at creation, so by the time the frontend sees
		// the CA these per-role pairs are already on the object.
		const seeded = ca({
			score: HIDDEN,
			is_scored: HIDDEN,
			documentation_score: HIDDEN,
			status: AUDITOR_ONLY,
			extended_result: AUDITOR_ONLY,
			respondent_alignment: HIDDEN
		});

		const respondent = getFieldVisibility(seeded, 'respondent');
		expect(respondent.showStatus).toBe(false);
		expect(respondent.showExtendedResult).toBe(false);
		expect(respondent.showScore).toBe(false);
		expect(respondent.showDocumentationScore).toBe(false);

		const auditor = getFieldVisibility(seeded, 'auditor');
		expect(auditor.showStatus).toBe(true);
		expect(auditor.showExtendedResult).toBe(true);
		// score/documentation_score are HIDDEN for both by default — auditors
		// only see them once the CA opts in.
		expect(auditor.showScore).toBe(false);
		expect(auditor.showDocumentationScore).toBe(false);
	});

	it('applies DEFAULT_VISIBILITY when the CA payload lacks a key', () => {
		// Regression: legacy CAs (or any payload missing the per-field pair)
		// must still hide `extended_result` / `status` from respondents, even
		// though the explicit override isn't in `field_visibility`. Without
		// this fallback the auditee-assessments page leaked `extended_result`.
		const empty = getFieldVisibility(ca(), 'respondent');
		expect(empty.showExtendedResult).toBe(false);
		expect(empty.showStatus).toBe(false);
		expect(empty.showScore).toBe(false);
		expect(empty.showDocumentationScore).toBe(false);
		expect(empty.showRespondentAlignment).toBe(false);

		const auditorEmpty = getFieldVisibility(ca(), 'auditor');
		expect(auditorEmpty.showExtendedResult).toBe(true);
		expect(auditorEmpty.showStatus).toBe(true);
		// score/documentation_score still HIDDEN for auditor by default.
		expect(auditorEmpty.showScore).toBe(false);
	});

	it('treats fields without an explicit override as visible to everyone', () => {
		// `answers` and `result` are not in DEFAULT_VISIBILITY, so they
		// resolve to EVERYONE_EDIT for both roles unless the CA opts out.
		const flags = getFieldVisibility(ca(), 'respondent');
		expect(flags.showAnswers).toBe(true);
		expect(flags.showResult).toBe(true);
	});

	it('hides answers when the CA explicitly sets answers to HIDDEN', () => {
		// Regression guard: this is the field whose visibility was silently
		// ignored across every editable surface before the audit fix.
		const flags = getFieldVisibility(ca({ answers: HIDDEN }), 'auditor');
		expect(flags.showAnswers).toBe(false);
	});

	it('reflects parent/child independence — status and result resolve separately', () => {
		// Regression guard for the table-mode bug where `status` was wrapped in
		// `showResult`. The two are independent fields with independent visibility.
		const flags = getFieldVisibility(ca({ status: AUDITOR_ONLY, result: EDIT }), 'respondent');
		expect(flags.showStatus).toBe(false);
		expect(flags.showResult).toBe(true);
	});

	it('treats a null/undefined complianceAssessment like an empty visibility map', () => {
		// A missing CA must not crash and must apply the same DEFAULT_VISIBILITY
		// fallback as an empty payload.
		const fromNull = getFieldVisibility(null, 'respondent');
		const fromUndefined = getFieldVisibility(undefined, 'respondent');
		const fromEmpty = getFieldVisibility(ca(), 'respondent');
		expect(fromNull).toEqual(fromEmpty);
		expect(fromUndefined).toEqual(fromEmpty);
		// answers / result aren't in DEFAULT_VISIBILITY — they still resolve
		// to EVERYONE_EDIT.
		expect(fromNull.showAnswers).toBe(true);
		expect(fromNull.showResult).toBe(true);
		// status / extended_result ARE in DEFAULT_VISIBILITY — they must be
		// hidden for respondents even with no CA payload.
		expect(fromNull.showExtendedResult).toBe(false);
		expect(fromNull.showStatus).toBe(false);
	});

	it('defaults the role argument to auditor', () => {
		// Verify the role default by checking a field where the two roles
		// diverge. With the CA seeding `status` as AUDITOR_ONLY, the implicit
		// call must mirror the auditor call (status visible).
		const seeded = ca({ status: AUDITOR_ONLY });
		const implicit = getFieldVisibility(seeded);
		const auditor = getFieldVisibility(seeded, 'auditor');
		const respondent = getFieldVisibility(seeded, 'respondent');
		expect(implicit).toEqual(auditor);
		expect(implicit.showStatus).toBe(true);
		expect(respondent.showStatus).toBe(false);
	});
});

describe('isFieldVisible / isFieldEditable', () => {
	it('treats `read` as visible but not editable', () => {
		const c = ca({ observation: { auditor: 'read', respondent: 'hidden' } });
		expect(isFieldVisible(c, 'observation', 'auditor')).toBe(true);
		expect(isFieldEditable(c, 'observation', 'auditor')).toBe(false);
		expect(isFieldVisible(c, 'observation', 'respondent')).toBe(false);
		expect(isFieldEditable(c, 'observation', 'respondent')).toBe(false);
	});

	it('treats `edit` as both visible and editable', () => {
		const c = ca({ score: { auditor: 'edit', respondent: 'edit' } });
		expect(isFieldVisible(c, 'score', 'auditor')).toBe(true);
		expect(isFieldEditable(c, 'score', 'auditor')).toBe(true);
		expect(isFieldVisible(c, 'score', 'respondent')).toBe(true);
		expect(isFieldEditable(c, 'score', 'respondent')).toBe(true);
	});

	it('treats `hidden` as neither visible nor editable', () => {
		const c = ca({ result: { auditor: 'hidden', respondent: 'hidden' } });
		expect(isFieldVisible(c, 'result', 'auditor')).toBe(false);
		expect(isFieldEditable(c, 'result', 'auditor')).toBe(false);
	});

	it('resolves a missing role within a pair to `edit`', () => {
		// Partial pair (only one role set) — the missing role is treated as
		// permissive ('edit'), matching the backend resolver's contract.
		const c = ca({ score: { auditor: 'edit' } as any });
		expect(isFieldVisible(c, 'score', 'respondent')).toBe(true);
		expect(isFieldEditable(c, 'score', 'respondent')).toBe(true);
	});
});
