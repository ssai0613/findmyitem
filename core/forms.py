from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, LostItemTicket, HandInReport, FoundItem, ClaimRequest

class StudentSignUpForm(UserCreationForm):
    # Enforce strict input on the frontend form widget
    student_id = forms.CharField(
        max_length=7, 
        min_length=7,
        help_text="Required. 7 digits only.",
        widget=forms.TextInput(attrs={'type': 'number', 'placeholder': '1234567'})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        # Added program_year to the list
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name', 'student_id', 'program_year')

    # Custom "Checker" logic
    def clean_student_id(self):
        sid = self.cleaned_data.get('student_id')
        
        # 1. Check if it contains only numbers
        if not sid.isdigit():
            raise forms.ValidationError("Student ID must contain numbers only.")
        
        # 2. Check length
        if len(sid) != 7:
            raise forms.ValidationError("Student ID must be exactly 7 digits.")
            
        # 3. Check Uniqueness (The new logic)
        # We look for any user who has this ID
        if CustomUser.objects.filter(student_id=sid).exists():
            raise forms.ValidationError("This Student ID is already registered. Please log in or contact support.")
            
        return sid

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Roles.STUDENT
        if commit:
            user.save()
        return user
    

#Student: Report Lost Item
class LostItemForm(forms.ModelForm):
    class Meta:
        model = LostItemTicket
        fields = ['category', 'item_name', 'description', 'color', 'date_lost', 'location_lost', 'item_image']
        widgets = {
            'date_lost': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

#Public: Hand In Item
class HandInForm(forms.ModelForm):
    class Meta:
        model = HandInReport
        fields = ['finder_name', 'finder_contact', 'category', 'item_name', 'description', 'color', 'location_found']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class ClaimForm(forms.ModelForm):
    class Meta:
        model = ClaimRequest
        fields = ['proof_of_ownership', 'proof_image']
        widgets = {
            'proof_of_ownership': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe unique features, contents, or scratches to prove this is yours.'}),
        }

class FoundItemAdminForm(forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ['category', 'item_name', 'description', 'color', 'date_found', 'location_found', 'item_image', 'current_status']
        widgets = {
            'date_found': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

# Form for Admin to add new Staff users
class StaffCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = CustomUser.Roles.STAFF
        if commit:
            user.save()
        return user