from django.contrib import admin
from .models import CustomUser, HandInReport, FoundItem, LostItemTicket, ClaimRequest, AuditLog

# 1. User Admin
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'role', 'student_id', 'program_year', 'email')
    list_filter = ('role', 'program_year')
    search_fields = ('username', 'student_id', 'first_name', 'last_name')

# 2. Hand In Reports
@admin.register(HandInReport)
class HandInReportAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'reference_code', 'category', 'date_reported', 'is_received')
    list_filter = ('is_received', 'category', 'date_reported')
    search_fields = ('reference_code', 'item_name', 'finder_name')

# 3. Found Items
@admin.register(FoundItem)
class FoundItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'current_status', 'location_found', 'date_found')
    list_filter = ('current_status', 'category', 'date_found')
    search_fields = ('item_name', 'description', 'location_found')

# 4. Lost Tickets
@admin.register(LostItemTicket)
class LostItemTicketAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'owner', 'status', 'date_lost')
    list_filter = ('status', 'category')
    search_fields = ('item_name', 'owner__username', 'description')

# 5. Claims
@admin.register(ClaimRequest)
class ClaimRequestAdmin(admin.ModelAdmin):
    list_display = ('found_item', 'claimant', 'status', 'request_date')
    list_filter = ('status',)

# 6. Audit Logs (Read Only is best for logs)
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'target_model', 'timestamp')
    list_filter = ('action', 'target_model')
    readonly_fields = ('actor', 'action', 'ip_address', 'timestamp', 'target_model', 'target_object_id', 'changes')