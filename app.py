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

st.set_page_config(page_title="Rekhta eBook Downloader", page_icon="bookdownloader.png")

st.markdown(
    """
    <style>
    div[data-testid="InputInstructions"] {
        display: none !important;
    }
    
    /* Enforce 100% identical height, margins, and borders */
    div[data-testid="stTextInput"],
    div[data-testid="stTextInput"] > div,
    div[data-testid="stTextInput"] input,
    div[data-testid="stButton"],
    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"],
    div[data-testid="stDownloadButton"] > button,
    .processing-container {
        height: 48px !important;
        min-height: 48px !important;
        max-height: 48px !important;
        box-sizing: border-box !important;
    }

    div[data-testid="stTextInput"] {
        margin-bottom: 8px !important;
    }
    div[data-testid="stButton"] {
        margin-top: 0px !important;
    }

    /* Text input styling */
    div[data-testid="stTextInput"] input {
        padding: 0 16px !important;
        background-color: #0e1117 !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: #ffffff !important;
        font-size: 16px !important;
        font-family: inherit !important;
        border-radius: 8px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #279e63 !important;
        box-shadow: none !important;
    }

    /* State 1 & General Button styling */
    div[data-testid="stButton"] > button {
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        font-size: 16px !important;
        font-family: inherit !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }
    div[data-testid="stButton"] > button:hover {
        border-color: #279e63 !important;
        color: #ffffff !important;
    }

    /* State 2: Processing Container styling */
    .processing-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        width: 100%;
        background-color: #212328;
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #ffffff;
        font-size: 16px;
        font-family: inherit;
        font-weight: 500;
        border-radius: 8px;
    }
    
    .spinner-ring {
        width: 15px;
        height: 15px;
        border: 2px dashed #ffffff;
        border-radius: 50%;
        animation: spin 1.2s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* State 3: Download Button green styling */
    div[data-testid="stDownloadButton"] > button {
        background-color: #0b291b !important;
        border: 1px solid #1f7a4d !important;
        color: #ffffff !important;
        font-size: 16px !important;
        font-family: inherit !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #123d29 !important;
        border-color: #279e63 !important;
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<h3 style='text-align: center; margin-bottom: 25px;'>📚 Rekhta eBook Downloader</h3>", unsafe_allow_html=True)

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
    
    return webdriver.Chrome(options=options)

def get_processing_html(percentage):
    return f"""
    <div class="processing-container">
        <div class="spinner-ring"></div>
        <span>Processing Generating eBook - {percentage}%</span>
    </div>
    """

url = st.text_input("Paste Rekhta Link Here:", placeholder="https://www.rekhta.org/ebooks/...")
if url:
    url = url.replace("/detail", "")

button_slot = st.empty()
start_clicked = button_slot.button("Start Extraction", use_container_width=True)

if start_clicked and url:
    driver = get_driver()
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)
    
    button_slot.markdown(get_processing_html(0), unsafe_allow_html=True)
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
                    
                    pct = min(int((extracted_count / target_pages) * 100), 100)
                    button_slot.markdown(get_processing_html(pct), unsafe_allow_html=True)
                    
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
            if stuck_counter % 3 == 0:
                click_next_page()
            if stuck_counter >= 15:
                break

    driver.quit()
    
    if len(images) > 0:
        pdf_buffer = BytesIO()
        images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:], resolution=100.0)
        pdf_data = pdf_buffer.getvalue()
        
        parsed_url = urlparse(url)
        slug = parsed_url.path.strip('/').split('/')[-1]
        filename = slug.replace('-', ' ').title() + ".pdf"
        
        button_slot.empty()
        button_slot.download_button(
            label="📥 Download Rekhta eBook",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True
        )
    else:
        button_slot.error("Failed to extract pages.")
