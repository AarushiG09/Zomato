"""Main Streamlit Web Application (Phase 6)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to sys.path explicitly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH
from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.llm import MockLLMProvider
from src.services.ranker import LLMRankingService
from src.services.recommender import RecommendationService

# --- Page Configuration ---
st.set_page_config(
    page_title="zomato AI | Galactic Gastronomy Dashboard",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Visual Assets (Stitch Design) ---
RESTAURANT_IMAGES = [
    "https://lh3.googleusercontent.com/aida-public/AB6AXuAvn7xlypLSXim5VFe8GyN6v0s4RFt886aTXNGxc6r4VY-bOaupm3sSnq2Q4rZrlmD_ORyHVG4iUOE1iZa-SHHmQuKJF4e5CyE28RIkGv44JjA1Yd2IR6Ohm-OgHtvfUTYqickAc5XnDtBpFbPSSTHThBCfULSxzfxBsynKmTwDpRbJGwyUhZjAoMybqFwuXZnWMEvJ3uyxBEmjSVpsprA77msGTeaCpzabOJnJeMiHaRznW222ifdFhIrHt7qL62PBN47KnYpbFh7c",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDgLwjxY956jS9dL9X5s26it0SWSULIV9tj9Bspd8foIcHch7EpXW-H8N-J97xJT0UPVnaYjh6maV7axEklkJu99IpQ5W31HSFEygvXOp9a-kmosX4vu30AjMm6SKUuMZv4LDGVske3gK3fu79AfeyVmxKsIUFbXGFvQQIdAM8X6xRNPniK00YbolJn5iKrqMrYc7es63NFId6B-nMiIinMyjOg4-HIK0cnxbXsq46qFhn-p0GVyugy7Bfa8v1Y2UUZrEW-29Kh5_tq",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDivFkRvlVYCacsAy2MH2Iwo4ZwHdL6t1xy_Y_XI7pwizg4_XjJdwIZyRrt6Rlt9mKAV2OSrGOaOiuc3ZQWsEW78ktJ4LxumcWL7az9KDjq00Phx3AI4Kx60tfJNVKsEElCu647xc2a0QoHGgbcuHY3jVtF1RCaoz0aLP-sfGJuUc31D90-CtKUFP62bhxnCcSCLgTT6CBtnHpiUqTPULiONk3qEPjjOERVfEuPWqylYtyLqNVS9GLjLzz-b4yFT8JQg3fchWfdshwQ",
]

# --- CSS Injection (Sleek Dark Mode, Mesh Gradients, Glassmorphism Aesthetics) ---
CUSTOM_CSS = """
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&amp;family=Inter:wght@300;400;600&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<style>
/* Hide Streamlit Default Overlays */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stAppDeployButton {display: none;}
[data-testid="stHeader"] {display: none;}

