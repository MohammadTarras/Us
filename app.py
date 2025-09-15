import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client
import hashlib
import time
import re
import secrets
from datetime import datetime, timedelta, timezone

# Configure page
st.set_page_config(
    page_title="Our Events",
    page_icon="🕵️‍♀️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Supabase configuration
SUPABASE_URL = "https://qvkrvidkgzscjycbmdxu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF2a3J2aWRrZ3pzY2p5Y2JtZHh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY4ODY5OTQsImV4cCI6MjA3MjQ2Mjk5NH0.HHAwIvBpxJeAJUpyI0KemV9Et1mezv5Tli-qB1n1PGI"

@st.cache_resource
def init_supabase():
    """Initialize Supabase client with caching"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_session_token():
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

def save_session_token(username, token):
    """Save session token to database with improved error handling"""
    try:
        supabase = init_supabase()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        # Clean up existing sessions for this user
        supabase.table('user_sessions').delete().eq('username', username).execute()
        
        # Insert new session
        supabase.table('user_sessions').insert({
            'username': username,
            'session_token': token,
            'expires_at': expires_at
        }).execute()
        return True
    except Exception as e:
        st.error(f"Session error: Please try logging in again.")
        return False

@st.cache_data(ttl=30, show_spinner=False)  # Shorter cache for better UX
def verify_session_token(token):
    """Verify session token and return user data with caching"""
    try:
        supabase = init_supabase()
        
        session_response = supabase.table('user_sessions').select('*').eq('session_token', token).execute()
        
        if session_response.data and len(session_response.data) > 0:
            session = session_response.data[0]
            
            expires_at_str = session['expires_at']
            if expires_at_str.endswith('Z'):
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            elif '+' in expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
            else:
                expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)
            
            current_time = datetime.now(timezone.utc)
            
            if expires_at > current_time:
                user_response = supabase.table('users').select('*').eq('username', session['username']).execute()
                if user_response.data and len(user_response.data) > 0:
                    return user_response.data[0]
            else:
                # Token expired, clean it up
                supabase.table('user_sessions').delete().eq('session_token', token).execute()
        return None
    except Exception:
        return None

def cleanup_expired_sessions():
    """Clean up expired session tokens"""
    try:
        supabase = init_supabase()
        current_time = datetime.now(timezone.utc).isoformat()
        supabase.table('user_sessions').delete().lt('expires_at', current_time).execute()
    except Exception:
        pass

def check_session_from_url():
    """Check for valid session token in URL"""
    query_params = st.query_params
    if 'session_token' in query_params:
        token = query_params['session_token']
        user = verify_session_token(token)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            set_user_context(user['username'])
            return True
        else:
            st.query_params.clear()
            st.session_state.authenticated = False
            st.session_state.user = None
    return False

def set_user_context(username):
    """Set the current user context for RLS policies"""
    try:
        supabase = init_supabase()
        supabase.rpc('set_current_user', {'user_name': username}).execute()
        return True
    except Exception:
        return False

@st.cache_data(ttl=60, show_spinner=False)  # Cache for 1 minute
def load_events_from_db(username):
    """Load events from Supabase database with optimized caching"""
    try:
        supabase = init_supabase()
        set_user_context(username)
        
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
        st.error(f"Error loading events: {str(e)}")
        return []

def save_event_to_db(title, event_date, preview, description, username):
    """Save new event to Supabase database"""
    try:
        supabase = init_supabase()
        set_user_context(username)
        
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

def update_event_in_db(event_id, title, event_date, preview, description, username):
    """Update existing event in Supabase database"""
    try:
        supabase = init_supabase()
        set_user_context(username)
        
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

def delete_event_from_db(event_id, username):
    """Delete event from database"""
    try:
        supabase = init_supabase()
        set_user_context(username)
        
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
    """Authenticate user and create session token"""
    try:
        supabase = init_supabase()
        hashed_password = hash_password(password)
        
        response = supabase.table('users').select('*').eq('username', username).eq('password_hash', hashed_password).execute()
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            set_user_context(username)
            
            session_token = generate_session_token()
            if save_session_token(username, session_token):
                st.query_params.update({'session_token': session_token})
                
                # Log the login
                supabase.table('logins').insert({
                    'username': username,
                }).execute()
                
                return True, user
            else:
                return False, None
        return False, None
    except Exception:
        st.error("Authentication error. Please try again.")
        return False, None

def logout():
    """Logout and clear session"""
    if st.session_state.authenticated and st.session_state.user:
        try:
            supabase = init_supabase()
            session_token = st.query_params.get('session_token')
            if session_token:
                supabase.table('user_sessions').delete().eq('session_token', session_token).execute()
        except Exception:
            pass
    
    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.query_params.clear()
    st.rerun()

def is_arabic_text(text):
    """Detect if text contains Arabic characters"""
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
    return bool(arabic_pattern.search(text))

# Enhanced CSS with better performance and mobile optimization
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@300;400;600;700&display=swap');
    
    /* Hide sidebar completely */
    .css-1d391kg {display: none;}
    section[data-testid="stSidebar"] {display: none !important;}
    .stApp > div:first-child {margin-left: 0rem;}
    
    .main-header {
        text-align: center;
        color: #2c3e50;
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        font-family: 'Cairo', sans-serif;
    }
    
    /* Action buttons */
    .action-buttons {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin: 2rem 0;
        flex-wrap: wrap;
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
    
    /* Event Card Styles */
    .event-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        color: white;
        transition: all 0.3s ease;
        border: none;
        position: relative;
        overflow: hidden;
    }
    
    .event-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 35px rgba(0,0,0,0.25);
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
        margin-bottom: 1rem;
    }
    
    .card-actions {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 1rem;
    }
    
    /* Event Detail View */
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
    
    .user-info {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
        font-family: 'Cairo', sans-serif;
    }
    
    /* Form styles */
    .event-form {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        border: 1px solid #dee2e6;
    }
    
    .form-header {
        text-align: center;
        color: #2c3e50;
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
        font-family: 'Cairo', sans-serif;
    }
    
    /* Mobile-First Responsive Design */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .action-buttons {
            flex-direction: column;
            align-items: center;
            gap: 0.5rem;
        }
        
        .event-detail-container {
            padding: 0.5rem;
        }
        
        .event-detail-card {
            padding: 1.5rem;
            margin: 0.5rem 0;
            border-radius: 15px;
        }
        
        .event-detail-title {
            font-size: 1.8rem;
            line-height: 1.2;
        }
        
        .event-description {
            font-size: 1.1rem;
            line-height: 1.6;
            padding: 1.5rem;
        }
        
        .event-card {
            padding: 1.2rem;
        }
        
        .card-actions {
            justify-content: center;
        }
        
        .login-container {
            margin: 1rem 0.5rem;
            padding: 2rem 1.5rem;
            width: calc(100% - 1rem);
            box-sizing: border-box;
        }
    }
    
    @media (max-width: 480px) {
        .main-header {
            font-size: 1.8rem;
        }
        
        .event-detail-title {
            font-size: 1.5rem;
        }
        
        .event-description {
            font-size: 1rem;
            padding: 1rem;
        }
        
        .event-form {
            padding: 1rem;
            margin: 0.5rem 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    cleanup_expired_sessions()
    check_session_from_url()

if 'user' not in st.session_state:
    st.session_state.user = None
if 'selected_event' not in st.session_state:
    st.session_state.selected_event = None
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False
if 'edit_event_id' not in st.session_state:
    st.session_state.edit_event_id = None

def login_page():
    """Display login page"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-header">🔐 Login</h1>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        
        if submitted:
            if username and password:
                with st.spinner("Authenticating..."):
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
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_event_details(event):
    """Display detailed view of selected event with Arabic text support"""
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

def add_event_form():
    """Display form to add new event"""
    st.markdown('<div class="event-form">', unsafe_allow_html=True)
    st.markdown('<div class="form-header">➕ Add New Event</div>', unsafe_allow_html=True)
    
    with st.form("add_event_form", clear_on_submit=True):
        new_title = st.text_input("Event Title", placeholder="Enter event title")
        new_date = st.date_input("Event Date", value=date.today())
        new_preview = st.text_input("Short Preview", placeholder="Brief description for timeline...")
        new_description = st.text_area("Detailed Description", height=200, 
                                     placeholder="Full description of the event...")
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("💾 Add Event", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                st.session_state.show_add_form = False
                st.rerun()
        
        if submitted:
            if new_title and new_preview and new_description:
                with st.spinner("Adding event..."):
                    success = save_event_to_db(new_title, new_date, new_preview, 
                                             new_description, st.session_state.user['username'])
                    if success:
                        st.success("✅ Event added successfully!")
                        st.session_state.show_add_form = False
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("Please fill in all required fields.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def edit_event_form(event):
    """Display form to edit existing event"""
    st.markdown('<div class="event-form">', unsafe_allow_html=True)
    st.markdown('<div class="form-header">✏️ Edit Event</div>', unsafe_allow_html=True)
    
    with st.form("edit_event_form"):
        edit_title = st.text_input("Event Title", value=event['title'])
        edit_date = st.date_input("Event Date", value=event['date'])
        edit_preview = st.text_input("Short Preview", value=event['preview'])
        edit_description = st.text_area("Detailed Description", value=event['description'], height=200)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            save_clicked = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                st.session_state.edit_event_id = None
                st.rerun()
        with col3:
            delete_clicked = st.form_submit_button("🗑️ Delete", use_container_width=True)
        
        if save_clicked:
            if edit_title and edit_preview and edit_description:
                with st.spinner("Updating event..."):
                    success = update_event_in_db(event['id'], edit_title, edit_date, edit_preview, 
                                               edit_description, st.session_state.user['username'])
                    if success:
                        st.success("✅ Event updated successfully!")
                        st.session_state.edit_event_id = None
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("Please fill in all required fields.")
        
        if delete_clicked:
            if st.checkbox("Confirm deletion (this cannot be undone)", key="confirm_delete"):
                with st.spinner("Deleting event..."):
                    success = delete_event_from_db(event['id'], st.session_state.user['username'])
                    if success:
                        st.success("✅ Event deleted successfully!")
                        st.session_state.edit_event_id = None
                        st.session_state.selected_event = None
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("Please confirm deletion to proceed.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def create_event_cards(events):
    """Create event cards with inline edit buttons"""
    if not events:
        return
    
    for i, event in enumerate(events):
        card_html = f'''
        <div class="event-card">
            <div class="card-title">{event['title']}</div>
            <div class="card-date">📅 {event['date'].strftime('%B %d, %Y')}</div>
            <div class="card-preview">{event['preview']}</div>
        </div>
        '''
        
        st.markdown(card_html, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"👁️ View Details", key=f"view_{i}", 
                        type="secondary", use_container_width=True):
                st.session_state.selected_event = i
                st.session_state.edit_event_id = None
                st.rerun()
        
        with col2:
            if st.button(f"✏️ Edit", key=f"edit_{i}", 
                        type="secondary", use_container_width=True):
                st.session_state.selected_event = i
                st.session_state.edit_event_id = event['id']
                st.rerun()
        
        st.markdown("---")

def main():
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Header
    st.markdown('<h1 class="main-header">📅 Our Events</h1>', unsafe_allow_html=True)
    
    # User info and logout
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f'<div class="user-info">👋 Welcome, {st.session_state.user["username"]}!</div>', 
                   unsafe_allow_html=True)
    with col2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            logout()
    
    # Action buttons
    st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:  # Center the button
        if st.button("➕ Add New Event", type="primary", use_container_width=True):
            st.session_state.show_add_form = True
            st.session_state.selected_event = None
            st.session_state.edit_event_id = None
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load events
    with st.spinner("Loading events..."):
        events_data = load_events_from_db(st.session_state.user['username'])
    
    # Show appropriate content
    if st.session_state.show_add_form:
        add_event_form()
    elif st.session_state.selected_event is not None and st.session_state.selected_event < len(events_data):
        # Back button
        if st.button("← Back to Events", type="primary"):
            st.session_state.selected_event = None
            st.session_state.edit_event_id = None
            st.rerun()
        
        event = events_data[st.session_state.selected_event]
        
        # Show edit form or event details
        if st.session_state.edit_event_id == event['id']:
            edit_event_form(event)
        else:
            display_event_details(event)
    else:
        # Events grid view
        if events_data:
            st.markdown("---")
            st.subheader("📅 Your Events Timeline")
            create_event_cards(events_data)
        else:
            st.markdown("""
            <div class="no-events">
                <h2>🎯 Create Your First Event</h2>
                <p>Click "Add New Event" button above to get started!</p>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()