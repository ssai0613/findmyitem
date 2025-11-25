from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from .models import FoundItem, ClaimRequest, LostItemTicket, AuditLog
import json

# Helper function to serialize data for the JSON field
def serialize_instance(instance):
    # Convert model instance to a simple dictionary
    data = model_to_dict(instance)
    # Remove image fields (binary data causes errors in JSON)
    if 'item_image' in data: del data['item_image']
    if 'proof_image' in data: del data['proof_image']
    # Convert dates to strings
    for key, value in data.items():
        if value and not isinstance(value, (str, int, float, bool)):
            data[key] = str(value)
    return data

# 1. LOG CHANGES TO FOUND ITEMS
@receiver(post_save, sender=FoundItem)
def log_found_item_changes(sender, instance, created, **kwargs):
    action = "CREATED_ITEM" if created else "UPDATED_ITEM"
    
    # Who did it? (If registered_by is set)
    actor = instance.registered_by
    
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model="FoundItem",
        target_object_id=str(instance.id),
        changes=serialize_instance(instance) # Snapshot of the item
    )

# 2. LOG CLAIM PROCESSING
@receiver(post_save, sender=ClaimRequest)
def log_claim_changes(sender, instance, created, **kwargs):
    # We only care about updates (Approvals/Rejections), not initial creation by student
    if not created: 
        action = f"CLAIM_{instance.status}" # e.g., CLAIM_APPROVED
        
        # Who did it? (The staff reviewer)
        actor = instance.reviewed_by 
        
        # If reviewed_by isn't set yet (rare), fallback to None
        
        AuditLog.objects.create(
            actor=actor,
            action=action,
            target_model="ClaimRequest",
            target_object_id=str(instance.id),
            changes={'status': instance.status, 'item': instance.found_item.item_name}
        )

# 3. LOG TICKET MATCHING
@receiver(post_save, sender=LostItemTicket)
def log_ticket_changes(sender, instance, created, **kwargs):
    if not created and instance.status == 'MATCH_FOUND':
        AuditLog.objects.create(
            actor=instance.owner, # Or System
            action="MATCH_LINKED",
            target_model="LostItemTicket",
            target_object_id=str(instance.id),
            changes={'status': instance.status, 'matched_item_id': str(instance.matched_item.id if instance.matched_item else 'None')}
        )