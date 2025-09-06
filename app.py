import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client
import hashlib
import time
import re

# Configure page
st.set_page_config(
    page_title="Our Events",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Supabase configuration
SUPABASE_URL = "https://qvkrvidkgzscjycbmdxu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF2a3J2aWRrZ3pzY2p5Y2JtZHh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY4ODY5OTQsImV4cCI6MjA3MjQ2Mjk5NH0.HHAwIvBpxJeAJUpyI0KemV9Et1mezv5Tli-qB1n1PGI"

@st.cache_resource
def init_supabase():
    """Initialize Supabase client with caching"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_events_from_db():
    """Load events from Supabase database with caching"""
    try:
        supabase = init_supabase()
        response = supabase.table('our_events').select('*').order('event_date').execute()
        
        events = []
        for event in response.data:
            events.append({
                'id': event['id'],
                'title': event['event_title'],
                'date': datetime.strptime(event['event_date'], '%Y-%m-%d').date(),
                'preview': event['preview_text'],
                'description': event['description']
            })
        return events
    except Exception as e:
        # For demo purposes, return sample data if database fails
        st.warning(f"Using sample data. Database error: {str(e)}")
        

@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_users_from_db():
    """Load users from Supabase database with caching"""
    try:
        supabase = init_supabase()
        response = supabase.table('users').select('*').execute()
        return response.data
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")
        return []

def save_event_to_db(title, event_date, preview, description):
    """Save new event to Supabase database"""
    try:
        supabase = init_supabase()
        response = supabase.table('our_events').insert({
            'event_title': title,
            'event_date': str(event_date),
            'preview_text': preview,
            'description': description
        }).execute()
        # Clear cache after successful save
        load_events_from_db.clear()
        return True
    except Exception as e:
        st.error(f"Error saving event: {str(e)}")
        return False

def update_event_in_db(event_id, title, event_date, preview, description):
    """Update existing event in Supabase database"""
    try:
        supabase = init_supabase()
        response = supabase.table('our_events').update({
            'event_title': title,
            'event_date': str(event_date),
            'preview_text': preview,
            'description': description
        }).eq('id', event_id).execute()
        # Clear cache after successful update
        load_events_from_db.clear()
        return True
    except Exception as e:
        st.error(f"Error updating event: {str(e)}")
        return False

def delete_event_from_db(event_id):
    """Delete event from Supabase database"""
    try:
        supabase = init_supabase()
        response = supabase.table('our_events').delete().eq('id', event_id).execute()
        # Clear cache after successful delete
        load_events_from_db.clear()
        return True
    except Exception as e:
        st.error(f"Error deleting event: {str(e)}")
        return False

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(username, password):
    """Authenticate user against database"""
    users = load_users_from_db()
    hashed_password = hash_password(password)
    
    for user in users:
        if user['username'] == username and user['password_hash'] == hashed_password:
            return True, user
    return False, None

def create_user(username, password, email):
    """Create new user in database"""
    try:
        supabase = init_supabase()
        hashed_password = hash_password(password)
        
        response = supabase.table('users').insert({
            'username': username,
            'email': email,
            'password_hash': hashed_password,
            'created_at': datetime.now().isoformat()
        }).execute()
        
        # Clear users cache
        load_users_from_db.clear()
        return True
    except Exception as e:
        st.error(f"Error creating user: {str(e)}")
        return False

def is_arabic_text(text):
    """Detect if text contains Arabic characters"""
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
    return bool(arabic_pattern.search(text))

# Enhanced CSS with better mobile optimization and Arabic support
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@300;400;600;700&display=swap');
    
    .main-header {
        text-align: center;
        color: #2c3e50;
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        font-family: 'Cairo', sans-serif;
    }
    
    /* Login Container */
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 3rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        color: white;
        text-align: center;
    }
    
    .login-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 2rem;
        font-family: 'Cairo', sans-serif;
    }
    
    /* Event Card Styles - Simplified for better compatibility */
    .event-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        color: white;
        transition: all 0.3s ease;
        border: none;
        cursor: pointer;
        text-decoration: none;
    }
    
    .event-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 35px rgba(0,0,0,0.25);
        text-decoration: none;
        color: white;
    }
    
    .card-title {
        font-size: 1.4rem;
        font-weight: bold;
        margin-bottom: 0.8rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        font-family: 'Cairo', sans-serif;
        line-height: 1.3;
    }
    
    .card-date {
        font-size: 0.9rem;
        margin-bottom: 0.8rem;
        opacity: 0.9;
        font-family: 'Cairo', sans-serif;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .card-preview {
        font-size: 0.95rem;
        opacity: 0.9;
        line-height: 1.4;
        font-family: 'Cairo', sans-serif;
    }
    
    /* Event Detail View - Enhanced for mobile */
    .event-detail-container {
        max-width: 100%;
        margin: 0 auto;
        padding: 1rem;
    }
    
    .event-detail-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 25px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        color: #2c3e50;
        position: relative;
        overflow: hidden;
        width: 100%;
    }
    
    .event-detail-title {
        color: #2c3e50;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
        text-align: center;
        font-family: 'Cairo', sans-serif;
        position: relative;
        z-index: 1;
    }
    
    .event-detail-meta {
        text-align: center;
        color: #7f8c8d;
        font-size: 1.2rem;
        margin-bottom: 2rem;
        font-style: italic;
        font-family: 'Cairo', sans-serif;
        position: relative;
        z-index: 1;
    }
    
    .event-description {
        font-size: 1.2rem;
        line-height: 1.8;
        color: #2c3e50;
        font-family: 'Amiri', 'Cairo', serif;
        position: relative;
        z-index: 1;
        background: rgba(255, 255, 255, 0.7);
        padding: 2rem;
        border-radius: 15px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        width: 100%;
        box-sizing: border-box;
        text-align: justify;
    }
    
    .event-description.arabic {
        direction: rtl;
        text-align: right;
        font-family: 'Amiri', 'Cairo', serif;
    }
    
    .no-events {
        text-align: center;
        padding: 4rem 2rem;
        color: #7f8c8d;
        font-family: 'Cairo', sans-serif;
    }
    
    .no-events h2 {
        font-size: 2rem;
        margin-bottom: 1rem;
    }
    
    .no-events p {
        font-size: 1.1rem;
        opacity: 0.8;
    }
    
    /* User info */
    .user-info {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
        font-family: 'Cairo', sans-serif;
    }
    
    /* Mobile-First Responsive Design */
    @media (max-width: 768px) {
        .event-detail-container {
            padding: 0.5rem;
            width: 100%;
        }
        
        .event-detail-card {
            padding: 1.5rem;
            margin: 0.5rem 0;
            border-radius: 15px;
            width: 100%;
            box-sizing: border-box;
        }
        
        .event-detail-title {
            font-size: 1.8rem;
            margin-bottom: 1rem;
            line-height: 1.2;
        }
        
        .event-detail-meta {
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .event-description {
            font-size: 1.1rem;
            line-height: 1.6;
            padding: 1.5rem;
            margin: 0;
            width: 100%;
            box-sizing: border-box;
            border-radius: 10px;
        }
        
        .main-header {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .login-container {
            margin: 1rem 0.5rem;
            padding: 2rem 1.5rem;
            width: calc(100% - 1rem);
            box-sizing: border-box;
        }
        
        .event-card {
            padding: 1.2rem;
            margin-bottom: 1rem;
        }
        
        .card-title {
            font-size: 1.2rem;
        }
        
        .user-info {
            padding: 0.8rem;
            font-size: 0.9rem;
        }
    }
    
    /* Extra small screens */
    @media (max-width: 480px) {
        .event-detail-container {
            padding: 0.25rem;
        }
        
        .event-detail-card {
            padding: 1rem;
            margin: 0.25rem 0;
        }
        
        .event-detail-title {
            font-size: 1.5rem;
        }
        
        .event-description {
            font-size: 1rem;
            padding: 1rem;
        }
        
        .main-header {
            font-size: 1.8rem;
        }
    }
    
    /* Ensure full width usage */
    .stApp > div > div > div > div {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    
    .element-container {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'selected_event' not in st.session_state:
    st.session_state.selected_event = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'edit_event_id' not in st.session_state:
    st.session_state.edit_event_id = None

def login_page():
    """Display login/registration page"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-header">🔐 Login</h1>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Sign In")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if username and password:
                success, user = authenticate_user(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success("✅ Login successful!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("Please enter both username and password")
    
    with tab2:
        st.subheader("Create Account")
        new_username = st.text_input("Username", key="reg_username")
        new_email = st.text_input("Email", key="reg_email")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        
        if st.button("Create Account", type="primary", use_container_width=True):
            if new_username and new_email and new_password and confirm_password:
                if new_password == confirm_password:
                    success = create_user(new_username, new_password, new_email)
                    if success:
                        st.success("✅ Account created! Please login.")
                    else:
                        st.error("❌ Error creating account")
                else:
                    st.error("❌ Passwords don't match")
            else:
                st.error("Please fill in all fields")
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_event_details(event):
    """Display detailed view of selected event with Arabic text support"""
    # Check if description contains Arabic text
    arabic_class = "arabic" if is_arabic_text(event["description"]) else ""
    
    st.markdown(f'''
    <div class="event-detail-container">
        <div class="event-detail-card">
            <div class="event-detail-title">{event["title"]}</div>
            <div class="event-detail-meta">
                📅 {event["date"].strftime("%B %d, %Y")}
            </div>
            <div class="event-description {arabic_class}">
                {event["description"]}
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def create_event_cards(events):
    """Create event cards using Streamlit columns for better compatibility"""
    if not events:
        return
    
    # Create columns based on number of events (max 3 per row)
    num_cols = min(len(events), 3)
    cols = st.columns(num_cols)
    
    for i, event in enumerate(events):
        with cols[i % num_cols]:
            # Create clickable card using button
            card_html = f'''
            <div class="event-card">
                <div class="card-title">{event['title']}</div>
                <div class="card-date">{event['date'].strftime('%B %d, %Y')}</div>
                <div class="card-preview">{event['preview']}</div>
            </div>
            '''
            
            # Display the card HTML
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Add invisible button that spans the card area
            if st.button(f"View {event['title']}", key=f"card_btn_{i}", 
                        type="secondary", use_container_width=True,
                        help="Click to view event details"):
                st.session_state.selected_event = i
                st.session_state.edit_mode = False
                st.rerun()

def edit_event_form(event, event_index):
    """Display form to edit existing event"""
    st.subheader("✏️ Edit Event")
    
    edit_title = st.text_input("Event Title", value=event['title'], key=f"edit_title_{event_index}")
    edit_date = st.date_input("Event Date", value=event['date'], key=f"edit_date_{event_index}")
    edit_preview = st.text_input("Short Preview", value=event['preview'], key=f"edit_preview_{event_index}")
    edit_description = st.text_area("Detailed Description", value=event['description'], 
                                   height=200, key=f"edit_desc_{event_index}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Changes", type="primary", key=f"save_edit_{event_index}"):
            if edit_title and edit_preview and edit_description:
                success = update_event_in_db(event['id'], edit_title, edit_date, edit_preview, edit_description)
                if success:
                    st.success("✅ Event updated successfully!")
                    st.session_state.edit_mode = False
                    st.session_state.edit_event_id = None
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Please fill in all fields.")
    
    with col2:
        if st.button("❌ Cancel", key=f"cancel_edit_{event_index}"):
            st.session_state.edit_mode = False
            st.session_state.edit_event_id = None
            st.rerun()

def main():
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Header
    st.markdown('<h1 class="main-header">📅 Our Events</h1>', unsafe_allow_html=True)
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<div class="user-info">👋 Welcome, {st.session_state.user["username"]}!</div>', 
                   unsafe_allow_html=True)
    with col2:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.selected_event = None
            st.session_state.edit_mode = False
            st.rerun()
    
    # Load events from database
    events_data = load_events_from_db()
    
    # Sidebar for event management
    with st.sidebar:
        st.header("📝 Event Management")
        
        # Add new event
        with st.expander("➕ Add New Event", expanded=False):
            new_title = st.text_input("Event Title")
            new_date = st.date_input("Event Date", value=date.today())
            new_preview = st.text_input("Short Preview", placeholder="Brief description for timeline...")
            new_description = st.text_area("Detailed Description", height=200, 
                                         placeholder="Full description...")
            
            if st.button("Add Event", type="primary"):
                if new_title and new_preview and new_description:
                    success = save_event_to_db(new_title, new_date, new_preview, new_description)
                    if success:
                        st.success("✅ Event added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in all fields.")
        
        # Event list for management
        if events_data:
            st.subheader("📋 Manage Events")
            for i, event in enumerate(events_data):
                with st.container():
                    st.write(f"**{event['title'][:20]}{'...' if len(event['title']) > 20 else ''}**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("👁️", key=f"view_{i}", help="View event"):
                            st.session_state.selected_event = i
                            st.session_state.edit_mode = False
                            st.rerun()
                    with col2:
                        if st.button("✏️", key=f"edit_{i}", help="Edit event"):
                            st.session_state.selected_event = i
                            st.session_state.edit_mode = True
                            st.session_state.edit_event_id = event['id']
                            st.rerun()
                    with col3:
                        if st.button("🗑️", key=f"delete_{i}", help="Delete event"):
                            success = delete_event_from_db(event['id'])
                            if success:
                                st.success("Event deleted!")
                                if st.session_state.selected_event == i:
                                    st.session_state.selected_event = None
                                    st.session_state.edit_mode = False
                                st.rerun()
                    st.divider()
    
    # Main content
    if st.session_state.selected_event is not None and st.session_state.selected_event < len(events_data):
        # Back button
        if st.button("← Back to Events", type="primary"):
            st.session_state.selected_event = None
            st.session_state.edit_mode = False
            st.session_state.edit_event_id = None
            st.rerun()
        
        event = events_data[st.session_state.selected_event]
        
        # Show edit form or event details
        if st.session_state.edit_mode and st.session_state.edit_event_id == event['id']:
            edit_event_form(event, st.session_state.selected_event)
        else:
            # Add edit button in detail view
            if st.button("✏️ Edit Event"):
                st.session_state.edit_mode = True
                st.session_state.edit_event_id = event['id']
                st.rerun()
            
            display_event_details(event)
    else:
        # Events grid view
        if events_data:
            st.markdown("---")
            st.subheader("📅 Click on any event button to view details")
            
            create_event_cards(events_data)
        else:
            st.markdown("""
            <div class="no-events">
                <h2>🎯 Create Your First Event</h2>
                <p>Use the sidebar to add events and build your timeline!</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")

if __name__ == "__main__":
    main()