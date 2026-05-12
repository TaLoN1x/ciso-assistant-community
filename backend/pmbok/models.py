from django.db import models
from iam.models import FolderMixin, PublishInRootFolderMixin
from core.models import (
    FilteringLabelMixin,
    FindingsAssessment,
    Policy,
    ComplianceAssessment,
    RiskAssessment,
    Evidence,
    SecurityException,
    Terminology,
)
from crq.models import QuantitativeRiskStudy
from ebios_rm.models import EbiosRMStudy
from tprm.models import Entity, EntityAssessment
from core.base_models import AbstractBaseModel, NameDescriptionMixin

from auditlog.registry import auditlog


class NameDescriptionFolderMixin(NameDescriptionMixin, FolderMixin):
    class Meta:
        abstract = True


class GenericCollection(NameDescriptionFolderMixin, FilteringLabelMixin):
    ref_id = models.CharField(max_length=100, blank=True)
    compliance_assessments = models.ManyToManyField(
        ComplianceAssessment,
        blank=True,
    )
    risk_assessments = models.ManyToManyField(
        RiskAssessment,
        blank=True,
    )
    crq_studies = models.ManyToManyField(
        QuantitativeRiskStudy,
        blank=True,
    )

    ebios_studies = models.ManyToManyField(
        EbiosRMStudy,
        blank=True,
    )
    entity_assessments = models.ManyToManyField(
        EntityAssessment,
        blank=True,
    )
    findings_assessments = models.ManyToManyField(
        FindingsAssessment,
        blank=True,
    )
    documents = models.ManyToManyField(
        Evidence,
        blank=True,
    )
    security_exceptions = models.ManyToManyField(
        SecurityException,
        blank=True,
    )

    policies = models.ManyToManyField(
        Policy,
        blank=True,
    )

    dependencies = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
    )


class Accreditation(NameDescriptionFolderMixin, FilteringLabelMixin):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("in_progress", "In progress"),
        ("accredited", "Accredited"),
        ("not_accredited", "Not Accredited"),
        ("obsolete", "Obsolete"),
    )
    CATEGORY_CHOICES = (
        ("accreditation_simplified", "accreditationSimplified"),
        ("accreditation_elaborated", "accreditationElaborated"),
        ("accreditation_advanced", "accreditationAdvanced"),
        ("accreditation_sensitive", "accreditationSensitive"),
        ("accreditation_restricted", "accreditationRestricted"),
        ("other", "Other"),
    )

    ref_id = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(
        Terminology,
        on_delete=models.PROTECT,
        related_name="accreditation_category",
        limit_choices_to={
            "field_path": Terminology.FieldPath.ACCREDITATION_CATEGORY,
            "is_visible": True,
        },
    )
    authority = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        related_name="accreditation_authority",
        null=True,
        blank=True,
        help_text="Accreditation authority entity",
    )
    authority_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Free-text authority name, for authorities not registered as entities",
    )
    status = models.ForeignKey(
        Terminology,
        on_delete=models.PROTECT,
        related_name="accreditation_status",
        limit_choices_to={
            "field_path": Terminology.FieldPath.ACCREDITATION_STATUS,
            "is_visible": True,
        },
    )

    author = models.ForeignKey(
        "core.Actor",
        on_delete=models.SET_NULL,
        null=True,
        related_name="authored_accreditations",
    )
    expiry_date = models.DateField(
        blank=True,
        null=True,
    )
    linked_collection = models.ForeignKey(
        GenericCollection, null=True, on_delete=models.SET_NULL
    )
    checklist = models.ForeignKey(
        ComplianceAssessment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accreditation_checklist",
    )
    commission_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of the accreditation commission decision",
    )
    duration_months = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Accreditation validity duration in months",
    )
    decision_evidence = models.ManyToManyField(
        Evidence,
        blank=True,
        related_name="accreditation_decisions",
        help_text="Evidence documents for the accreditation decision (e.g. minutes/PV)",
    )
    observation = models.TextField(verbose_name="Observation", blank=True, null=True)


