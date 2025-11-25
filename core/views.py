from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.db.models import Count, Q

from .forms import (
    StudentSignUpForm, LostItemForm, HandInForm, 
    ClaimForm, FoundItemAdminForm, StaffCreationForm
)
from .models import (
    LostItemTicket, HandInReport, FoundItem, 
    ClaimRequest, AuditLog, CustomUser
)

# ==============================================================================
# 1. PUBLIC VIEWS (Home, Gallery, Hand-in)
# ==============================================================================

def home(request):
    """Landing page showing recent available items."""
    items = FoundItem.objects.filter(current_status='AVAILABLE').order_by('-date_found')[:8]
    return render(request, 'home.html', {'items': items})

def item_gallery(request):
    """Full catalogue of found items."""
    # 1. Fetch Items
    items = FoundItem.objects.filter(current_status=FoundItem.Status.AVAILABLE)
    
    # 2. Search Logic (Optional, but good to add if you want that search bar to work)
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(item_name__icontains=query) | 
            Q(category__icontains=query) |
            Q(description__icontains=query)
        )

    # 3. CRITICAL FIX: Sort by Category for the 'regroup' tag to work
    # We sort by 'category' field (the machine name, e.g., 'ELECTRONICS')
    items = items.order_by('category', '-date_found')
    
    return render(request, 'items/gallery.html', {'items': items})

def hand_in_item(request):
    """Public form for reporting found items (Stranger/Guest)."""
    if request.method == 'POST':
        form = HandInForm(request.POST)
        if form.is_valid():
            report = form.save()
            return render(request, 'items/hand_in_success.html', {'report': report})
    else:
        form = HandInForm()
    return render(request, 'items/hand_in.html', {'form': form})


# ==============================================================================
# 2. AUTHENTICATION (Signup)
# ==============================================================================

def signup(request):
    if request.method == 'POST':
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created! Welcome, {user.username}.")
            return redirect('home')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StudentSignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


# ==============================================================================
# 3. STUDENT DASHBOARD & ACTIONS
# ==============================================================================

@login_required
def dashboard(request):
    """Router: Redirects to Student or Staff dashboard based on role."""
    user = request.user
    if user.role == 'STUDENT':
        return student_dashboard(request)
    elif user.role in ['STAFF', 'ADMIN']:
        return redirect('staff_dashboard')
    return redirect('home')

@login_required
def student_dashboard(request):
    my_tickets = LostItemTicket.objects.filter(owner=request.user).order_by('-date_submitted')
    my_claims = ClaimRequest.objects.filter(claimant=request.user).order_by('-request_date')
    
    return render(request, 'dashboard/student.html', {
        'tickets': my_tickets, 
        'claims': my_claims
    })

@login_required
def submit_lost_ticket(request):
    if request.method == 'POST':
        form = LostItemForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.owner = request.user
            ticket.save()
            messages.success(request, "Lost item ticket submitted!")
            return redirect('dashboard')
    else:
        form = LostItemForm()
    return render(request, 'items/report_lost.html', {'form': form})

@login_required
def submit_claim(request, item_id):
    """Student claiming a specific item."""
    item = get_object_or_404(FoundItem, id=item_id)
    
    # Prevent duplicate claims
    if ClaimRequest.objects.filter(claimant=request.user, found_item=item, status='PENDING').exists():
        messages.warning(request, "You already have a pending claim for this item.")
        return redirect('item_gallery')

    if request.method == 'POST':
        form = ClaimForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.found_item = item
            claim.claimant = request.user
            
            # Auto-Link logic: If user has an open ticket matching this category
            existing_ticket = LostItemTicket.objects.filter(
                owner=request.user, 
                category=item.category,
                status__in=['SEARCHING', 'MATCH_FOUND']
            ).first()
            
            if existing_ticket:
                claim.ticket = existing_ticket
                existing_ticket.matched_item = item
                existing_ticket.status = LostItemTicket.Status.CLAIM_PENDING 
                existing_ticket.save()

            claim.save()
            messages.success(request, "Claim submitted! Staff will review your proof.")
            return redirect('dashboard')
    else:
        form = ClaimForm()
    
    return render(request, 'items/claim_form.html', {'form': form, 'item': item})


# ==============================================================================
# 4. STAFF DASHBOARD & MATCHING TOOLS
# ==============================================================================

@login_required
def staff_dashboard(request):
    # ... [KEEP AS IS] ...
    if request.user.role not in ['STAFF', 'ADMIN']: return redirect('home')
    
    stats = {
        'pending_claims': ClaimRequest.objects.filter(status='PENDING').count(),
        'items_in_inventory': FoundItem.objects.filter(current_status='AVAILABLE').count(),
        'lost_tickets': LostItemTicket.objects.filter(status='SEARCHING').count(),
        'hand_ins': HandInReport.objects.filter(is_received=False).count(),
    }
    recent_tickets = LostItemTicket.objects.filter(status='SEARCHING').order_by('-date_submitted')[:5]
    pending_hand_ins = HandInReport.objects.filter(is_received=False).order_by('-date_reported')[:5]
    # We don't need these lists for the dash anymore as we have dedicated pages, 
    # but keeping them for the summary widgets is fine.
    
    recent_logs = AuditLog.objects.all().order_by('-timestamp')[:10]

    return render(request, 'dashboard/staff.html', {
        'stats': stats,
        'recent_tickets': recent_tickets,
        'pending_hand_ins': pending_hand_ins,
        'recent_logs': recent_logs,
        # Removed pending_claims_list as it's now on a separate page
    })

