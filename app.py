import streamlit as st
import base64
import time
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

st.set_page_config(page_title="Rekhta PDF Extractor", page_icon="📚")
st.title("📚 Rekhta PDF Extractor")

st.markdown(
    """
    <style>
    div[data-testid="InputInstructions"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--user-data-dir=/tmp/chrome-session")
    
    driver = webdriver.Chrome(options=options)
    return driver

# --- UNIFIED STATUS TRACKER ---
def get_status_html(message, show_spinner=True):
    icon_html = """<div style="width: 18px; height: 18px; border: 2px solid rgba(128, 128, 128, 0.3); border-top: 2px solid var(--text-color); border-radius: 50%; animation: spin 1s linear infinite;"></div>""" if show_spinner else "✨"
    
    return f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-top: 6px;">
        {icon_html}
        <span style="font-size: 16px; font-weight: 500; color: var(--text-color);">{message}</span>
    </div>
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    """

url = st.text_input(" Paste Rekhta Link Here:", placeholder="https://www.rekhta.org/ebooks/...")

col1, col2 = st.columns([2, 8])
with col1:
    start_btn = st.button("Start Extraction", use_container_width=True)
with col2:
    status_placeholder = st.empty()

progress_bar = st.empty() 

if start_btn and url:
    progress_bar = progress_bar.progress(0)
    
    driver = get_driver()
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)
    
    # State A: Loading & Counting
    status_placeholder.markdown(get_status_html("Loading Book & Counting Pages..."), unsafe_allow_html=True)
    driver.get(url)
    time.sleep(5) 
    
    try:
        total_elem = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ebookTotalPageCount")))
        target_pages = int(total_elem.text.strip())
    except Exception:
        target_pages = 500
    
    images = []
    seen_b64 = set()
    extracted_count = 0
    stuck_counter = 0

    def get_visible_canvases():
        return driver.execute_script("""
            var windowWidth = window.innerWidth;
            var canvases = document.querySelectorAll("canvas.actualmage");
            var result = [];
            canvases.forEach(function(c) {
                var rect = c.getBoundingClientRect();
                var centerX = rect.left + (rect.width / 2);
                var style = window.getComputedStyle(c);
                
                if (centerX > 0 && centerX < windowWidth && rect.width > 0 && 
                    parseFloat(style.opacity) > 0.5 && style.visibility !== 'hidden' && style.display !== 'none') {
                    var b64 = c.toDataURL('image/jpeg', 1.0).substring(23);
                    result.push({ x: rect.left, b64: b64 });
                }
            });
            return result;
        """)

    def nuke_overlays():
        driver.execute_script("""
            var popups = document.querySelectorAll('.modal, .overlay, [role="dialog"], .popup');
            popups.forEach(function(p) { p.remove(); });
            var allDivs = document.querySelectorAll('div');
            allDivs.forEach(function(el) {
                var style = window.getComputedStyle(el);
                if ((style.position === 'fixed' || style.position === 'absolute') && parseInt(style.zIndex) > 10) {
                    if (!el.querySelector('canvas')) { el.style.display = 'none'; }
                }
            });
            document.body.style.overflow = 'auto';
        """)

    def click_next_page():
        nuke_overlays()
        body = driver.find_element(By.TAG_NAME, 'body')
        window_width = driver.execute_script("return window.innerWidth;")
        x_offset = int(-(window_width / 2) + 40)
        actions.reset_actions()
        actions.move_to_element_with_offset(body, x_offset, 0).click().pause(0.5).perform()

    # Initial Extraction State
    status_placeholder.markdown(get_status_html(f"Extracting Page {extracted_count} Out Of {target_pages}"), unsafe_allow_html=True)

    while extracted_count < target_pages:
        time.sleep(5) 
        
        nuke_overlays()
        canvas_data = get_visible_canvases()
        
        has_new = any(d['b64'] not in seen_b64 for d in canvas_data)
        
        if has_new:
            time.sleep(4)
            
            canvas_data = get_visible_canvases()
            canvas_data.sort(key=lambda item: item['x'], reverse=True)
            
            new_pages_added = 0
            for data in canvas_data:
                if data['b64'] not in seen_b64:
                    seen_b64.add(data['b64'])
                    img = Image.open(BytesIO(base64.b64decode(data['b64']))).convert('RGB')
                    images.append(img)
                    extracted_count += 1
                    new_pages_added += 1
                    
                    # State B: Dynamic Extraction Updates
                    status_placeholder.markdown(get_status_html(f"Extracting Page {extracted_count} Out Of {target_pages}"), unsafe_allow_html=True)
                    progress_bar.progress(min(extracted_count / target_pages, 1.0))
                    
                    if extracted_count >= target_pages:
                        break
                        
            if extracted_count >= target_pages:
                break
            
            if new_pages_added > 0:
                stuck_counter = 0
                time.sleep(1) 
                click_next_page()
            
        else:
            stuck_counter += 1
            status_placeholder.markdown(get_status_html(f"Waiting for network... ({stuck_counter}/15)"), unsafe_allow_html=True)
            
            if stuck_counter % 3 == 0:
                click_next_page()
            
            if stuck_counter >= 15:
                # Breaks out to compile what we have if stuck
                break

    driver.quit()
    
    # --- PDF GENERATION & FINAL STATE ---
    if len(images) > 0:
        status_placeholder.markdown(get_status_html("Compiling PDF..."), unsafe_allow_html=True)
        
        pdf_buffer = BytesIO()
        images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:], resolution=100.0)
        pdf_data = pdf_buffer.getvalue()
        
        parsed_url = urlparse(url)
        slug = parsed_url.path.strip('/').split('/')[-1]
        filename = slug.replace('-', ' ').title() + ".pdf"
        
        # State C: Completed
        status_placeholder.markdown(get_status_html("Extraction Completed, You Can Download The Book Now", show_spinner=False), unsafe_allow_html=True)
        
        st.download_button(
            label="Download PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf"
        )
    else:
        status_placeholder.markdown(get_status_html("Failed. No pages were extracted.", show_spinner=False), unsafe_allow_html=True)