class ResponsibilityRole(NameDescriptionFolderMixin, PublishInRootFolderMixin):
    """A single role in a responsibility taxonomy (e.g. 'Responsible' in RACI).

    Multiple taxonomies (RACI, RASCI, RAPID, custom) coexist; a ResponsibilityMatrix
    references the subset of roles it uses through its `roles` M2M.
    """

    class Taxonomy(models.TextChoices):
        RACI = "raci", "RACI"
        RASCI = "rasci", "RASCI"
        RAPID = "rapid", "RAPID"
        CUSTOM = "custom", "Custom"

    is_published = models.BooleanField(default=True)
    code = models.CharField(
        max_length=8,
        help_text="Short letter shown in matrix cells (e.g. 'R', 'A', 'C', 'I')",
    )
    color = models.CharField(max_length=20, blank=True)
    order = models.PositiveIntegerField(default=0)
    taxonomy = models.CharField(
        max_length=20,
        choices=Taxonomy.choices,
        default=Taxonomy.CUSTOM,
        help_text="Which responsibility taxonomy this role belongs to",
    )
    builtin = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    translations = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        ordering = ["taxonomy", "order", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ResponsibilityMatrix(NameDescriptionFolderMixin, FilteringLabelMixin):
    """A folder-scoped responsibility matrix (RACI / RASCI / RAPID / custom).

    The `roles` M2M is the authoritative scope of role options available to
    activities within this matrix.
    """

    class Preset(models.TextChoices):
        RACI = "raci", "RACI"
        RASCI = "rasci", "RASCI"
        RAPID = "rapid", "RAPID"
        CUSTOM = "custom", "Custom"

    ref_id = models.CharField(max_length=100, blank=True)
    preset = models.CharField(
        max_length=20,
        choices=Preset.choices,
        default=Preset.RACI,
    )
    roles = models.ManyToManyField(
        ResponsibilityRole,
        related_name="matrices",
        blank=True,
    )


class ResponsibilityActivity(AbstractBaseModel, FolderMixin):
    """A row in a responsibility matrix: the thing being done."""

    matrix = models.ForeignKey(
        ResponsibilityMatrix,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        # Inherit folder from parent matrix so IAM scoping can place this object
        self.folder = self.matrix.folder
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ResponsibilityMatrixActor(AbstractBaseModel, FolderMixin):
    """An actor attached to a matrix (a matrix column), with display order.

    Promotes actor-on-matrix to a first-class concept so columns can be added,
    removed, and reordered independently of any concrete assignment.
    """

    matrix = models.ForeignKey(
        ResponsibilityMatrix,
        on_delete=models.CASCADE,
        related_name="matrix_actors",
    )
    actor = models.ForeignKey(
        "core.Actor",
        on_delete=models.CASCADE,
        related_name="matrix_memberships",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "actor"],
                name="unique_matrix_actor",
            )
        ]

    def save(self, *args, **kwargs):
        self.folder = self.matrix.folder
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.actor} in {self.matrix.name}"


class ResponsibilityAssignment(AbstractBaseModel, FolderMixin):
    """A single cell: (activity, actor) -> role. One role per cell."""

    activity = models.ForeignKey(
        ResponsibilityActivity,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    actor = models.ForeignKey(
        "core.Actor",
        on_delete=models.CASCADE,
        related_name="responsibility_assignments",
    )
    role = models.ForeignKey(
        ResponsibilityRole,
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "actor"],
                name="unique_responsibility_cell",
            )
        ]

    def save(self, *args, **kwargs):
        self.folder = self.activity.matrix.folder
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.actor} = {self.role.code} for {self.activity.name}"


common_exclude = ["created_at", "updated_at"]
auditlog.register(
    GenericCollection,
    exclude_fields=common_exclude,
)
auditlog.register(
    Accreditation,
    exclude_fields=common_exclude,
)
auditlog.register(
    ResponsibilityRole,
    exclude_fields=common_exclude,
)
auditlog.register(
    ResponsibilityMatrix,
    exclude_fields=common_exclude,
)
auditlog.register(
    ResponsibilityActivity,
    exclude_fields=common_exclude,
)
auditlog.register(
    ResponsibilityMatrixActor,
    exclude_fields=common_exclude,
)
auditlog.register(
    ResponsibilityAssignment,
    exclude_fields=common_exclude,
)