@login_required
def ticket_match_view(request, ticket_id):
    """Runs the Stored Procedure + Broad Search."""
    if request.user.role not in ['STAFF', 'ADMIN']: return redirect('home')
        
    ticket = get_object_or_404(LostItemTicket, id=ticket_id)
    ai_matches = []
    ai_ids = []

    # 1. PRIMARY SEARCH: AI / Stored Procedure (Trigram)
    with connection.cursor() as cursor:
        try:
            cursor.callproc('find_potential_matches', [ticket_id])
            results = cursor.fetchall() 
            for row in results:
                # row[0]=id, row[1]=name, row[2]=score
                item = FoundItem.objects.get(id=row[0])
                item.score = round(row[2] * 100, 1) 
                ai_matches.append(item)
                ai_ids.append(item.id)
        except Exception as e:
            print(f"Error calling stored procedure: {e}")

    # 2. SECONDARY SEARCH: "Other Findings" (Category + Keyword Safety Net)
    # Find items in same category OR matching name, excluding the ones already found by AI
    other_findings = FoundItem.objects.filter(
        current_status='AVAILABLE'
    ).exclude(
        id__in=ai_ids
    ).filter(
        Q(category=ticket.category) | 
        Q(item_name__icontains=ticket.item_name.split()[0]) # Match first word of name at least
    ).order_by('-date_found')[:10] # Limit to 10 to keep UI clean

    return render(request, 'dashboard/match_tool.html', {
        'ticket': ticket, 
        'matches': ai_matches,
        'other_findings': other_findings
    })

@login_required
def confirm_match(request, ticket_id, item_id):
    """Staff manually links a ticket to an item."""
    if request.user.role not in ['STAFF', 'ADMIN']: return redirect('home')

    try:
        ticket = LostItemTicket.objects.get(id=ticket_id)
        found_item = FoundItem.objects.get(id=item_id)
        
        ticket.status = LostItemTicket.Status.MATCH_FOUND
        ticket.matched_item = found_item
        ticket.save()
        
        messages.success(request, f"Match confirmed! Student notified.")
    except (LostItemTicket.DoesNotExist, FoundItem.DoesNotExist):
        messages.error(request, "Error finding records.")

    return redirect('staff_dashboard')

@login_required
def process_claim(request, claim_id, action):
    """Approve or Reject a student's claim."""
    if request.user.role not in ['STAFF', 'ADMIN']: return redirect('home')

    claim = get_object_or_404(ClaimRequest, id=claim_id)
    item = claim.found_item

    if action == 'approve':
        # Approve Claim
        claim.status = ClaimRequest.Status.APPROVED
        claim.reviewed_by = request.user
        claim.save()
        
        # Mark Item as Claimed
        item.current_status = FoundItem.Status.CLAIMED
        item.save() # Triggers Audit Log

        # Close Ticket
        if claim.ticket:
            claim.ticket.status = LostItemTicket.Status.CLOSED
            claim.ticket.save()
        
        # Auto-reject duplicate claims for this item
        ClaimRequest.objects.filter(found_item=item, status='PENDING').exclude(id=claim.id).update(status=ClaimRequest.Status.REJECTED)

        messages.success(request, f"Claim Approved. Item released to {claim.claimant.username}.")

    elif action == 'reject':
        claim.status = ClaimRequest.Status.REJECTED
        claim.reviewed_by = request.user
        claim.save()
        messages.info(request, "Claim Rejected.")

    # Redirect back to list if coming from manage page, or dashboard if coming from dashboard
    if 'claims' in request.META.get('HTTP_REFERER', ''):
        return redirect('manage_claims')
    return redirect('staff_dashboard')

@login_required
def receive_handin(request, report_id):
    """Converts a HandInReport into a FoundItem."""
    if request.user.role not in ['STAFF', 'ADMIN']: return redirect('home')
    
    report = get_object_or_404(HandInReport, id=report_id)
    
    if request.method == 'POST':
        # Create the Found Item
        item = FoundItem.objects.create(
            category=report.category,
            item_name=report.item_name,
            description=report.description,
            color=report.color,
            date_found=report.date_reported.date(), # Convert datetime to date
            location_found=report.location_found,
            registered_by=request.user,
            hand_in_ref=report,
            current_status='AVAILABLE'
        )
        
        # Update Report Status
        report.is_received = True
        report.save()
        
        messages.success(request, f"Item received! Inventory ID: {item.id}")
        return redirect('manage_handins')
    
    return render(request, 'dashboard/receive_confirm.html', {'report': report})


# ==============================================================================
# 5. MANAGEMENT VIEWS (Lists, Search, CRUD)
# ==============================================================================