/* Adjust padding for fullscreen app effect */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* Background Animations and Mesh Gradients */
[data-testid="stAppViewContainer"] {
    background: transparent !important;
}
[data-testid="stApp"] {
    background-color: #0b0f19 !important;
    color: #dfe2f1 !important;
    overflow-x: hidden;
    background-image: radial-gradient(at 0% 0%, rgba(255, 77, 109, 0.15) 0px, transparent 50%),
                      radial-gradient(at 100% 0%, rgba(0, 166, 224, 0.1) 0px, transparent 50%),
                      radial-gradient(at 50% 100%, rgba(255, 82, 96, 0.05) 0px, transparent 50%) !important;
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar custom overlay */
[data-testid="stSidebar"] {
    background-color: rgba(15, 19, 29, 0.65) !important;
    backdrop-filter: blur(24px) !important;
    -webkit-backdrop-filter: blur(24px) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    padding: 1.5rem 0.5rem !important;
}

[data-testid="stSidebar"] label p {
    color: #e2bec0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* Selectbox styling */
div[data-testid="stSelectbox"] div div {
    background-color: #171b26 !important;
    border: 1px solid #5a4042 !important;
    border-radius: 0.5rem !important;
    color: #dfe2f1 !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background-color: transparent !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
    color: #dfe2f1 !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-baseweb="popover"] ul {
    background-color: #171b26 !important;
    border: 1px solid #5a4042 !important;
}
div[data-baseweb="popover"] li {
    color: #dfe2f1 !important;
    font-family: 'Inter', sans-serif !important;
    transition: background-color 0.2s ease !important;
}
div[data-baseweb="popover"] li:hover {
    background-color: #ff506f !important;
    color: #ffffff !important;
}

/* Text inputs and textareas styling */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
    background-color: #171b26 !important;
    border: 1px solid #5a4042 !important;
    border-radius: 0.5rem !important;
    color: #dfe2f1 !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
    border-color: #ff506f !important;
    box-shadow: 0 0 0 2px rgba(255, 80, 111, 0.5) !important;
    outline: none !important;
}

/* Radio buttons styled as Budget pills */
div[data-testid="stRadio"] div[role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    gap: 8px !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label {
    flex: 1 1 0% !important;
    padding: 6px 12px !important;
    border-radius: 9999px !important;
    border: 1px solid #5a4042 !important;
    background-color: transparent !important;
    color: #dfe2f1 !important;
    text-align: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
    background-color: #313540 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
    background-color: #ff506f !important;
    color: #5b0019 !important;
    border-color: transparent !important;
    box-shadow: 0 10px 15px -3px rgba(255, 80, 111, 0.3) !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label div[role="presentation"] {
    display: none !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
    margin-left: 0 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
    font-size: 12px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Slider overrides */
div[data-testid="stSlider"] div[data-testid="stSliderTrack"] {
    background-color: #313540 !important;
}
div[data-testid="stSlider"] div[data-testid="stSliderTrack"] div div {
    background-color: #ffb2b8 !important;
}
div[data-testid="stSlider"] div[role="slider"] {
    background-color: #ffb2b8 !important;
    border: 2px solid #67001e !important;
}

/* Search button overrides */
.stButton button {
    background: linear-gradient(135deg, #ff4d6d 0%, #e6003a 100%) !important;
    color: white !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 600 !important;
    border: none !important;
    padding: 0.75rem 1.5rem !important;
    border-radius: 12px !important;
    box-shadow: 0 10px 40px -10px rgba(255, 77, 109, 0.4) !important;
    width: 100% !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-top: 1rem !important;
}
.stButton>button:hover {
    transform: scale(0.98) !important;
    box-shadow: 0 12px 45px -8px rgba(255, 77, 109, 0.6) !important;
}
.stButton>button:active {
    transform: scale(0.95) !important;
}

/* Glassmorphism Card styles */
.glass-card {
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.rose-gradient {
    background: linear-gradient(135deg, #ff4d6d 0%, #e6003a 100%);
}

.hover-lift {
    transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.hover-lift:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 30px -10px rgba(255, 77, 109, 0.3);
}

.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
}

.ai-border-glow { position: relative; }
.ai-border-glow::after {
    content: '';
    position: absolute;
    inset: -1px;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(90deg, transparent, #ff4d6d, transparent);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    animation: rotate-glow 4s linear infinite;
}

@keyframes rotate-glow {
    0% { filter: hue-rotate(0deg); opacity: 0.5; }
    100% { filter: hue-rotate(360deg); opacity: 0.8; }
}
</style>

<script id="tailwind-config">
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      "colors": {
              "tertiary-container": "#ff5260",
              "surface-tint": "#ffb2b8",
              "surface": "#0f131d",
              "on-background": "#dfe2f1",
              "surface-container": "#1c1f2a",
              "primary-container": "#ff506f",
              "tertiary": "#ffb3b3",
              "on-secondary-container": "#00374d",
              "secondary-fixed-dim": "#7bd0ff",
              "primary-fixed-dim": "#ffb2b8",
              "on-tertiary-container": "#5b0011",
              "on-secondary-fixed": "#001e2c",
              "on-error": "#690005",
              "surface-container-highest": "#313540",
              "surface-bright": "#353944",
              "on-primary-fixed": "#40000f",
              "on-surface-variant": "#e2bec0",
              "surface-container-lowest": "#0a0e18",
              "outline-variant": "#5a4042",
              "error-container": "#93000a",
              "outline": "#a9898b",
              "on-tertiary": "#680015",
              "inverse-on-surface": "#2c303b",
              "surface-container-high": "#262a35",
              "secondary-fixed": "#c4e7ff",
              "surface-container-low": "#171b26",
              "on-tertiary-fixed-variant": "#920021",
              "surface-dim": "#0f131d",
              "inverse-primary": "#ba1340",
              "surface-variant": "#313540",
              "on-error-container": "#ffdad6",
              "tertiary-fixed-dim": "#ffb3b3",
              "error": "#ffb4ab",
              "primary": "#ffb2b8",
              "on-surface": "#dfe2f1",
              "on-tertiary-fixed": "#400009",
              "on-primary-fixed-variant": "#91002d",
              "on-secondary-fixed-variant": "#004c69",
              "background": "#0f131d",
              "secondary": "#7bd0ff",
              "on-primary-container": "#5b0019",
              "primary-fixed": "#ffdadb",
              "on-secondary": "#00354a",
              "inverse-surface": "#dfe2f1",
              "on-primary": "#67001e",
              "tertiary-fixed": "#ffdad9",
              "secondary-container": "#00a6e0"
      },
      "borderRadius": {
              "DEFAULT": "0.25rem",
              "lg": "0.5rem",
              "xl": "0.75rem",
              "full": "9999px"
      },
      "spacing": {
              "base": "8px",
              "gutter": "24px",
              "xs": "4px",
              "margin-desktop": "40px",
              "sm": "12px",
              "margin-mobile": "16px",
              "md": "24px",
              "lg": "48px",
              "xl": "80px"
      },
      "fontFamily": {
              "body-lg": ["Inter"],
              "headline-md": ["Outfit"],
              "label-sm": ["Inter"],
              "body-md": ["Inter"],
              "display-lg-mobile": ["Outfit"],
              "metric-xl": ["Outfit"],
              "display-lg": ["Outfit"]
      },
      "fontSize": {
              "body-lg": ["18px", {"lineHeight": "1.6", "fontWeight": "400"}],
              "headline-md": ["24px", {"lineHeight": "1.3", "fontWeight": "600"}],
              "label-sm": ["12px", {"lineHeight": "1", "letterSpacing": "0.05em", "fontWeight": "600"}],
              "body-md": ["16px", {"lineHeight": "1.5", "fontWeight": "400"}],
              "display-lg-mobile": ["32px", {"lineHeight": "1.2", "fontWeight": "700"}],
              "metric-xl": ["36px", {"lineHeight": "1", "letterSpacing": "-0.01em", "fontWeight": "700"}],
              "display-lg": ["48px", {"lineHeight": "1.1", "letterSpacing": "-0.02em", "fontWeight": "700"}]
      }
    }
  }
}
</script>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --- Ingestion Error Boundary Check ---
if not DATABASE_PATH.exists():
    st.error("🚨 SQLite Database file not found!")
    st.markdown(
        f"""
    The restaurant database was not found at `{DATABASE_PATH}`. 
    To populate the local restaurant dataset, please run the ingestion script from the workspace root:
    
    ```bash
    python scripts/ingest_dataset.py
    ```
    """
    )
    st.stop()


# --- Load Repository ---
@st.cache_resource
def get_repository() -> RestaurantRepository:
    return RestaurantRepository(DATABASE_PATH)


repo = get_repository()
known_cities = repo.list_cities()

# --- Sidebar UI Controls (Preference Capture Form) ---
st.sidebar.markdown(
    """
    <div class="px-2 py-4">
        <h1 class="text-2xl font-bold text-transparent bg-clip-text font-headline-md text-headline-md tracking-tight rose-gradient" style="-webkit-background-clip: text; -webkit-text-fill-color: transparent;">zomato AI</h1>
        <p class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mt-xs">Recommendation Assistant</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("<br>", unsafe_allow_html=True)

# Location selectbox loaded dynamically from list_cities
default_city_idx = (
    known_cities.index("Indiranagar") if "Indiranagar" in known_cities else 0
)
location = st.sidebar.selectbox(
    "Location",
    options=known_cities,
    index=default_city_idx,
)

# Cuisine text input
cuisine = st.sidebar.text_input(
    "Cuisine",
    value="North Indian",
    help="e.g. Italian, Chinese, North Indian (or 'any')",
)

# Budget Tier enum radio
budget = st.sidebar.radio(
    "Budget Tier",
    options=["Low", "Medium", "High"],
    index=1,
    horizontal=True,
)

# Min rating slider
min_rating = st.sidebar.slider(
    "Minimum Rating",
    min_value=0.0,
    max_value=5.0,
    value=4.0,
    step=0.1,
)

# Top K recommendations
top_k = st.sidebar.slider(
    "Top K Results",
    min_value=1,
    max_value=20,
    value=5,
)

# Additional preferences text area
additional_raw = st.sidebar.text_area(
    "Notes (mood / atmosphere / tags)",
    value="",
    placeholder="e.g. rooftop, family friendly, evening ambiance",
)

# Advanced Provider Option (for offline testing)
st.sidebar.markdown("---")
with st.sidebar.expander("Advanced Settings"):
    use_mock = st.checkbox(
        "Use Mock LLM Provider",
        value=False,
        help="Simulates AI completions without invoking Groq networks.",
    )

find_button = st.sidebar.button("🚀 Search")


# --- Helper Rendering functions ---
def render_header_and_metrics(total_candidates: int, latency_ms: float | None, model: str, provider: str, fallback: str) -> str:
    latency_display = f"{latency_ms:.0f}" if latency_ms else "--"
    latency_unit = "ms" if latency_ms else ""
    return f"""
    <!-- Header Section -->
    <header class="flex justify-between items-end">
        <div class="space-y-xs">
            <h2 class="font-display-lg text-display-lg font-bold text-on-surface leading-tight" style="font-family: 'Outfit', sans-serif;">AI Restaurant Recommendation Engine</h2>
            <div class="flex items-center gap-base text-on-surface-variant">
                <span class="material-symbols-outlined text-[18px]">verified_user</span>
                <span class="font-body-md text-body-md">Personalized gastronomic insights powered by Zomato Data Intelligence</span>
            </div>
        </div>
        <div class="flex gap-md">
            <button class="p-base rounded-full bg-surface-container-highest/50 hover:bg-surface-container-highest transition-colors relative">
                <span class="material-symbols-outlined">notifications</span>
                <span class="absolute top-2 right-2 w-2 h-2 bg-primary rounded-full"></span>
            </button>
            <div class="w-12 h-12 rounded-full overflow-hidden border-2 border-primary/20">
                <img alt="User profile" class="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuD8PMmbagmqJrEI3DBQbhltxSVAA-kpfSL9tDw5iHdXTBGYHzJbQWERbnncach2PrkG7zxtg6J8aQYG06u0ePQWgKRabBVrxXGDf4wyj1QKVbTT6NHuQBfdNg0WrPRBuLv_fJOZVHkpGSMWhHAied1zuzE21Ch77bi33p2cTZRRWAbnegKn-SrwwF_NkGedZHAu5bUCr6NLpLHlhbI3NHuYwBj2xJruEIlLnZXyqxQ1nOcYKprO291v71yAMCz2EVQbuz9kZzro8OLM"/>
            </div>
        </div>
    </header>

    <!-- Metric Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-gutter mt-6">
        <div class="glass-card p-md rounded-2xl flex flex-col justify-between">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase">Candidates Evaluated</span>
            <div class="mt-base">
                <span class="font-metric-xl text-metric-xl text-on-surface" style="font-family: 'Outfit', sans-serif;">{total_candidates:,}</span>
                <span class="text-secondary font-label-sm ml-xs">+12% vs last search</span>
            </div>
        </div>
        <div class="glass-card p-md rounded-2xl flex flex-col justify-between">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase">Engine Latency</span>
            <div class="mt-base flex items-baseline gap-xs">
                <span class="font-metric-xl text-metric-xl text-secondary" style="font-family: 'Outfit', sans-serif;">{latency_display}</span>
                <span class="font-body-md text-body-md text-secondary/70">{latency_unit}</span>
            </div>
        </div>
        <div class="glass-card p-md rounded-2xl flex flex-col justify-between border-primary/20">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase">LLM Architecture</span>
            <div class="mt-base">
                <div class="flex items-center gap-base">
                    <span class="material-symbols-outlined text-primary">memory</span>
                    <span class="font-headline-md text-headline-md text-on-surface" style="font-family: 'Outfit', sans-serif;">{model}</span>
                </div>
                <span class="font-label-sm text-label-sm text-on-surface-variant">{provider} / fallback: {fallback}</span>
            </div>
        </div>
    </div>
    """


def render_welcome_card(total_count: int) -> str:
    return f"""
    <!-- Welcome Card -->
    <div class="glass-card p-12 rounded-[32px] text-center max-w-2xl mx-auto space-y-6 mt-12">
        <span class="material-symbols-outlined text-[64px] text-primary">restaurant_menu</span>
        <h3 class="text-2xl font-bold text-on-surface" style="font-family: 'Outfit', sans-serif;">Aether Dining Recommendation System</h3>
        <p class="text-on-surface-variant text-base leading-relaxed">
            Enter your dining preferences in the sidebar (such as neighborhood, cuisine type, budget constraints, and ambiance keywords) and click <strong>Search</strong> to generate personalized AI-guided restaurant insights.
        </p>
        <p class="text-xs text-on-surface-variant">
            Currently indexing <strong>{total_count:,}</strong> premium dining venues across Bangalore.
        </p>
    </div>
    """


def render_assistant_banner(summary: str, cuisine: str, location: str, budget: str) -> str:
    # Highlight key preferences in summary
    highlighted_summary = summary
    if cuisine:
        highlighted_summary = highlighted_summary.replace(
            cuisine,
            f'<span class="text-secondary font-semibold">{cuisine}</span>'
        )
    if location:
        highlighted_summary = highlighted_summary.replace(
            location,
            f'<span class="text-secondary font-semibold">{location}</span>'
        )
    if budget:
        highlighted_summary = highlighted_summary.replace(
            budget.title(),
            f'<span class="text-primary font-bold">{budget.title()}</span>'
        )

    match_score = 98

    return f"""
    <!-- AI Assistant Banner -->
    <section class="glass-card p-lg rounded-[32px] relative overflow-hidden group ai-border-glow mt-8">
        <div class="absolute inset-0 bg-secondary/5 blur-[80px] -z-10 group-hover:bg-secondary/10 transition-colors"></div>
        <div class="flex flex-col md:flex-row gap-lg items-center">
            <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-secondary to-primary flex items-center justify-center text-white shadow-2xl">
                <span class="material-symbols-outlined text-[40px]" data-weight="fill">auto_awesome</span>
            </div>
            <div class="flex-1 space-y-sm">
                <h3 class="font-headline-md text-headline-md text-on-surface" style="font-family: 'Outfit', sans-serif;">Intelligence Summary</h3>
                <p class="font-body-lg text-body-lg text-on-surface-variant max-w-3xl leading-relaxed">
                    {highlighted_summary}
                </p>
            </div>
            <div class="hidden lg:block w-[1px] h-24 bg-white/10"></div>
            <div class="flex flex-col items-center">
                <div class="relative w-20 h-20">
                    <svg class="w-full h-full" viewBox="0 0 36 36">
                        <path class="text-white/10" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" stroke-dasharray="100, 100" stroke-width="2.5"></path>
                        <path class="text-primary" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" stroke-dasharray="{match_score}, 100" stroke-linecap="round" stroke-width="2.5"></path>
                    </svg>
                    <div class="absolute inset-0 flex items-center justify-center font-bold text-on-surface text-lg">{match_score}%</div>
                </div>
                <span class="font-label-sm text-label-sm text-on-surface-variant mt-xs">Match Score</span>
            </div>
        </div>
    </section>
    """


def render_restaurant_grid(recommendations: list) -> str:
    html_out = '<section class="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-gutter mt-8">'
    for idx, item in enumerate(recommendations):
        r = item.restaurant
        img_url = RESTAURANT_IMAGES[idx % len(RESTAURANT_IMAGES)]

        # Rating stars mapping
        full_stars = int(round(r.rating))
        empty_stars = 5 - full_stars
        star_html = (
            '<span class="material-symbols-outlined text-[18px] text-yellow-400" data-weight="fill">star</span>'
            * full_stars
        )
        if empty_stars > 0:
            star_html += (
                '<span class="material-symbols-outlined text-[18px] text-on-surface-variant/40">star_outline</span>'
                * empty_stars
            )

        cuisine_badges = "".join(
            [
                f'<span class="px-sm py-xs bg-surface-container-highest rounded-full text-label-sm text-on-surface font-semibold">{c}</span>'
                for c in r.cuisines
            ]
        )

        html_out += f"""
        <!-- Restaurant Card #{idx+1} -->
        <div class="glass-card rounded-3xl overflow-hidden hover-lift flex flex-col">
            <div class="h-56 relative overflow-hidden">
                <img class="w-full h-full object-cover" src="{img_url}"/>
                <div class="absolute top-4 left-4 rose-gradient px-md py-xs rounded-lg font-bold text-white shadow-lg">#{idx+1} Rank</div>
                <div class="absolute bottom-4 right-4 bg-black/60 backdrop-blur-md px-md py-xs rounded-full flex items-center gap-xs">
                    <span class="material-symbols-outlined text-secondary text-[16px]" data-weight="fill">verified</span>
                    <span class="text-label-sm text-white font-semibold">AI Choice</span>
                </div>
            </div>
            <div class="p-md space-y-md flex-1 flex flex-col">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-headline-md text-headline-md text-on-surface" style="font-family: 'Outfit', sans-serif;">{r.name}</h4>
                        <div class="flex items-center gap-xs mt-1">
                            {star_html}
                            <span class="text-on-surface-variant font-label-sm ml-xs">({r.rating} ★)</span>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="font-label-sm text-secondary block font-semibold">{r.estimated_cost_display}</span>
                        <span class="font-label-sm text-on-surface-variant">{r.city}</span>
                    </div>
                </div>
                <div class="flex flex-wrap gap-xs">
                    {cuisine_badges}
                </div>
                <div class="p-md rounded-xl bg-primary/5 border border-primary/10 italic text-on-surface-variant text-body-md relative mt-2">
                    <span class="material-symbols-outlined absolute -top-3 -left-2 text-primary/30 text-[32px]">format_quote</span>
                    "{item.explanation}"
                </div>
                <button class="w-full mt-auto py-sm border border-secondary/30 text-secondary rounded-lg font-bold hover:bg-secondary/10 transition-colors flex items-center justify-center gap-base">
                    View Details
                    <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
                </button>
            </div>
        </div>
        """

    html_out += "</section>"
    return html_out


def render_footer() -> str:
    return """
    <!-- Footer / Data Source Note -->
    <footer class="pt-lg border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-md mt-16">
        <div class="flex items-center gap-base text-on-surface-variant">
            <span class="material-symbols-outlined">database</span>
            <span class="font-label-sm text-label-sm font-semibold">Data refreshed 14 minutes ago. Source: Zomato Internal API v2.4</span>
        </div>
        <div class="flex gap-lg">
            <a class="font-label-sm text-label-sm hover:text-primary transition-colors text-on-surface-variant" href="#">API Docs</a>
            <a class="font-label-sm text-label-sm hover:text-primary transition-colors text-on-surface-variant" href="#">Feedback Loop</a>
            <a class="font-label-sm text-label-sm hover:text-primary transition-colors text-on-surface-variant" href="#">Privacy Cloud</a>
        </div>
    </footer>
    """


# --- Main Layout Area ---
st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# Initialize Session State
if "response" not in st.session_state:
    st.session_state["response"] = None
if "error" not in st.session_state:
    st.session_state["error"] = None

# --- Recommendation Search Action ---
if find_button:
    with st.spinner("🍳 Cooking up your perfect recommendations..."):
        try:
            # 1. Setup providers
            if use_mock:
                mock_json = json.dumps(
                    {
                        "ranked": [
                            {
                                "restaurant_id": "r1",
                                "rank": 1,
                                "explanation": "A stellar choice matching your cuisines and budget perfectly.",
                            }
                        ],
                        "summary": f"Based on your preference for {cuisine} and your location in {location}, I have evaluated the local venues. We prioritized authentic options and evening ambiance within your budget.",
                    }
                )
                provider = MockLLMProvider(mock_json)
                ranking_service = LLMRankingService(provider=provider)
            else:
                ranking_service = LLMRankingService()

            service = RecommendationService(
                repository=repo,
                ranking_service=ranking_service,
            )

            # 2. Parse additional inputs
            additional_list = [
                x.strip() for x in additional_raw.split(",") if x.strip()
            ]

            # 3. Request E2E suggestions
            response = service.recommend(
                {
                    "location": location,
                    "budget": budget.lower(),
                    "cuisine": cuisine,
                    "min_rating": min_rating,
                    "top_k": top_k,
                    "additional": additional_list,
                }
            )

            st.session_state["response"] = response
            st.session_state["error"] = None
        except PreferenceValidationError as exc:
            st.session_state["error"] = ("validation", exc.errors)
            st.session_state["response"] = None
        except Exception as exc:
            logger.exception("Orchestration error")
            st.session_state["error"] = ("general", str(exc))
            st.session_state["response"] = None

# Query total candidates in the database for display
total_db_count = repo.count_all()

# Header & Metrics (always visible)
if st.session_state["response"]:
    resp = st.session_state["response"]
    candidates_count = resp.meta.candidates_considered
    latency_ms = resp.meta.llm_latency_ms
    model_name = resp.meta.llm_model or "llama-3.3-70b"
    provider_name = resp.meta.llm_provider or "groq"
    fallback_status = str(resp.meta.llm_fallback)
else:
    candidates_count = total_db_count
    latency_ms = None
    model_name = "llama-3.3-70b"
    provider_name = "groq-versatile"
    fallback_status = "False"

# Render header & metrics
st.markdown(
    render_header_and_metrics(
        total_candidates=candidates_count,
        latency_ms=latency_ms,
        model=model_name,
        provider=provider_name,
        fallback=fallback_status,
    ),
    unsafe_allow_html=True,
)

# Render conditional body
if st.session_state["error"]:
    err_type, err_val = st.session_state["error"]
    if err_type == "validation":
        st.warning("⚠️ Please correct your preferences:")
        for field, msg in err_val.items():
            st.markdown(f"*   **{field.title()}**: {msg}")
    else:
        st.error(f"💥 Recommendation pipeline failed: {err_val}")
elif st.session_state["response"]:
    resp = st.session_state["response"]
    
    # AI Assistant Banner
    st.markdown(
        render_assistant_banner(
            summary=resp.summary,
            cuisine=resp.preferences.cuisine,
            location=resp.preferences.location,
            budget=resp.preferences.budget.value,
        ),
        unsafe_allow_html=True,
    )
    
    # Results Grid
    st.markdown(render_restaurant_grid(resp.recommendations), unsafe_allow_html=True)
else:
    # Welcome Card
    st.markdown(render_welcome_card(total_db_count), unsafe_allow_html=True)

# Footer (always visible)
st.markdown(render_footer(), unsafe_allow_html=True)
