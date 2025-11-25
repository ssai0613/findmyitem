from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import uuid

# 1. ACCOUNTS
class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Staff'
        STUDENT = 'STUDENT', 'Student/Crew'

    class YearLevel(models.TextChoices):
        FIRST = '1st Year', 'First Year'
        SECOND = '2nd Year', 'Second Year'
        THIRD = '3rd Year', 'Third Year'
        FOURTH = '4th Year', 'Fourth Year'
        FIFTH = '5th Year', 'Fifth Year'
        SIXTH = '6th Year', 'Sixth Year'

    role = models.CharField(max_length=10, choices=Roles.choices, default=Roles.STUDENT)
    student_id = models.CharField(
        max_length=7, 
        blank=True, 
        null=True,
        validators=[RegexValidator(r'^\d{7}$', message='Student ID must be exactly 7 digits.')],
        help_text="Enter your 7-digit ID number."
    )
    program_year = models.CharField(max_length=20, choices=YearLevel.choices, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

# --- HARD CODED CATEGORIES ---
class ItemCategory(models.TextChoices):
    ELECTRONICS = 'ELECTRONICS', 'Electronics'
    CLOTHING = 'CLOTHING', 'Clothing'
    IDS = 'IDS', 'IDs & Cards'
    KEYS = 'KEYS', 'Keys'
    BOOKS = 'BOOKS', 'Books & Stationery'
    BAGS = 'BAGS', 'Bags & Wallets'
    TUMBLERS = 'TUMBLERS', 'Tumblers/Bottles'
    OTHERS = 'OTHERS', 'Others'

# 2. HAND-IN REPORTS
class HandInReport(models.Model):
    reference_code = models.CharField(max_length=12, unique=True, editable=False)
    finder_name = models.CharField(max_length=100, blank=True, null=True)
    finder_contact = models.CharField(max_length=50, blank=True, null=True)
    
    # CHANGED: Now using choices instead of ForeignKey
    category = models.CharField(max_length=50, choices=ItemCategory.choices, default=ItemCategory.OTHERS)
    
    item_name = models.CharField(max_length=100)
    description = models.TextField()
    color = models.CharField(max_length=30)
    date_reported = models.DateTimeField(auto_now_add=True)
    location_found = models.CharField(max_length=255)
    is_received = models.BooleanField(default=False)
    received_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = "HND-" + str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.item_name} ({self.reference_code})"

# 3. FOUND ITEMS
class FoundItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        CLAIMED = 'CLAIMED', 'Claimed'
        DONATED = 'DONATED', 'Donated/Disposed'

    hand_in_ref = models.OneToOneField(HandInReport, on_delete=models.SET_NULL, null=True, blank=True)
    registered_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, limit_choices_to={'role__in': ['ADMIN', 'STAFF']})
    
    # CHANGED
    category = models.CharField(max_length=50, choices=ItemCategory.choices)
    
    item_name = models.CharField(max_length=100)
    description = models.TextField()
    color = models.CharField(max_length=30)
    item_image = models.ImageField(upload_to='found_items/', blank=True, null=True)
    date_found = models.DateField()
    location_found = models.CharField(max_length=255)
    date_enrolled = models.DateTimeField(auto_now_add=True)
    current_status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    def __str__(self):
        return f"{self.item_name} - {self.current_status}"

# 4. LOST TICKETS
class LostItemTicket(models.Model):
    class Status(models.TextChoices):
        SEARCHING = 'SEARCHING', 'Searching'
        MATCH_FOUND = 'MATCH_FOUND', 'Potential Match Found'
        CLAIM_PENDING = 'CLAIM_PENDING', 'Claim Verification in Progress' # <--- NEW
        CLOSED = 'CLOSED', 'Closed/Found'

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='lost_tickets')
    
    # CHANGED
    category = models.CharField(max_length=50, choices=ItemCategory.choices)
    
    item_name = models.CharField(max_length=100)
    description = models.TextField()
    color = models.CharField(max_length=30)
    item_image = models.ImageField(upload_to='lost_tickets/', blank=True, null=True)
    date_lost = models.DateField()
    location_lost = models.CharField(max_length=255)
    date_submitted = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SEARCHING)
    matched_item = models.ForeignKey('FoundItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_tickets')

# 5. CLAIMS
class ClaimRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Verification'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Item Picked Up'

    ticket = models.ForeignKey(LostItemTicket, on_delete=models.CASCADE, null=True, blank=True)
    found_item = models.ForeignKey(FoundItem, on_delete=models.CASCADE, related_name='claims')
    claimant = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    proof_of_ownership = models.TextField()
    proof_image = models.ImageField(upload_to='claims_evidence/', blank=True, null=True)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='reviewed_claims')
    rejection_reason = models.TextField(blank=True, null=True)

# 6. AUDIT LOG
class AuditLog(models.Model):
    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    target_model = models.CharField(max_length=50)
    target_object_id = models.CharField(max_length=50)
    changes = models.JSONField(default=dict, blank=True)