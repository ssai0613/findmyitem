from django.urls import path
from . import views

urlpatterns = [
    # --- PUBLIC PAGES ---
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('browse-found-items/', views.item_gallery, name='item_gallery'),
    path('hand-in/', views.hand_in_item, name='hand_in'),

    # --- STUDENT DASHBOARD ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('report-lost/', views.submit_lost_ticket, name='submit_ticket'),
    path('request-claim/<int:item_id>/', views.submit_claim, name='submit_claim'),

    # --- STAFF/ADMIN DASHBOARD ---
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    
    # Matching Logic
    path('staff/ticket/<int:ticket_id>/match/', views.ticket_match_view, name='ticket_match'),
    path('confirm-match/<int:ticket_id>/<int:item_id>/', views.confirm_match, name='confirm_match'),
    path('staff/process-claim/<int:claim_id>/<str:action>/', views.process_claim, name='process_claim'),

    # --- MANAGEMENT LISTS (The replacement for old admin links) ---
    
    # 1. Found Items
    path('dashboard/items/', views.manage_found_items, name='manage_found_items'),
    path('dashboard/items/add/', views.add_found_item, name='add_found_item'),
    path('dashboard/items/delete/<int:item_id>/', views.delete_found_item, name='delete_found_item'),

    # 2. Lost Tickets
    path('dashboard/tickets/', views.manage_lost_tickets, name='manage_lost_tickets'),

    # 3. Hand-ins
    path('dashboard/handins/', views.manage_handins, name='manage_handins'),
    path('dashboard/handins/receive/<int:report_id>/', views.receive_handin, name='receive_handin'),

    # 4. Claims
    path('dashboard/claims/', views.manage_claims, name='manage_claims'),

    # 5. Users (Replaces manage_staff and manage_students)
    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/add-staff/', views.add_staff, name='add_staff'),
    path('dashboard/users/edit/<int:user_id>/', views.edit_user, name='edit_user'),

    # 6. Logs
    path('dashboard/audit-logs/', views.view_audit_logs, name='view_audit_logs'),
]