# --- A. Found Items ---
@login_required
def manage_found_items(request):
    if request.user.role not in ['ADMIN', 'STAFF']: return redirect('home')
    
    items = FoundItem.objects.all().order_by('-date_enrolled')
    
    # Search Logic
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(item_name__icontains=query) | 
            Q(category__icontains=query) |
            Q(description__icontains=query) |
            Q(location_found__icontains=query)
        )
        
    return render(request, 'dashboard/manage_items.html', {'items': items})

@login_required
def add_found_item(request):
    if request.user.role not in ['ADMIN', 'STAFF']: return redirect('home')

    if request.method == 'POST':
        form = FoundItemAdminForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.registered_by = request.user
            item.save()
            messages.success(request, "Item added to inventory.")
            return redirect('manage_found_items')
    else:
        form = FoundItemAdminForm()
    return render(request, 'dashboard/form_page.html', {'form': form, 'title': 'Add Found Item'})

@login_required
def delete_found_item(request, item_id):
    if request.user.role != 'ADMIN': 
        messages.error(request, "Permission denied.")
        return redirect('manage_found_items')
        
    item = get_object_or_404(FoundItem, id=item_id)
    item.delete()
    messages.success(request, "Item deleted.")
    return redirect('manage_found_items')


# --- B. Lost Tickets ---
@login_required
def manage_lost_tickets(request):
    if request.user.role not in ['ADMIN', 'STAFF']: return redirect('home')
    
    tickets = LostItemTicket.objects.all().order_by('-date_submitted')
    
    # Search Logic
    query = request.GET.get('q')
    if query:
        tickets = tickets.filter(
            Q(item_name__icontains=query) | 
            Q(owner__username__icontains=query) | 
            Q(owner__student_id__icontains=query)
        )
    return render(request, 'dashboard/manage_tickets.html', {'tickets': tickets})


# --- C. Hand-in Reports ---
@login_required
def manage_handins(request):
    if request.user.role not in ['ADMIN', 'STAFF']: return redirect('home')
    
    reports = HandInReport.objects.all().order_by('-date_reported')
    
    # Search Logic
    query = request.GET.get('q')
    if query:
        reports = reports.filter(
            Q(reference_code__icontains=query) | 
            Q(item_name__icontains=query) |
            Q(finder_name__icontains=query)
        )
    return render(request, 'dashboard/manage_handins.html', {'reports': reports})


# --- D. Claims ---
@login_required
def manage_claims(request):
    if request.user.role not in ['ADMIN', 'STAFF']: return redirect('home')
    
    claims = ClaimRequest.objects.all().order_by('-request_date')
    
    # Search Logic
    query = request.GET.get('q')
    status_filter = request.GET.get('status')
    
    if query:
        claims = claims.filter(
            Q(found_item__item_name__icontains=query) | 
            Q(claimant__username__icontains=query) |
            Q(claimant__student_id__icontains=query)
        )
    
    if status_filter:
        claims = claims.filter(status=status_filter)
        
    return render(request, 'dashboard/manage_claims.html', {'claims': claims})


# --- E. User Management (Admin Only) ---
@login_required
def manage_users(request):
    if request.user.role != 'ADMIN': return redirect('staff_dashboard')
    
    role_filter = request.GET.get('role', 'STAFF')
    users = CustomUser.objects.filter(role=role_filter)
    
    # Search Logic
    query = request.GET.get('q')
    if query:
        users = users.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(student_id__icontains=query)
        )
    
    return render(request, 'dashboard/manage_users.html', {'users': users, 'role': role_filter})

@login_required
def add_staff(request):
    if request.user.role != 'ADMIN': return redirect('staff_dashboard')

    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New Staff account created.")
            return redirect('manage_users')
    else:
        form = StaffCreationForm()
    return render(request, 'dashboard/form_page.html', {'form': form, 'title': 'Add New Staff'})

@login_required
def edit_user(request, user_id):
    if request.user.role != 'ADMIN':
        return redirect('staff_dashboard')
        
    user_to_edit = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        user_to_edit.first_name = request.POST.get('first_name')
        user_to_edit.last_name = request.POST.get('last_name')
        user_to_edit.email = request.POST.get('email')
        
        is_active = request.POST.get('is_active') == 'on'
        user_to_edit.is_active = is_active
        
        user_to_edit.save()
        messages.success(request, f"User {user_to_edit.username} updated successfully.")
        return redirect(f"/dashboard/users/?role={user_to_edit.role}")
        
    return render(request, 'dashboard/edit_user_modal.html', {'target_user': user_to_edit})


# --- F. Audit Logs ---
@login_required
def view_audit_logs(request):
    if request.user.role != 'ADMIN': return redirect('staff_dashboard')
    
    logs = AuditLog.objects.all().order_by('-timestamp')[:100]
    
    # Search Logic
    query = request.GET.get('q')
    if query:
        logs = logs.filter(
            Q(actor__username__icontains=query) | 
            Q(action__icontains=query) | 
            Q(target_model__icontains=query)
        )
    return render(request, 'dashboard/audit_logs.html', {'logs': logs})